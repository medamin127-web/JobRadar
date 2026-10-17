"""
Country profiles: everything JobRadar knows about searching (and getting
a work visa) in one country.

You choose which countries to search in config.py (COUNTRIES). A profile
here is only used when its key is in that list.

Fields:
    name               shown in the report
    location           what LinkedIn / Indeed / Bayt are searched with
    indeed_country     Indeed's name for the country (None = no Indeed)
    sites              search sites that make sense there (Bayt = Gulf only,
                       Glassdoor = not in the Gulf)
    stepstone          StepStone's site there (optional), stepstone_terms its searches
    sponsor_register   official list of employers allowed to sponsor visas
                       (sponsors.py): "uk" or "nl"
    location_keywords  a feed job (Jaabz, Arbeitnow, career pages) belongs
                       to this country when its location contains one
    local_language     the language employers may ask for
    jaabz              the country's name in Jaabz addresses (?countries=...)
    visa_norm          "explicit": silence about visas means probably no
                       (Germany, most of Europe)
                       "employer_sponsored": the employer normally arranges
                       the work visa (Gulf); silence is a cautious maybe
    search_terms       one search per term and site
"""

# Searched everywhere. A country can add its own terms.
BASE_TERMS = [
    "Full Stack Developer",
    "Software Engineer",
    "Web Developer",
]

GULF_TERMS = BASE_TERMS + [
    "React Developer",
    "Backend Developer",
]

COUNTRY_PROFILES = {

    # ------------------------------------------------------------ Europe

    "germany": {
        "name": "Germany",
        "jaabz": "germany",
        "location": "Germany",
        "indeed_country": "germany",
        "sites": ["linkedin", "indeed", "glassdoor"],
        # StepStone's site for this country, and what to search there.
        "stepstone": "www.stepstone.de",
        "stepstone_terms": [
            "Full Stack Developer", "Software Engineer", "Web Developer",
            "React Developer", "Backend Developer",
        ],
        "local_language": "German",
        "visa_norm": "explicit",
        "location_keywords": [
            "germany", "deutschland", "berlin", "munich", "münchen", "hamburg",
            "cologne", "köln", "frankfurt", "düsseldorf", "dusseldorf",
            "stuttgart", "leipzig", "dresden", "hannover", "hanover",
            "nuremberg", "nürnberg", "bremen", "essen", "dortmund", "bonn",
            "karlsruhe", "mannheim", "heidelberg", "potsdam", "aachen",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer visa sponsorship",
            "Developer visa sponsorship",
            "Software Engineer relocation",
            "Developer relocation Germany",
            "Software Engineer EU Blue Card",
        ],
    },

    "netherlands": {
        "name": "Netherlands",
        "jaabz": "netherlands",
        "location": "Netherlands",
        "indeed_country": "netherlands",
        "sites": ["linkedin", "indeed"],
        "local_language": "Dutch",
        "visa_norm": "explicit",
        # Highly skilled migrant permits go through IND recognised sponsors.
        "sponsor_register": "nl",
        "location_keywords": [
            "netherlands", "nederland", "the netherlands", "holland", "amsterdam",
            "rotterdam", "utrecht", "the hague", "den haag", "'s-gravenhage",
            "eindhoven", "delft", "leiden", "groningen", "haarlem", "amersfoort",
            "arnhem", "nijmegen", "tilburg", "breda", "maastricht", "zwolle",
            "enschede", "almere", "hilversum", "schiphol", "amstelveen",
            "hoofddorp", "den bosch", "'s-hertogenbosch", "noord-holland",
            "zuid-holland", "noord-brabant",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer visa sponsorship",
            "Developer highly skilled migrant",
        ],
    },

    "ireland": {
        "name": "Ireland",
        "jaabz": "ireland",
        "location": "Ireland",
        "indeed_country": "ireland",
        "sites": ["linkedin", "indeed"],
        "local_language": "English",
        "visa_norm": "explicit",
        "location_keywords": [
            "ireland", "dublin", "cork", "galway", "limerick", "waterford",
            "athlone", "kilkenny", "sligo", "drogheda", "dundalk", "letterkenny",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer visa sponsorship",
        ],
    },

    "uk": {
        "name": "United Kingdom",
        "jaabz": "united-kingdom",
        "location": "United Kingdom",
        "indeed_country": "uk",
        "sites": ["linkedin", "indeed"],
        "local_language": "English",
        "visa_norm": "explicit",
        # Only licensed sponsors can sponsor a Skilled Worker visa.
        "sponsor_register": "uk",
        "location_keywords": [
            "united kingdom", "uk", "england", "scotland", "wales", "northern ireland",
            "london", "manchester", "birmingham", "edinburgh", "glasgow", "leeds",
            "bristol", "cambridge", "oxford", "belfast", "liverpool", "newcastle",
            "sheffield", "nottingham", "brighton", "cardiff", "milton keynes",
            "southampton", "leicester", "coventry", "aberdeen",
            "greater london",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer visa sponsorship",
            "Graduate Software Engineer",
        ],
    },

    # ------------------------------------------------------------ Gulf

    "uae": {
        "name": "United Arab Emirates",
        "jaabz": "united-arab-emirates",
        "location": "United Arab Emirates",
        "indeed_country": "united arab emirates",
        "sites": ["linkedin", "indeed", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": [
            "united arab emirates", "uae", "u.a.e", "dubai", "abu dhabi",
            "sharjah", "ajman", "ras al khaimah", "fujairah", "al ain",
            "umm al quwain",
        ],
        "search_terms": GULF_TERMS,
    },

    "saudi_arabia": {
        "name": "Saudi Arabia",
        "jaabz": "saudi-arabia",
        "location": "Saudi Arabia",
        "indeed_country": "saudi arabia",
        "sites": ["linkedin", "indeed", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": [
            "saudi", "ksa", "riyadh", "jeddah", "jiddah", "dammam", "khobar",
            "dhahran", "mecca", "makkah", "medina", "madinah", "neom",
            "tabuk", "abha", "jubail", "yanbu",
        ],
        "search_terms": GULF_TERMS,
    },

    "qatar": {
        "name": "Qatar",
        "jaabz": "qatar",
        "location": "Qatar",
        "indeed_country": "qatar",
        "sites": ["linkedin", "indeed", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": ["qatar", "doha", "lusail", "al rayyan", "al wakrah"],
        "search_terms": GULF_TERMS,
    },

    # Smaller markets: ready, but not in COUNTRIES by default.

    "kuwait": {
        "name": "Kuwait",
        "jaabz": "kuwait",
        "location": "Kuwait",
        "indeed_country": "kuwait",
        "sites": ["linkedin", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": ["kuwait"],
        "search_terms": BASE_TERMS,
    },

    "oman": {
        "name": "Oman",
        "jaabz": "oman",
        "location": "Oman",
        "indeed_country": "oman",
        "sites": ["linkedin", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": ["oman", "muscat", "sohar", "salalah"],
        "search_terms": BASE_TERMS,
    },

    "bahrain": {
        "name": "Bahrain",
        "jaabz": "bahrain",
        "location": "Bahrain",
        "indeed_country": "bahrain",
        "sites": ["linkedin", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": ["bahrain", "manama"],
        "search_terms": BASE_TERMS,
    },
}


def search_configs(keys, priorities=None):
    """
    The search configs (one per country) for the given profile keys,
    in that order, each with its priority (1 = normal). Unknown keys stop
    the program with a clear message.
    """

    unknown = [key for key in keys if key not in COUNTRY_PROFILES]

    if unknown:
        raise SystemExit(
            f"Unknown country in config.py COUNTRIES: {', '.join(unknown)}\n"
            f"Known: {', '.join(COUNTRY_PROFILES)}"
        )

    priorities = priorities or {}

    return [
        {"key": key, **COUNTRY_PROFILES[key], "priority": priorities.get(key, 1)}
        for key in keys
    ]


def country_of_location(location, configs):
    """The key of the first country whose keywords appear in a location."""

    from sources.relevance import in_country

    for config in configs:
        if in_country(location, config.get("location_keywords", [])):
            return config["key"]

    return None


def profile_of(key):
    return COUNTRY_PROFILES.get(key or "")