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
    r"|recipe|value engineer|pre-?sales|customer success",
    re.IGNORECASE,
)

# Sources that return jobs from everywhere (not a search in one country).
FEED_SITES = {"arbeitnow", "greenhouse", "lever"}

# A remote feed job is kept only when its location is just "remote" (or a
# region that includes your countries), not "Remote, Netherlands" or
# "Werken op afstand" (Dutch for working remotely).
GENERIC_REMOTE = re.compile(
    r"^\W*(?:remote|remote job|fully remote|anywhere|worldwide|global"
    r"|europe|eu|emea|remote\W+(?:europe|eu|emea|worldwide|anywhere))\W*$",
    re.IGNORECASE,
)


def is_tech_title(title) -> bool:
    title = str(title or "")
    return bool(TECH_TITLE.search(title)) and not NOT_TECH.search(title)


def in_country(location, keywords) -> bool:
    """True when the location names the country or one of its cities."""

    location = str(location or "").lower()
    return any(keyword.lower() in location for keyword in keywords)


def in_target_countries(frame, configs):
    """
    Boolean mask: which jobs belong to the countries you search.

    Search sites (LinkedIn, Indeed) were already searched by country, so
    their jobs always count. Feed jobs count when their location names one
    of your countries/cities, or when they are remote.
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

    from_feed = sites.isin(FEED_SITES)
    located = locations.map(lambda loc: in_country(loc, keywords))
    generic_remote = remote & locations.map(
        lambda loc: not str(loc or "").strip() or bool(GENERIC_REMOTE.match(str(loc)))
    )

    return ~from_feed | located | generic_remote