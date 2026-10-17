"""
Keep only feed jobs worth analyzing.

LinkedIn and Indeed searches already return relevant jobs. Feeds such as
Arbeitnow or a company's whole career page return everything (HR, sales,
other countries), so we keep tech titles in the target country first.
"""

import re

TECH_TITLE = re.compile(
    r"\bdevelopers?\b|development engineer|software develop|engineer|entwickler"
    r"|programmier|software|full[\s-]?stack|front[\s-]?end|back[\s-]?end"
    r"|\bweb\b|\bdevops\b|\bsre\b|informatiker",
    re.IGNORECASE,
)

NOT_TECH = re.compile(
    r"sales engineer|solutions? engineer|support engineer|field engineer"
    r"|mechanical|electrical|elektro|maschinenbau|civil engineer|bauingenieur"
    r"|verfahrenstechn|process engineer|quality engineer|qualitätsingenieur"
    r"|\bintern\b|internship|praktik|werkstudent|working student|ausbildung"
    r"|business development|sales|representative|recruit|marketing"
    r"|\bmanager\b|\bdirector\b|head of|account executive"
    r"|recipe|value engineer|pre-?sales|customer success"
    r"|planning engineer|site engineer|commissioning|draftsman|draughtsman"
    r"|interior|landscap|timekeeper|\bhvac\b|\bmep\b|surveyor|estimator"
    r"|technician|\bit support\b|helpdesk|help desk|volunteer|vrijwillig",
    re.IGNORECASE,
)

# Sources that return jobs from everywhere (not a search in one country).
FEED_SITES = {"arbeitnow", "greenhouse", "lever", "jaabz", "relocateme"}

# A remote feed job is kept only when its location is just "remote" (or a
# region that includes your countries), not "Remote, Netherlands" or
# "Werken op afstand" (Dutch for working remotely).
GENERIC_REMOTE = re.compile(
    r"^\W*(?:remote|remote job|fully remote|anywhere|worldwide|global"
    r"|europe|eu|emea|remote\W+(?:europe|eu|emea|worldwide|anywhere))\W*$",
    re.IGNORECASE,
)


# Not a paid job at all, whatever the role: skipped even when the title
# says "Web Developer".
UNPAID_TITLE = re.compile(r"volunteer|vrijwillig|ehrenamt|\bunpaid\b", re.IGNORECASE)


def is_unpaid_title(title) -> bool:
    return bool(UNPAID_TITLE.search(title or ""))


def is_tech_title(title) -> bool:
    title = str(title or "")
    return bool(TECH_TITLE.search(title)) and not NOT_TECH.search(title)


def has_keyword(text, keywords) -> bool:
    """
    True when one of the keywords appears in the text as a whole word:
    "Oman" is in "Muscat, Oman" but not in "Romania".
    """

    text = str(text or "").lower()

    return any(
        re.search(r"(?<![a-zäöüß])" + re.escape(keyword.lower()) + r"(?![a-zäöüß])", text)
        for keyword in keywords
    )


# Cities that exist in North America too: "Cambridge, MA", "London, ON",
# "Birmingham, AL" are not the UK.
ELSEWHERE = re.compile(
    r"\b(?:usa|u\.s\.a?|united states|america|canada)\b"
    # US states / Canadian provinces, except codes that are also countries
    # or common words (DE, IN, ID, ME, OR, HI...).
    r"|,\s*(?:al|ak|az|ar|ca|co|ct|fl|ga|il|ia|ks|ky|md|ma|mi|mn|ms"
    r"|mo|mt|nv|nh|nj|nm|ny|nc|nd|oh|ok|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy"
    r"|on|qc|bc|mb|ns|nb)\b(?:\s*,|\s*$)",
    re.IGNORECASE,
)


def in_country(location, keywords) -> bool:
    """True when the location names the country or one of its cities."""

    if ELSEWHERE.search(str(location or "")):
        return False

    return has_keyword(location, keywords)


def in_target_countries(frame, configs):
    """
    Boolean mask: which jobs belong to the countries you search.

    Search sites (LinkedIn, Indeed, Bayt) were searched by country: their
    jobs count when that country is still in your list (older jobs without
    a search_country were Germany searches and always count). Feed jobs
    count when their location names one of your countries/cities, or when
    they are remote.
    """

    import pandas as pd

    if frame.empty:
        return pd.Series([], dtype=bool)

    keywords = [w for config in configs for w in config.get("location_keywords", [])]
    sites = frame["site"] if "site" in frame.columns else pd.Series([""] * len(frame), index=frame.index)
    locations = frame["location"] if "location" in frame.columns else pd.Series([""] * len(frame), index=frame.index)
    remote = (
        frame["is_remote"].map(lambda v: str(v).strip().lower() in ("true", "1"))
        if "is_remote" in frame.columns
        else pd.Series([False] * len(frame), index=frame.index)
    )

    keys = {config.get("key") for config in configs}
    searched = (
        frame["search_country"].map(
            lambda key: not isinstance(key, str) or not key or key in keys
        )
        if "search_country" in frame.columns
        else pd.Series([True] * len(frame), index=frame.index)
    )

    from_feed = sites.isin(FEED_SITES)
    located = locations.map(lambda loc: in_country(loc, keywords))
    generic_remote = remote & locations.map(
        lambda loc: not str(loc or "").strip() or bool(GENERIC_REMOTE.match(str(loc)))
    )

    return (~from_feed & searched) | located | generic_remote