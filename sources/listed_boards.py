"""
Country job boards without an API, read like Relocate.me: a public list
page, its job links, then each new tech job page once (its schema.org
JobPosting when it has one, else the page text).

    Japan   tokyodev     https://www.tokyodev.com/jobs/apply-from-abroad
                         (only jobs you can apply to from abroad)
            japandev     https://japan-dev.com/japan-jobs-relocation
                         ("Apply from Abroad" jobs)
    Poland  justjoinit   https://justjoin.it/job-offers/all-locations/javascript ...
            nofluffjobs  https://nofluffjobs.com/frontend ...

The Japan boards show badges next to each job ("No Japanese required",
"Business Japanese", "Japan residents only"). JobRadar adds them to the
description as plain sentences, so the language and local-hiring checks
read them like any ad text.

If a board changes its layout, "python sources_check.py tokyodev dump"
saves the pages in data/samples to fix the parser.
"""

import hashlib
import random
import re
import time

import pandas as pd

from .http import FetchError, get_html
from .jsonld import best_description, parse_job_page
from .relevance import is_tech_title

STOP_AFTER_FAILURES = 3

# Badge on the list page -> sentence added to the description.
JAPAN_BADGES = [
    (re.compile(r"no japanese required|japanese not required", re.I), "Japanese is not required."),
    (re.compile(r"business(?:[- ]level)? japanese|japanese[^<]{0,20}business", re.I),
     "Japanese language skills at business level are required."),
    (re.compile(r"conversational japanese", re.I), "Japanese language skills at conversational level are required."),
    (re.compile(r"fluent japanese|native japanese", re.I), "Fluent Japanese language skills are required."),
    (re.compile(r"(?<!no )japanese required", re.I), "Japanese language skills are required."),
    (re.compile(r"residents only", re.I), "Applicants must already reside in Japan."),
    (re.compile(r"apply from abroad", re.I), "Applicants from abroad are accepted (visa sponsorship)."),
]


def _words(slug: str) -> str:
    return " ".join(part.capitalize() for part in str(slug).split("-") if part)


def _short_hash(text) -> str:
    return hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:12]


class ListedBoard:
    """One board: its list pages, how its job links look, what it hints."""

    def __init__(
        self,
        name,
        prefix,
        base,
        list_urls,
        link_pattern,
        country_name,
        country_key=None,
        country_codes=(),
        hint=None,
        badges=None,
        title_from=None,
        max_pages=1,
        page_param="page",
        known_ids=(),
        get=None,
        sleep=time.sleep,
        delay=(1.0, 2.5),
    ):
        self.name = name
        self.prefix = prefix
        self.base = base
        self.list_urls = list_urls
        self.link_pattern = re.compile(link_pattern, re.IGNORECASE)
        self.country_name = country_name
        self.country_key = country_key or country_name.lower()
        # How the board writes the country after a city: "Warszawa, PL".
        self.country_codes = [code.lower() for code in country_codes]
        self.hint = hint
        self.badges = badges or []
        self.title_from = title_from or (lambda path: _words(path.rstrip("/").rsplit("/", 1)[-1]))
        self.max_pages = max_pages
        self.page_param = page_param
        self.known_ids = set(known_ids)
        self.get = get
        self.sleep = sleep
        self.delay = delay
        self.stats = {}

    # ------------------------------------------------------------ pages

    def _page(self, url, params=None):
        return get_html(url, params=params, get=self.get, sleep=self.sleep)

    def job_links(self, page: str) -> list:
        """[(path, badge sentences)] in page order, each job once."""

        page = page or ""
        matches = list(self.link_pattern.finditer(page))
        found = {}

        for index, match in enumerate(matches):
            path = match.group(1)

            if path in found:
                continue

            # The card: from this link to the next job link.
            end = matches[index + 1].start() if index + 1 < len(matches) else len(page)
            card = re.sub(r"<[^>]+>", " ", page[match.start(): min(end, match.start() + 6000)])
            sentences = [text for pattern, text in self.badges if pattern.search(card)]

            # A board's first match wins (business beats "japanese required").
            if any("business level" in s or "conversational" in s or "Fluent" in s for s in sentences):
                sentences = [s for s in sentences if s != "Japanese language skills are required."]

            found[path] = sentences

        return list(found.items())

    def place(self, raw):
        """
        (location, country key or None, remote?) from the page's location.

            ""                            -> the board's country
            "Warszawa, PL"                -> the board's country
            "London, GB"                  -> left as it is (another country)
            "Poland | Hungary | ... (all the world)"
                                          -> a remote job: country "remote"
        """

        raw = str(raw or "").strip()
        parts = [p.strip() for p in raw.split("|") if p.strip() and p.strip() != "---"]

        if len(parts) >= 5:
            return "Remote: " + ", ".join(parts), "remote", True

        if not raw:
            return self.country_name, self.country_key, False

        lowered = raw.lower()
        codes = [c for c in self.country_codes if re.search(r",\s*" + re.escape(c) + r"\b", lowered)]

        if self.country_name.lower() in lowered or codes:
            name = raw if self.country_name.lower() in lowered else f"{raw}, {self.country_name}"
            return name, self.country_key, False

        return raw, None, False

    def job_id(self, path) -> str:
        number = re.search(r"-(\d{3,})/?$", path)
        return f"{self.prefix}-{number.group(1) if number else _short_hash(path)}"

    # ------------------------------------------------------------ fetch

    def fetch(self) -> pd.DataFrame:
        links = {}

        for url in self.list_urls:
            for number in range(1, self.max_pages + 1):
                params = {self.page_param: number} if number > 1 else None

                try:
                    page = self._page(url, params)
                except FetchError as error:
                    if number == 1:
                        print(f"  {self.name}: {error}")
                    break

                fresh = [(p, b) for p, b in self.job_links(page) if p not in links]

                if not fresh:
                    break

                links.update(fresh)

        tech = [(p, b) for p, b in links.items() if is_tech_title(self.title_from(p))]
        to_open = [(p, b) for p, b in tech if self.job_id(p) not in self.known_ids]

        self.stats = {
            "listed": len(links),
            "tech": len(tech),
            "already_saved": len(tech) - len(to_open),
            "opened": 0,
            "structured": 0,
        }

        if not links and self.list_urls:
            # Every list page failed or had no job links.
            raise FetchError(f"no job links found on {self.list_urls[0]}")

        rows = []
        failures = 0

        for path, badges in to_open:
            if failures >= STOP_AFTER_FAILURES:
                print(f"  {self.name}: {failures} job pages failed in a row, stopping")
                break

            if self.stats["opened"]:
                self.sleep(random.uniform(*self.delay))

            url = self.base + path

            try:
                page = self._page(url)
            except FetchError as error:
                failures += 1
                print(f"  {self.name}: {error}")
                continue

            failures = 0
            self.stats["opened"] += 1

            job = parse_job_page(page)
            self.stats["structured"] += int(job.pop("structured"))

            description = best_description(job, page)

            if badges:
                description = " ".join(badges) + "\n\n" + description

            location, country, remote = self.place(job["location"])

            rows.append({
                "id": self.job_id(path),
                "site": self.name,
                "job_url": url,
                **job,
                "title": job["title"] or self.title_from(path),
                "location": location,
                "is_remote": bool(job["is_remote"]) or remote,
                "search_country": country,
                "description": description,
                "search_term": self.name,
                "source_hint": self.hint,
            })

        return pd.DataFrame(rows)


# ==================================================
# THE BOARDS
# ==================================================

def tokyodev(**kwargs) -> ListedBoard:
    return ListedBoard(
        name="tokyodev",
        prefix="td",
        base="https://www.tokyodev.com",
        list_urls=["https://www.tokyodev.com/jobs/apply-from-abroad"],
        link_pattern=r"""href=["'](?:https?://www\.tokyodev\.com)?(/companies/[a-z0-9-]+/jobs/[a-z0-9-]+)["']""",
        country_name="Japan",
        country_key="japan",
        country_codes=("jp", "jpn"),
        # Every job on this list accepts people from abroad (visa sponsored).
        hint="visa",
        badges=JAPAN_BADGES,
        **kwargs,
    )


def japandev(**kwargs) -> ListedBoard:
    return ListedBoard(
        name="japandev",
        prefix="jd",
        base="https://japan-dev.com",
        list_urls=["https://japan-dev.com/japan-jobs-relocation"],
        link_pattern=r"""href=["'](?:https?://japan-dev\.com)?(/jobs/[a-z0-9-]+/[a-z0-9-]+)["']""",
        country_name="Japan",
        country_key="japan",
        country_codes=("jp", "jpn"),
        hint="visa",
        badges=JAPAN_BADGES,
        **kwargs,
    )


def justjoinit(**kwargs) -> ListedBoard:
    return ListedBoard(
        name="justjoinit",
        prefix="jj",
        base="https://justjoin.it",
        list_urls=[
            f"https://justjoin.it/job-offers/all-locations/{category}"
            for category in ("javascript", "php", "python", "java")
        ],
        link_pattern=r"""href=["'](?:https?://justjoin\.it)?(/job-offer/[a-z0-9-]+)["']""",
        country_name="Poland",
        country_key="poland",
        country_codes=("pl", "pol"),
        **kwargs,
    )


def nofluffjobs(**kwargs) -> ListedBoard:
    return ListedBoard(
        name="nofluffjobs",
        prefix="nf",
        base="https://nofluffjobs.com",
        list_urls=[f"https://nofluffjobs.com/{category}" for category in ("frontend", "backend", "fullstack")],
        link_pattern=r"""href=["'](?:https?://nofluffjobs\.com)?(/(?:[a-z]{2}/)?job/[a-z0-9-]+)["']""",
        country_name="Poland",
        country_key="poland",
        country_codes=("pl", "pol"),
        **kwargs,
    )


BOARDS = {"tokyodev": tokyodev, "japandev": japandev, "justjoinit": justjoinit, "nofluffjobs": nofluffjobs}


def country_board_sources(configs, max_pages=1, known_ids=()):
    """The boards of the countries searched this run ("boards" in countries.py)."""

    sources = []

    for config in configs:
        for name in config.get("boards") or []:
            if name not in BOARDS:
                raise SystemExit(f"Unknown board '{name}' in countries.py ({config['key']}). "
                                 f"Known: {', '.join(BOARDS)}")

            sources.append(BOARDS[name](max_pages=max_pages, known_ids=known_ids))

    return sources