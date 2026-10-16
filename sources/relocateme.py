"""
Relocate.me: tech jobs that all come with a relocation package (often
visa services, a flight ticket, moving money). No API: JobRadar reads
the public list pages

    https://relocate.me/international-jobs?page=2

whose job links carry the place:  /netherlands/amsterdam/catawiki/lead-security-engineer-10303
Then it opens each new tech job once and keeps the page text.
"""

import random
import re
import time

import pandas as pd

from .http import FetchError, get_html
from .jsonld import best_description, page_text, parse_job_page
from .relevance import is_tech_title

BASE = "https://relocate.me"
LIST_URL = BASE + "/international-jobs"

_JOB_LINK = re.compile(
    r"""href=["'](?:https?://(?:www\.)?relocate\.me)?"""
    r"""/([a-z-]+)/([a-z0-9-]+)/([a-z0-9-]+)/([a-z0-9-]+?)-(\d+)["']""",
    re.IGNORECASE,
)

# Relocate.me's own ads among the jobs.
NOT_EMPLOYERS = {"the-global-move", "relocate-me"}

VISA_IN_PACKAGE = re.compile(r"visa (?:services|support|sponsorship|assistance)", re.IGNORECASE)

# "Senior Frontend Engineer | Relocation Offered"
TITLE_SUFFIX = re.compile(r"\s*\|\s*relocation offered\s*$", re.IGNORECASE)

STOP_AFTER_FAILURES = 3


def _words(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def job_links(page: str) -> list:
    """[{number, country, city, company, slug, path}, ...] in page order, once each."""

    found = {}

    for country, city, company, slug, number in _JOB_LINK.findall(page or ""):
        if company.lower() in NOT_EMPLOYERS or number in found:
            continue

        found[number] = {
            "number": number,
            "country": country.lower(),
            "city": city.lower(),
            "company": company.lower(),
            "slug": slug.lower(),
            "path": f"/{country}/{city}/{company}/{slug}-{number}".lower(),
        }

    return list(found.values())


def location_of(link) -> str:
    if link["country"] == "remote":
        return "Remote"

    return f"{_words(link['city'])}, {_words(link['country'])}"


class RelocateMeSource:

    name = "relocateme"

    def __init__(self, max_pages=5, known_ids=(), get=None, sleep=time.sleep, delay=(1.0, 2.5)):
        self.max_pages = max_pages
        self.known_ids = set(known_ids)
        self.get = get
        self.sleep = sleep
        self.delay = delay
        self.stats = {}

    def _page(self, url, params=None):
        return get_html(url, params=params, get=self.get, sleep=self.sleep)

    def fetch(self) -> pd.DataFrame:
        links = []
        seen = set()

        for number in range(1, self.max_pages + 1):
            try:
                page = self._page(LIST_URL, {"page": number} if number > 1 else None)
            except FetchError as error:
                if number == 1:
                    raise
                print(f"  relocateme: stopped at page {number}: {error}")
                break

            fresh = [link for link in job_links(page) if link["number"] not in seen]

            if not fresh:
                break

            for link in fresh:
                seen.add(link["number"])

            links += fresh

        tech = [link for link in links if is_tech_title(_words(link["slug"]))]
        to_open = [link for link in tech if f"rm-{link['number']}" not in self.known_ids]

        self.stats = {
            "listed": len(links),
            "tech": len(tech),
            "already_saved": len(tech) - len(to_open),
            "opened": 0,
            "structured": 0,
        }

        rows = []
        failures = 0

        for link in to_open:
            if failures >= STOP_AFTER_FAILURES:
                print(f"  relocateme: {failures} job pages failed in a row, stopping")
                break

            if self.stats["opened"]:
                self.sleep(random.uniform(*self.delay))

            url = BASE + link["path"]

            try:
                page = self._page(url)
            except FetchError as error:
                failures += 1
                print(f"  relocateme: {error}")
                continue

            failures = 0
            self.stats["opened"] += 1

            job = parse_job_page(page)
            self.stats["structured"] += int(job.pop("structured"))

            description = best_description(job, page)

            # The package ("Flight ticket, Visa services") is shown next to
            # the description, not inside it.
            package = page_text(page)[:1500]

            rows.append({
                "id": f"rm-{link['number']}",
                "site": "relocateme",
                "job_url": url,
                **job,
                "title": TITLE_SUFFIX.sub("", job["title"] or "") or _words(link["slug"]),
                "company": job["company"] or _words(link["company"]),
                "location": job["location"] or location_of(link),
                "is_remote": job["is_remote"] or link["country"] == "remote",
                "description": description,
                "search_term": "relocateme",
                # Every job here has a relocation package; most include visa help.
                "source_hint": "visa" if VISA_IN_PACKAGE.search(package + description) else "relocation",
            })

        return pd.DataFrame(rows)