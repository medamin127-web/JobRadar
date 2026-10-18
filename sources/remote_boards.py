"""
Remote-only job boards, all with free public feeds (no scraping of web
pages, no login):

    remotive        https://remotive.com/api/remote-jobs?category=software-dev
                    Asks for at most ~4 calls a day: JobRadar keeps a copy
                    for REMOTIVE_CACHE_HOURS and reuses it.
    remoteok        https://remoteok.com/api          (latest jobs, all kinds)
    weworkremotely  RSS feeds of the programming categories
    workingnomads   https://www.workingnomads.com/api/exposed_jobs/
    himalayas       https://himalayas.app/jobs/api/search?country=Tunisia
                    Already filtered to jobs open to people in your country.

Every board asks to be credited and linked: each job keeps the board's
own link (job_url), so you open it on the board.

The job's location is the board's region text ("Anywhere in the World",
"USA Only", "Europe"): eligibility_analyzer.py decides from it whether
you can do the job from Tunisia.
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pandas as pd

from .http import FetchError, get_html, get_json
from .relevance import is_tech_title
from .text import html_to_text

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
REMOTEOK_API = "https://remoteok.com/api"
WORKINGNOMADS_API = "https://www.workingnomads.com/api/exposed_jobs/"
HIMALAYAS_SEARCH = "https://himalayas.app/jobs/api/search"
WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
]

CACHE_DIR = os.path.join("data", "cache")
REMOTIVE_CACHE_HOURS = 6


def _date(value) -> str | None:
    """ISO date (YYYY-MM-DD) from an epoch number or an ISO / RSS date."""

    if value in (None, ""):
        return None

    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()

        text = str(value)

        if re.match(r"\d{4}-\d{2}-\d{2}", text):
            return text[:10]

        return parsedate_to_datetime(text).date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def _short_hash(text) -> str:
    return hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:12]


def _row(site, prefix, key, url, title, company, region, date, description, tags=None, hint=None):
    tags = [t for t in (tags or []) if t]
    text = html_to_text(description)

    return {
        "id": f"{prefix}-{key}",
        "site": site,
        "job_url": url,
        "title": (title or "").strip() or None,
        "company": (company or "").strip() or None,
        # The board's region text, e.g. "Anywhere in the World", "USA Only".
        "location": (region or "").strip() or "Remote",
        "date_posted": date,
        "is_remote": True,
        "job_type": None,
        "description": text + (f"\n\nTags: {', '.join(tags)}" if tags else ""),
        "search_term": site,
        "source_hint": hint,
    }


class _Board:

    name = "board"

    def __init__(self, get=None, sleep=time.sleep, cache_dir=CACHE_DIR):
        self.get = get
        self.sleep = sleep
        self.cache_dir = cache_dir
        self.stats = {}

    def _json(self, url, params=None):
        return get_json(url, params=params, get=self.get, sleep=self.sleep)

    def fetch(self) -> pd.DataFrame:
        rows = [row for row in self.rows() if row["title"] and row["job_url"]]
        self.stats = {"listed": len(rows), "tech": sum(is_tech_title(r["title"]) for r in rows)}
        return pd.DataFrame(rows)

    def rows(self):
        raise NotImplementedError


class RemotiveSource(_Board):

    name = "remotive"

    def _payload(self):
        """The API answer, reused for REMOTIVE_CACHE_HOURS (they ask for few calls)."""

        path = os.path.join(self.cache_dir, "remotive.json") if self.cache_dir else None

        if path and os.path.exists(path):
            age_hours = (time.time() - os.path.getmtime(path)) / 3600

            if age_hours < REMOTIVE_CACHE_HOURS:
                with open(path, encoding="utf-8") as handle:
                    return json.load(handle)

        payload = self._json(REMOTIVE_API, {"category": "software-dev", "limit": 150})

        if path:
            os.makedirs(self.cache_dir, exist_ok=True)

            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

        return payload

    def rows(self):
        for job in self._payload().get("jobs") or []:
            yield _row(
                "remotive", "rv", job.get("id"), job.get("url"), job.get("title"),
                job.get("company_name"), job.get("candidate_required_location"),
                _date(job.get("publication_date")), job.get("description"), job.get("tags"),
            )


class RemoteOKSource(_Board):

    name = "remoteok"

    def rows(self):
        payload = self._json(REMOTEOK_API)

        # The first element is their legal notice, not a job.
        for job in payload if isinstance(payload, list) else []:
            if not isinstance(job, dict) or not job.get("position"):
                continue

            yield _row(
                "remoteok", "rok", job.get("id"), job.get("url"), job.get("position"),
                job.get("company"), job.get("location") or "Worldwide",
                _date(job.get("epoch") or job.get("date")), job.get("description"), job.get("tags"),
            )


class WeWorkRemotelySource(_Board):

    name = "weworkremotely"

    def rows(self):
        import xml.etree.ElementTree as ET

        seen = set()

        for feed in WWR_FEEDS:
            try:
                xml = get_html(feed, get=self.get, sleep=self.sleep)
            except FetchError as error:
                print(f"  weworkremotely: {error}")
                continue

            try:
                root = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
            except ET.ParseError as error:
                print(f"  weworkremotely: unreadable feed ({error})")
                continue

            for item in root.iter("item"):
                text = lambda tag: (item.findtext(tag) or "").strip()
                link = text("link") or text("guid")

                if not link or link in seen:
                    continue

                seen.add(link)

                # "Company: Job title"
                company, _, title = text("title").partition(": ")
                if not title:
                    company, title = "", company

                region = ", ".join(v for v in (text("region"), text("country")) if v)

                yield _row(
                    "weworkremotely", "wwr", link.rstrip("/").rsplit("/", 1)[-1], link, title,
                    company, region, _date(text("pubDate")), text("description"),
                    [text("skills")] if text("skills") else None,
                )


class WorkingNomadsSource(_Board):

    name = "workingnomads"

    def rows(self):
        payload = self._json(WORKINGNOMADS_API)

        for job in payload if isinstance(payload, list) else []:
            category = str(job.get("category_name") or "").lower()

            if "develop" not in category and "engineer" not in category and not is_tech_title(job.get("title")):
                continue

            url = job.get("url") or ""
            number = re.search(r"/(\d+)/?$", url)

            yield _row(
                "workingnomads", "wn", number.group(1) if number else _short_hash(url), url,
                job.get("title"), job.get("company_name"), job.get("location") or "Anywhere",
                _date(job.get("pub_date")), job.get("description"),
                str(job.get("tags") or "").split(","),
            )


class HimalayasSource(_Board):
    """
    Himalayas' search, filtered to jobs open to people living in your
    country (YOUR_COUNTRY in config.py), so these get source_hint
    "open_to_you".
    """

    name = "himalayas"

    def __init__(self, terms, country="Tunisia", pages=1, delay=1.0, **kwargs):
        super().__init__(**kwargs)
        self.terms = terms
        self.country = country
        self.pages = pages
        self.delay = delay

    def rows(self):
        seen = set()
        calls = 0

        for term in self.terms:
            for page in range(1, self.pages + 1):
                if calls:
                    self.sleep(self.delay)
                calls += 1

                try:
                    payload = self._json(HIMALAYAS_SEARCH, {
                        "q": term, "country": self.country, "sort": "recent", "page": page,
                    })
                except FetchError as error:
                    print(f"  himalayas: '{term}' page {page}: {error}")
                    break

                jobs = payload.get("jobs") or []

                for job in jobs:
                    guid = job.get("guid") or job.get("applicationLink")

                    if not guid or guid in seen:
                        continue

                    seen.add(guid)
                    places = job.get("locationRestrictions") or []
                    region = ", ".join(str(p) for p in places) if places else "Worldwide"

                    yield _row(
                        "himalayas", "hm", _short_hash(guid), job.get("applicationLink") or guid,
                        job.get("title"), job.get("companyName"), region, _date(job.get("pubDate")),
                        job.get("description") or job.get("excerpt"),
                        job.get("categories"), hint="open_to_you",
                    )

                if not jobs:
                    break


def remote_board_sources(names, himalayas_terms, your_country="Tunisia"):
    """The board sources named in config.py (REMOTE_BOARDS)."""

    makers = {
        "remotive": lambda: RemotiveSource(),
        "remoteok": lambda: RemoteOKSource(),
        "weworkremotely": lambda: WeWorkRemotelySource(),
        "workingnomads": lambda: WorkingNomadsSource(),
        "himalayas": lambda: HimalayasSource(himalayas_terms, country=your_country),
    }

    unknown = [name for name in names if name not in makers]

    if unknown:
        raise SystemExit(f"Unknown board in config.py REMOTE_BOARDS: {', '.join(unknown)}\n"
                         f"Known: {', '.join(makers)}")

    return [makers[name]() for name in names]