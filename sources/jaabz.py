"""
Jaabz (jaabz.com): a job board of jobs with visa sponsorship. It has no
API, so JobRadar reads its public list for each of your countries:

    https://jaabz.com/jobs?countries=saudi-arabia&visa_sponsorship=1&search_submitted=1

Each page links to up to 24 jobs (/jobs/284930-backend-engineer-ii-remote).
The job's title in the link decides whether it is worth opening; then
the job page is read (its schema.org JobPosting, see jsonld.py).

A Jaabz job page shows only a short excerpt of the ad, Jaabz's badges
(Visa Sponsorship / Relocation / Remote, checked when they apply) and a
link to the original posting (often LinkedIn), which is read for the
full description. Everything else on the page is Jaabz's own promotion
and is ignored.

A checked Visa Sponsorship badge gives the job source_hint "visa": weaker
than the ad saying it (see eligibility_evaluator.py), but it keeps the
job out of "probably no visa".
"""

import random
import re
import time

import pandas as pd

from .http import FetchError, get_html
from .jsonld import parse_job_page
from .text import html_to_text
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


# ---------------------------------------------------------------- job page

# Jaabz shows only a short excerpt; the full ad is on the original site.
_EXCERPT = re.compile(
    r'<div[^>]*class="[^"]*description-excerpt[^"]*"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_ORIGINAL = re.compile(
    r'class="[^"]*source-readmore-btn[^"]*"[^>]*?href="([^"]+)"'
    r'|href="([^"]+)"[^>]*class="[^"]*source-readmore-btn',
    re.IGNORECASE | re.DOTALL,
)
# The job's badges: <span class="benefit-tag active" itemprop="jobBenefits">
# <i ...></i><span>Visa Sponsorship</span> ... ("inactive" = does not apply).
_BADGE = re.compile(
    r'class="benefit-tag\s+(active|inactive)[^"]*"[^>]*>\s*(?:<i[^>]*>\s*</i>\s*)?<span[^>]*>([^<]+)</span>',
    re.IGNORECASE,
)
_DETAIL = re.compile(
    r'class="detail-label"[^>]*>(.*?)</span>\s*<span[^>]*class="detail-value"[^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
LINKEDIN_JOB = re.compile(r"linkedin\.com/jobs/view/(?:[^/?#]*-)?(\d{6,})", re.IGNORECASE)


# Jaabz's own summary of the ad: years asked, responsibilities, skills,
# benefits ("Visa sponsorship", "Relocation package"), nice to have.
_SUMMARY_SECTION = re.compile(
    r'<div[^>]*class="ai-(summary-text|key-points|responsibilities|requirements|qualifications'
    r'|hard-skills|soft-skills|benefits|nice-to-have)"[^>]*>',
    re.IGNORECASE,
)
_SECTION_END = re.compile(r'<div[^>]*class="(?:ai-|category-links-box)|Job Description', re.IGNORECASE)


def summary_sections(page: str) -> str:
    """The summary boxes of a Jaabz job page as plain text (headings kept)."""

    parts = []

    for match in _SUMMARY_SECTION.finditer(page or ""):
        rest = page[match.end():]
        end = _SECTION_END.search(rest)
        chunk = rest[: end.start() if end else 6000]
        text = re.sub(r"\n\s*\n+", "\n", html_to_text(chunk)).strip()

        if text:
            parts.append(text)

    return "\n\n".join(parts)


def _main_part(page: str) -> str:
    """The job itself: before the first list of other jobs ("premium" cards)."""

    end = page.find("premium-hidden")
    return page if end < 0 else page[:end]


def read_job_page(page: str) -> dict:
    """
    -> excerpt (plain text), original_url, badges {"Visa Sponsorship": True,
       "Relocation": False, ...}, details {"Job Type": "Full-time", ...}
    """

    main = _main_part(page or "")

    excerpt = _EXCERPT.search(main)
    original = _ORIGINAL.search(main)

    first_details = main.find("job-details-full")
    badge_area = main[:first_details] if first_details >= 0 else main
    badges = {}

    for state, name in _BADGE.findall(badge_area):
        name = name.strip()

        if name and "•" not in name:
            badges.setdefault(name, state.lower() == "active")

    details = {}
    details_area = main[first_details:first_details + 4000] if first_details >= 0 else ""

    for label, value in _DETAIL.findall(details_area):
        label, value = html_to_text(label), html_to_text(value)

        if label and value and "•" not in value:
            details.setdefault(label, value)

    return {
        "excerpt": html_to_text(excerpt.group(1)) if excerpt else "",
        "original_url": (original.group(1) or original.group(2)) if original else None,
        "badges": badges,
        "details": details,
        "summary": summary_sections(main),
    }


def source_hint_from(badges: dict):
    if badges.get("Visa Sponsorship"):
        return "visa"

    if badges.get("Relocation"):
        return "relocation"

    # Listed on the visa list without a readable badge: still a visa job.
    return None if badges else "visa"


_LINKEDIN_DESCRIPTION = re.compile(
    r'<div[^>]*class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)


def linkedin_description(page: str) -> str:
    """The description on a public LinkedIn job page (as JobSpy reads it)."""

    match = _LINKEDIN_DESCRIPTION.search(page or "")
    return html_to_text(match.group(1)) if match else ""


def title_from_slug(slug: str) -> str:
    return slug.replace("-", " ")


class JaabzSource:

    name = "jaabz"

    def __init__(self, countries, max_pages=2, known_ids=(), get=None, sleep=time.sleep,
                 delay=(1.0, 2.5), open_originals=True):
        """
        countries: [(jaabz slug, country name), ...], e.g. [("qatar", "Qatar")]
        open_originals: also read the original posting (LinkedIn...) for
        the full description; Jaabz itself shows only an excerpt.
        """
        self.open_originals = open_originals
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

    def _original_description(self, url) -> str:
        """
        The full description from the original posting: LinkedIn's public
        job page, or any page with a JobPosting. "" when unreachable
        (LinkedIn may refuse: the excerpt is kept then).
        """

        if not url or not self.open_originals:
            return ""

        linkedin = LINKEDIN_JOB.search(url)
        target = f"https://www.linkedin.com/jobs/view/{linkedin.group(1)}" if linkedin else url

        self.sleep(random.uniform(*self.delay))

        try:
            page = get_html(target, get=self.get, sleep=self.sleep, retries=0)
        except FetchError:
            self.stats["originals_refused"] = self.stats.get("originals_refused", 0) + 1
            return ""

        if linkedin:
            return linkedin_description(page)

        return parse_job_page(page).get("description") or ""

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

            # Only the excerpt box: the rest of the page is Jaabz's own
            # text ("Explore our directory of visa sponsorship jobs...").
            details = read_job_page(page)
            description = details["excerpt"] or job["description"]

            # The full ad, from the original posting when it is reachable.
            full = self._original_description(details["original_url"])

            if len(full) > len(description):
                description = full
                self.stats["full_text"] = self.stats.get("full_text", 0) + 1

            # Jaabz's summary boxes hold what the excerpt often lacks: years
            # asked, skills, benefits (visa, relocation).
            if details["summary"]:
                description = description + "\n\nSummary on Jaabz:\n" + details["summary"]

            facts = [f"{label}: {value}" for label, value in details["details"].items()]

            if facts:
                description = description + "\n" + "\n".join(facts)

            rows.append({
                "id": f"jz-{number}",
                "site": "jaabz",
                "job_url": url,
                **job,
                "job_url_direct": details["original_url"],
                "description": description,
                "title": job["title"] or title_from_slug(slug).title(),
                # The list was filtered by country: use it when the page
                # does not say where the job is.
                "location": job["location"] or country_of.get(number),
                "search_term": "jaabz",
                "source_hint": source_hint_from(details["badges"]),
            })

        return pd.DataFrame(rows)