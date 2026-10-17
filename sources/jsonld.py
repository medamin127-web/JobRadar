"""
Read a job page's schema.org JobPosting (the JSON block job sites add so
Google Jobs can list them), with simple HTML fallbacks.

Most job boards without an API still have this block on every job page,
which is far more stable than their HTML layout.
"""

import html
import json
import re

from .text import html_to_text

_SCRIPT = re.compile(
    r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_META = re.compile(
    r"<meta[^>]+(?:property|name)=[\"'](og:title|og:description|description)[\"'][^>]*>",
    re.IGNORECASE,
)
_CONTENT = re.compile(r"content=[\"'](.*?)[\"']", re.IGNORECASE | re.DOTALL)


def _postings(data):
    """Every JobPosting object inside a JSON-LD value (lists, @graph...)."""

    if isinstance(data, list):
        for item in data:
            yield from _postings(item)
    elif isinstance(data, dict):
        kind = data.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]

        if "JobPosting" in kinds:
            yield data

        if "@graph" in data:
            yield from _postings(data["@graph"])


def find_job_posting(page: str):
    """The first JobPosting dict on the page, or None."""

    for block in _SCRIPT.findall(page or ""):
        try:
            data = json.loads(block.strip())
        except ValueError:
            # Some sites leave raw line breaks inside strings.
            try:
                data = json.loads(re.sub(r"[\r\n\t]+", " ", block.strip()))
            except ValueError:
                continue

        for posting in _postings(data):
            return posting

    return None


def _name(value):
    if isinstance(value, dict):
        return value.get("name")

    if isinstance(value, list) and value:
        return _name(value[0])

    return value if isinstance(value, str) else None


def _location(posting) -> str:
    places = posting.get("jobLocation") or []

    if isinstance(places, dict):
        places = [places]

    names = []

    for place in places:
        address = place.get("address") if isinstance(place, dict) else None

        if isinstance(address, str):
            names.append(address)
            continue

        if not isinstance(address, dict):
            continue

        parts = [
            address.get("addressLocality"),
            address.get("addressRegion"),
            _name(address.get("addressCountry")),
        ]
        text = ", ".join(dict.fromkeys(p.strip() for p in parts if isinstance(p, str) and p.strip()))

        if text:
            names.append(text)

    if not names:
        countries = posting.get("applicantLocationRequirements") or []
        countries = countries if isinstance(countries, list) else [countries]
        names = [n for n in (_name(c) for c in countries) if n]

    return " | ".join(dict.fromkeys(names))


_NOISE_BLOCKS = re.compile(
    r"<(script|style|noscript|svg|nav|header|footer|form)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_H1_START = re.compile(r"<h1[^>]*>", re.IGNORECASE)


# Where the job ends and the site's suggestions begin.
_TAIL = re.compile(
    r"^(?:these jobs may fit you|similar jobs|related jobs|more jobs|you may also like"
    r"|jobseeker login|recommended jobs|other jobs)\b",
    re.IGNORECASE | re.MULTILINE,
)


def page_text(page: str, limit: int = 12000) -> str:
    """
    The readable text of a job page without menus, scripts, footers and
    "similar jobs", starting at its main title (<h1>) when there is one.
    """

    page = _NOISE_BLOCKS.sub(" ", page or "")
    start = _H1_START.search(page)

    if start:
        page = page[start.start():]

    text = html_to_text(page)
    tail = _TAIL.search(text)

    if tail:
        text = text[: tail.start()]

    text = remove_site_promotion(text)

    return text.strip()[:limit]


# Job boards' own sales lines, which look like the employer offering a visa:
#   "Searching for Development & Programming roles that provide visa sponsorship?"
#   "Looking to advance your Product Management career with relocation support?"
SITE_PROMOTION = re.compile(
    r"^(?:searching for|looking for|interested in)\b.{0,80}\b(?:roles?|jobs?|positions?|opportunities)\b.{0,40}"
    r"(?:visa|relocation|sponsor)"
    r"|^looking to (?:advance|grow|boost|take)\b.{0,80}\bcareer\b"
    r"|^(?:explore|discover|browse|find|search|check out|see)\b.{0,60}\b(?:jobs|roles|positions|openings|listings|directory)\b"
    # A sentence about "visa sponsorship jobs" / "relocation jobs" describes
    # the board's listings, never one employer's offer.
    r"|\b(?:visa[- ]sponsorship|visa[- ]sponsored|relocation|sponsored)\s+(?:jobs|roles|positions|opportunities)\b"
    r"|\bjobs\s+(?:with|offering|that (?:offer|provide))\s+(?:visa|relocation)"
    r"|\bemployers?\s+(?:worldwide|around the world|who are ready to sponsor)"
    r"|jaabz|^(?:sign up|log ?in|unlock job details|apply now|share this job)\b",
    re.IGNORECASE,
)


def remove_site_promotion(text: str) -> str:
    """
    Cut the board's promotion. When it starts in the second half of the
    page, everything from there on is the board's (FAQ, guides...); when
    it sits before the job, only its own lines are dropped.
    """

    lines = text.splitlines()
    total = sum(len(line) + 1 for line in lines) or 1
    kept = []
    seen = 0

    for line in lines:
        if SITE_PROMOTION.search(line.strip()):
            if seen > total * 0.5:
                break
            seen += len(line) + 1
            continue

        kept.append(line)
        seen += len(line) + 1

    return "\n".join(kept)


# Below this many characters a JobPosting description is only a summary
# (Jaabz): the page text is used when it says more.
SHORT_DESCRIPTION = 1000


def best_description(job: dict, page: str) -> str:
    description = job.get("description") or ""

    if len(description) >= SHORT_DESCRIPTION:
        return description

    text = page_text(page)

    return text if len(text) > len(description) else description


def parse_job_page(page: str) -> dict:
    """
    -> {title, company, location, date_posted, is_remote, job_type,
        description, structured}   (structured: a JobPosting was found)
    """

    posting = find_job_posting(page)

    if posting:
        remote = str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE"
        job_type = posting.get("employmentType")

        if isinstance(job_type, list):
            job_type = ", ".join(str(t) for t in job_type)

        return {
            "title": html.unescape(str(posting.get("title") or "")).strip() or None,
            "company": _name(posting.get("hiringOrganization")),
            "location": _location(posting) or None,
            "date_posted": str(posting.get("datePosted") or "")[:10] or None,
            "is_remote": remote,
            "job_type": job_type,
            "description": html_to_text(posting.get("description")),
            "structured": True,
        }

    # No JobPosting: the page title and its meta description.
    meta = {}

    for tag in _META.finditer(page or ""):
        content = _CONTENT.search(tag.group(0))

        if content:
            meta.setdefault(tag.group(1).lower(), html.unescape(content.group(1)).strip())

    heading = _H1.search(page or "")
    title = html_to_text(heading.group(1)) if heading else meta.get("og:title")

    return {
        "title": title or None,
        "company": None,
        "location": None,
        "date_posted": None,
        "is_remote": False,
        "job_type": None,
        "description": meta.get("og:description") or meta.get("description") or "",
        "structured": False,
    }