"""
StepStone (stepstone.de): Germany's biggest job board. No API: JobRadar
reads its public search pages

    https://www.stepstone.de/jobs/full-stack-developer?page=2

finds the job links (/stellenangebote--Full-Stack-Developer-Berlin-Acme--14030765-inline.html),
then opens each new tech job once and reads its schema.org JobPosting
(full description, company, place, date).

StepStone uses bot protection (Akamai). From a home internet connection
plain requests often work; when they are refused, installing curl_cffi
(pip install curl_cffi) lets JobRadar look like a real Chrome browser.
Check first with:  python sources_check.py stepstone
"""

import random
import re
import time

import pandas as pd

from .http import FetchError, get_html
from .jsonld import best_description, parse_job_page
from .relevance import is_tech_title

# The link also appears inside embedded JSON, with escaped slashes.
_JOB_LINK = re.compile(
    r"stellenangebote--([A-Za-z0-9%\-]+?)--(\d{5,})-inline\.html",
    re.IGNORECASE,
)

STOP_AFTER_FAILURES = 3


def slugify(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def job_links(page: str) -> list:
    """[(number, slug), ...] in page order, each job once."""

    found = {}

    for slug, number in _JOB_LINK.findall(page or ""):
        found.setdefault(number, slug)

    return list(found.items())


def title_from_slug(slug: str) -> str:
    """'Junior-Software-Engineer-AI-wmd-Muenchen-ADAC' -> words (title + place + company)."""

    return slug.replace("-", " ")


class StepStoneSource:

    def __init__(self, domain="www.stepstone.de", terms=(), country_key="germany",
                 country_name="Germany", max_pages=1, known_ids=(), get=None,
                 sleep=time.sleep, delay=(1.5, 3.5)):
        self.base = f"https://{domain}"
        self.terms = list(terms)
        self.country_key = country_key
        self.country_name = country_name
        self.max_pages = max_pages
        self.known_ids = set(known_ids)
        self.get = get
        self.sleep = sleep
        self.delay = delay
        self.name = "stepstone" if domain == "www.stepstone.de" else f"stepstone:{domain}"
        self.stats = {}

    def _page(self, url, params=None):
        return get_html(url, params=params, get=self.get, sleep=self.sleep, browser_like=True)

    def search_url(self, term):
        return f"{self.base}/jobs/{slugify(term)}"

    def fetch(self) -> pd.DataFrame:
        links = []
        reached = 0
        errors = []

        for term in self.terms:
            for number in range(1, self.max_pages + 1):
                if links or number > 1:
                    self.sleep(random.uniform(*self.delay))

                try:
                    page = self._page(self.search_url(term), {"page": number} if number > 1 else None)
                except FetchError as error:
                    errors.append(str(error))
                    break

                if number == 1:
                    reached += 1

                found = [link for link in job_links(page) if link not in links]

                if not found:
                    break

                links += found

        if self.terms and not reached:
            raise FetchError(errors[0] if errors else "no StepStone search page could be read")

        # The slug holds title, place and company; the title part decides.
        tech = [(n, slug) for n, slug in links if is_tech_title(title_from_slug(slug))]
        to_open = [(n, slug) for n, slug in tech if f"ss-{n}" not in self.known_ids]

        self.stats = {
            "listed": len(links),
            "tech": len(tech),
            "already_saved": len(tech) - len(to_open),
            "opened": 0,
            "structured": 0,
            "search_errors": errors,
        }

        rows = []
        failures = 0

        for number, slug in to_open:
            if failures >= STOP_AFTER_FAILURES:
                print(f"  stepstone: {failures} job pages failed in a row, stopping")
                break

            self.sleep(random.uniform(*self.delay))
            url = f"{self.base}/stellenangebote--{slug}--{number}-inline.html"

            try:
                page = self._page(url)
            except FetchError as error:
                failures += 1
                print(f"  stepstone: {error}")
                continue

            failures = 0
            self.stats["opened"] += 1

            job = parse_job_page(page)
            structured = job.pop("structured")
            self.stats["structured"] += int(structured)

            if not structured:
                continue   # a block page or a page without the job: not a job

            rows.append({
                "id": f"ss-{number}",
                "site": "stepstone",
                "job_url": url,
                **job,
                "description": best_description(job, page),
                "title": job["title"] or title_from_slug(slug),
                "location": job["location"] or self.country_name,
                "search_term": "stepstone",
                # A country search, like LinkedIn's: counts for that country.
                "search_country": self.country_key,
            })

        return pd.DataFrame(rows)