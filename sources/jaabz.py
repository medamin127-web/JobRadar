"""
Jaabz (jaabz.com): a job board of jobs with visa sponsorship. It has no
API, so JobRadar reads its public list for each of your countries:

    https://jaabz.com/jobs?countries=saudi-arabia&visa_sponsorship=1&search_submitted=1

Each page links to up to 24 jobs (/jobs/284930-backend-engineer-ii-remote).
The job's title in the link decides whether it is worth opening; then
the job page is read (its schema.org JobPosting, see jsonld.py).

Jaabz marks every job on this list as visa-sponsored, so the jobs get
source_hint "visa": weaker than the listing saying it (see
eligibility_evaluator.py), but it keeps them out of "probably no visa".
"""

import random
import re
import time

import pandas as pd

from .http import FetchError, get_html
from .jsonld import best_description, parse_job_page
from .relevance import is_tech_title

BASE = "https://jaabz.com"
LIST_URL = BASE + "/jobs"

# When the country search fails (Jaabz returned HTTP 500 for a while):
#   1. the country's landing page (only ~6 jobs, but the right country)
#   2. if no country could be read at all: the general programming list
LANDING_URL = BASE + "/jobs/in/{slug}/visasponsorship"
PROGRAMMING_URL = BASE + "/jobs/programming/visasponsorship"


def list_params(country_slug, page):
    return {
        "countries": country_slug,
        "visa_sponsorship": 1,
        "search_submitted": 1,
        "page": page,
    }

_JOB_LINK = re.compile(r"""href=["'](?:https?://(?:www\.)?jaabz\.com)?/jobs/(\d+)-([a-z0-9-]+)["']""", re.IGNORECASE)

# After this many job pages fail in a row, the site is probably blocking us.
STOP_AFTER_FAILURES = 3


def job_links(page: str) -> list:
    """[(number, slug), ...] in page order, each job once."""

    seen = {}

    for number, slug in _JOB_LINK.findall(page or ""):
        seen.setdefault(number, slug.lower())

    return list(seen.items())


def title_from_slug(slug: str) -> str:
    return slug.replace("-", " ")


class JaabzSource:

    name = "jaabz"

    def __init__(self, countries, max_pages=2, known_ids=(), get=None, sleep=time.sleep, delay=(1.0, 2.5)):
        """countries: [(jaabz slug, country name), ...], e.g. [("qatar", "Qatar")]"""
        self.countries = list(countries)
        self.max_pages = max_pages
        self.known_ids = set(known_ids)
        self.get = get
        self.sleep = sleep
        self.delay = delay

        # Filled by fetch(), for sources_check.py.
        self.stats = {}

    def _page(self, url, params=None):
        return get_html(url, params=params, get=self.get, sleep=self.sleep)

    def _read_list(self, url, params_for_page, label, links, country_of, country=None):
        """Read up to max_pages of one list. Returns True if page 1 was read."""

        for number in range(1, self.max_pages + 1):
            try:
                page = self._page(url, params_for_page(number) or None)
            except FetchError as error:
                if number == 1:
                    print(f"  jaabz {label}: {error}")
                    return False
                if "404" not in str(error):    # 404 after page 1 = end of the list
                    print(f"  jaabz {label}: stopped at page {number}: {error}")
                break

            found = [link for link in job_links(page) if link not in links]

            if not found:
                break   # empty page, or the same page again

            links += found

            if country:
                for job_number, _ in found:
                    country_of.setdefault(job_number, country)

            if params_for_page(number + 1) is None:
                break   # a list without pages

        return True

    def fetch(self) -> pd.DataFrame:
        links = []          # (number, slug)
        country_of = {}     # number -> country name of the list it came from
        reached = 0
        fallbacks = []

        for slug_country, name in self.countries:
            ok = self._read_list(
                LIST_URL, lambda n, c=slug_country: list_params(c, n),
                name, links, country_of, name,
            )

            if not ok:
                # The country search failed: its landing page has a few jobs.
                ok = self._read_list(
                    LANDING_URL.format(slug=slug_country),
                    lambda n: {} if n == 1 else None,
                    f"{name} (landing page)", links, country_of, name,
                )
                if ok:
                    fallbacks.append(f"{name}: landing page only")

            reached += ok

            if self.sleep:
                self.sleep(random.uniform(*self.delay))

        if not reached:
            # No country page at all: the general programming list (all
            # countries; the ranking keeps yours).
            if self._read_list(
                PROGRAMMING_URL, lambda n: {"query": "", "page": n},
                "programming list", links, country_of,
            ):
                fallbacks.append("country pages down: read the general programming list")
            else:
                raise FetchError("no Jaabz list page could be read")

        for note in fallbacks:
            print(f"  jaabz: {note}")

        tech = [(n, slug) for n, slug in links if is_tech_title(title_from_slug(slug))]
        to_open = [(n, slug) for n, slug in tech if f"jz-{n}" not in self.known_ids]

        self.stats = {
            "listed": len(links),
            "tech": len(tech),
            "already_saved": len(tech) - len(to_open),
            "opened": 0,
            "structured": 0,
            "fallbacks": fallbacks,
        }

        rows = []
        failures = 0

        for number, slug in to_open:
            if failures >= STOP_AFTER_FAILURES:
                print(f"  jaabz: {failures} job pages failed in a row, stopping")
                break

            if self.stats["opened"]:
                self.sleep(random.uniform(*self.delay))

            url = f"{BASE}/jobs/{number}-{slug}"

            try:
                page = self._page(url)
            except FetchError as error:
                failures += 1
                print(f"  jaabz: {error}")
                continue

            failures = 0
            self.stats["opened"] += 1

            job = parse_job_page(page)
            self.stats["structured"] += int(job.pop("structured"))

            # Jaabz's JobPosting has only a short summary.
            job["description"] = best_description(job, page)

            rows.append({
                "id": f"jz-{number}",
                "site": "jaabz",
                "job_url": url,
                **job,
                "title": job["title"] or title_from_slug(slug).title(),
                # The list was filtered by country: use it when the page
                # does not say where the job is.
                "location": job["location"] or country_of.get(number),
                "search_term": "jaabz",
                "source_hint": "visa",
            })

        return pd.DataFrame(rows)