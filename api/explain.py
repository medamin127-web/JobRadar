"""
JobRadar's internal codes (eligibility_evaluator.py) in plain words, for
the dashboard. "Blocked: NATIONALS_ONLY" becomes "Only for citizens of
that country".
"""

import re

TEXT = {
    # Visa
    "NO_VISA_SPONSORSHIP": "The ad says they do not sponsor visas",
    "SAYS_NO_VISA_SPONSORSHIP": "The ad says no visa sponsorship (you would work from Tunisia, so this may not matter)",
    "VISA_STATEMENTS_CONFLICT": "The ad says different things about visas",
    "VISA_SPONSORSHIP_OFFERED": "The ad offers visa sponsorship",
    "VISA_SPONSORSHIP_POSSIBLE": "The ad says a visa may be possible",
    "WORK_AUTHORIZATION_REQUIRED": "You must already be allowed to work there",
    "WORK_AUTHORIZATION_ALSO_MENTIONED": "Offers a visa but also mentions needing a work permit",
    "RELOCATION_SUPPORT": "Helps with relocation",
    "BOARD_LISTS_IT_AS_VISA_SPONSORED": "The job board lists it as visa sponsored",
    "BOARD_LISTS_IT_WITH_RELOCATION": "The job board lists it with relocation help",
    "EMPLOYER_VISA_IS_THE_NORM_THERE": "Employers there normally arrange the work visa",
    "ON_OFFICIAL_SPONSOR_REGISTER": "On the government's list of visa sponsors",
    "NOT_FOUND_ON_SPONSOR_REGISTER": "Not found on the government's list of visa sponsors (may be under another name)",
    "SAYS_SPONSOR_BUT_NOT_ON_REGISTER": "Offers a visa but is not on the government's list of sponsors",
    # Local hiring
    "NATIONALS_ONLY": "Only for citizens of that country",
    "LOCAL_CANDIDATES_ONLY": "Only for people already living there",
    "LOCAL_CANDIDATES_PREFERRED": "Prefers people already living there",
    "LOCAL_CANDIDATES_MENTIONED": "Offers a visa but also mentions local candidates",
    # Remote
    "REMOTE_WORLDWIDE": "Remote from anywhere",
    "REMOTE_EMEA": "Remote within Europe, the Middle East and Africa",
    "REMOTE_LIMITED_COUNTRIES": "Remote, but only from some countries",
    "REMOTE_REGION_RESTRICTED": "Remote only from inside one country or the EU",
    "REMOTE_SCOPE_UNCLEAR": "Remote, but it is unclear from where",
    "REMOTE_OPEN_TO_TUNISIA": "Hires people living in Tunisia",
    "REMOTE_NOT_OPEN_TO_TUNISIA": "Does not hire people living in Tunisia",
    "REMOTE_EUROPE_ONLY": "Remote from Europe only (usually means living in the EU)",
    "REMOTE_REGION_UNCLEAR": "Unclear which countries they hire in",
    # German
    "GERMAN_LEVEL_TOO_HIGH": "Needs more German than you have",
    "GERMAN_LEVEL_STRETCH": "Asks for a bit more German than you have",
    "GERMAN_LEVEL_OK": "Your German is enough",
    "GERMAN_LEVEL_UNVERIFIED": "German is mentioned without a level",
    "GERMAN_AD_NO_LEVEL_STATED": "The ad is in German but states no level",
    "GERMAN_NOT_REQUIRED": "German is not required",
    # Other signals
    "INTERNATIONAL_FRIENDLY": "Welcomes international applicants",
    "ENGLISH_WORKING_LANGUAGE": "English is the working language",
    "SALARY_ABOVE_JUNIOR_RANGE": "The salary suggests a more senior role",
}

LANGUAGE_CODES = [
    (re.compile(r"^([A-Z]+)_REQUIRED_YOU_HAVE_IT$"), "Asks for {lang}, which you have"),
    (re.compile(r"^([A-Z]+)_IS_A_PLUS_YOU_HAVE_IT$"), "{lang} is a plus, and you have it"),
    (re.compile(r"^([A-Z]+)_NOT_REQUIRED$"), "{lang} is not required"),
    (re.compile(r"^([A-Z]+)_LEVEL_STRETCH$"), "Asks for a bit more {lang} than you have"),
    (re.compile(r"^([A-Z]+)_REQUIRED$"), "Needs {lang}, which you do not speak well enough"),
]


def code_text(code: str) -> str:
    if code in TEXT:
        return TEXT[code]

    for pattern, text in LANGUAGE_CODES:
        match = pattern.match(code)

        if match:
            return text.format(lang=match.group(1).capitalize())

    return code.replace("_", " ").capitalize()


def codes_text(codes) -> list:
    return [code_text(code) for code in codes or []]


_CODE = re.compile(r"\b[A-Z][A-Z_]{4,}\b")


def reason_text(reason) -> str | None:
    """'Blocked: NATIONALS_ONLY, X' -> 'Blocked: Only for citizens of that country; ...'"""

    if not reason:
        return reason

    if reason.startswith("Blocked: "):
        codes = [c.strip() for c in reason[len("Blocked: "):].split(",") if c.strip()]
        return "Blocked: " + "; ".join(code_text(c) for c in codes) + "."

    return _CODE.sub(lambda m: code_text(m.group(0)), reason)