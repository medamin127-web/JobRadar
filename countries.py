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
    skip_locations     places in that country you do not want (French-speaking
                       Québec and Romandy): jobs there are skipped, with the
                       reason in skip_reason
    remote_search      search with LinkedIn's "remote" filter (the "remote" profile)
    boards             the country's own job boards (listed_boards.py), read
                       when the country is searched
    adzuna             Adzuna's country code (adzuna.py; needs a free key)
    visa_norm          "explicit": silence about visas means probably no
                       (Germany, most of Europe)
                       "employer_sponsored": the employer normally arranges
                       the work visa (Gulf); silence is a cautious maybe
                       "remote": no visa; the question is whether the
                       employer hires people living in Tunisia
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
        "adzuna": "de",
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
        "adzuna": "nl",
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
        "adzuna": "gb",
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

    "austria": {
        "name": "Austria",
        "adzuna": "at",
        "jaabz": "austria",
        "location": "Austria",
        "indeed_country": "austria",
        "sites": ["linkedin", "indeed"],
        "local_language": "German",
        "visa_norm": "explicit",
        # Software developers are on Austria's nationwide shortage list
        # (Red-White-Red Card for skilled workers in shortage occupations).
        "location_keywords": [
            "austria", "österreich", "osterreich", "vienna", "wien", "graz",
            "linz", "salzburg", "innsbruck", "klagenfurt", "villach", "wels",
            "st. pölten", "sankt pölten", "dornbirn", "hagenberg", "leonding",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer Red-White-Red Card",
            "Software Engineer relocation",
        ],
    },

    "switzerland": {
        "name": "Switzerland",
        "adzuna": "ch",
        "jaabz": "switzerland",
        "location": "Switzerland",
        "indeed_country": "switzerland",
        "sites": ["linkedin", "indeed"],
        "local_language": "German",
        "visa_norm": "explicit",
        # Non-EU hires need a cantonal quota permit and proof that no Swiss
        # or EU candidate was found: rare for juniors, so be sceptical.
        "location_keywords": [
            "switzerland", "schweiz", "suisse", "svizzera", "zurich", "zürich",
            "basel", "bern", "berne", "zug", "lucerne", "luzern", "winterthur",
            "st. gallen", "st gallen", "baar", "aarau", "schaffhausen", "chur",
            "geneva", "genève", "geneve", "lausanne", "lugano",
        ],
        # French- and Italian-speaking regions.
        "skip_locations": [
            "geneva", "genève", "geneve", "lausanne", "neuchâtel", "neuchatel",
            "fribourg", "sion", "yverdon", "montreux", "nyon", "vevey",
            "lugano", "bellinzona", "locarno", "romandie", "ticino",
        ],
        "skip_reason": "French/Italian-speaking part of Switzerland.",
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer visa sponsorship",
        ],
    },

    "malta": {
        "name": "Malta",
        "jaabz": "malta",
        "location": "Malta",
        "indeed_country": "malta",
        "sites": ["linkedin"],           # Indeed found nothing here (Oct 2026)
        # English is an official language; Maltese is almost never asked.
        "local_language": "English",
        "visa_norm": "explicit",
        "location_keywords": [
            "malta", "valletta", "sliema", "st julian's", "st. julian's",
            "saint julian's", "san giljan", "gzira", "msida", "birkirkara",
            "mriehel", "san gwann", "swieqi", "ta' xbiex", "qormi", "mosta",
            "pieta", "floriana", "gozo",
        ],
        # Online gaming (iGaming) and fintech are the big tech employers.
        "search_terms": BASE_TERMS + [
            "Software Developer iGaming",
            "Software Engineer visa sponsorship",
        ],
    },

    "poland": {
        "name": "Poland",
        "boards": ["justjoinit", "nofluffjobs"],
        "adzuna": "pl",
        "jaabz": "poland",
        "location": "Poland",
        "indeed_country": "poland",
        "sites": ["linkedin", "indeed"],
        "local_language": "Polish",
        "visa_norm": "explicit",
        "location_keywords": [
            "poland", "polska", "warsaw", "warszawa", "krakow", "kraków",
            "cracow", "wroclaw", "wrocław", "gdansk", "gdańsk", "gdynia",
            "sopot", "poznan", "poznań", "lodz", "łódź", "katowice",
            "szczecin", "lublin", "bialystok", "białystok", "rzeszow",
            "rzeszów", "bydgoszcz", "torun", "toruń", "gliwice",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer relocation",
        ],
    },

    "czechia": {
        "name": "Czechia",
        "jaabz": "czech-republic",
        "location": "Czechia",
        "indeed_country": "czech republic",
        "sites": ["linkedin", "indeed"],
        "local_language": "Czech",
        "visa_norm": "explicit",
        # Most non-EU hires come on the Employee Card; the EU Blue Card
        # needs a higher salary.
        "location_keywords": [
            "czechia", "czech republic", "česko", "česká republika", "prague",
            "praha", "brno", "ostrava", "plzen", "plzeň", "olomouc", "liberec",
            "hradec kralove", "hradec králové", "pardubice", "zlin", "zlín",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer relocation",
        ],
    },

    # Ready, not in COUNTRIES: work permits for non-EU workers were frozen for
    # months in 2026 and IT employers rarely use them.
    "romania": {
        "name": "Romania",
        "jaabz": "romania",
        "location": "Romania",
        "indeed_country": "romania",
        "sites": ["linkedin", "indeed"],
        "local_language": "Romanian",
        "visa_norm": "explicit",
        "location_keywords": [
            "romania", "românia", "bucharest", "bucurești", "bucuresti",
            "cluj-napoca", "cluj", "iasi", "iași", "timisoara", "timișoara",
            "brasov", "brașov", "sibiu", "oradea", "constanta", "constanța",
            "craiova",
        ],
        "search_terms": BASE_TERMS + ["Software Engineer relocation"],
    },

    "estonia": {
        "name": "Estonia",
        "jaabz": "estonia",
        "location": "Estonia",
        "indeed_country": "estonia",
        "sites": ["linkedin"],           # Indeed found nothing here (Oct 2026)
        "local_language": "Estonian",
        "visa_norm": "explicit",
        "location_keywords": ["estonia", "eesti", "tallinn", "tartu", "pärnu", "parnu", "narva"],
        "search_terms": BASE_TERMS + ["Software Engineer relocation"],
    },

    "lithuania": {
        "name": "Lithuania",
        "jaabz": "lithuania",
        "location": "Lithuania",
        "indeed_country": "lithuania",
        "sites": ["linkedin"],           # Indeed found nothing here (Oct 2026)
        "local_language": "Lithuanian",
        "visa_norm": "explicit",
        "location_keywords": [
            "lithuania", "lietuva", "vilnius", "kaunas", "klaipeda", "klaipėda",
            "siauliai", "šiauliai", "panevezys", "panevėžys",
        ],
        "search_terms": BASE_TERMS + ["Software Engineer relocation"],
    },

    "sweden": {
        "name": "Sweden",
        "jaabz": "sweden",
        "location": "Sweden",
        "indeed_country": "sweden",
        "sites": ["linkedin", "indeed"],
        "local_language": "Swedish",
        "visa_norm": "explicit",
        "location_keywords": [
            "sweden", "sverige", "stockholm", "gothenburg", "göteborg", "goteborg",
            "malmö", "malmo", "uppsala", "linköping", "linkoping", "lund",
            "västerås", "vasteras", "örebro", "orebro", "umeå", "umea",
            "helsingborg", "jönköping", "jonkoping", "norrköping", "karlskrona",
            "solna", "kista",
        ],
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer relocation",
        ],
    },

    # ------------------------------------------------------------ Asia

    "japan": {
        "name": "Japan",
        "boards": ["tokyodev", "japandev"],
        "jaabz": "japan",
        "location": "Japan",
        "indeed_country": "japan",
        "sites": ["linkedin", "indeed"],
        "local_language": "Japanese",
        "visa_norm": "explicit",
        # English searches find the English-speaking teams; ads written in
        # Japanese or asking for JLPT N1/N2 are marked as needing Japanese.
        "location_keywords": [
            "japan", "tokyo", "osaka", "kyoto", "yokohama", "fukuoka", "nagoya",
            "sapporo", "kobe", "sendai", "shibuya", "shinjuku", "minato",
            "chiyoda", "shinagawa", "roppongi", "meguro",
        ],
        "search_terms": BASE_TERMS + [
            "Software Engineer English",
            "Frontend Engineer",
            "Software Engineer visa sponsorship",
        ],
    },

    # ------------------------------------------------------------ North America

    "canada": {
        "name": "Canada",
        "adzuna": "ca",
        "jaabz": "canada",
        "location": "Canada",
        "indeed_country": "canada",
        "sites": ["linkedin", "indeed"],
        "local_language": "French",
        "visa_norm": "explicit",
        # Employers rarely sponsor juniors from abroad (LMIA work permit);
        # trust only ads that say they sponsor.
        "location_keywords": [
            "canada", "toronto", "vancouver", "ottawa", "calgary", "edmonton",
            "waterloo", "kitchener", "mississauga", "markham", "burnaby",
            "winnipeg", "halifax", "victoria", "hamilton", "london, on",
            "regina", "saskatoon", "surrey", "richmond hill", "oakville",
            "montreal", "montréal", "quebec city", "laval", "gatineau",
        ],
        # French-speaking Québec.
        "skip_locations": [
            "montreal", "montréal", "quebec", "québec", "laval", "gatineau",
            "sherbrooke", "longueuil", "trois-rivières", ", qc",
        ],
        "skip_reason": "Québec (French-speaking).",
        "search_terms": BASE_TERMS + [
            "Full Stack Engineer",
            "Software Engineer visa sponsorship",
            "Software Developer LMIA",
        ],
    },

    # ------------------------------------------------------------ Remote

    # Not a country: jobs you would do from home in Tunisia. Found by a
    # LinkedIn search of remote jobs in EMEA and by the remote job boards
    # (REMOTE_BOARDS in config.py). No visa needed, but the employer must
    # hire people in Tunisia: eligibility_analyzer.py reads the job's
    # region ("Anywhere", "EMEA" yes; "USA only", "UK only" no).
    "remote": {
        "name": "Remote (from Tunisia)",
        "location": "EMEA",
        "remote_search": True,           # LinkedIn's "remote" filter
        "indeed_country": None,
        "sites": ["linkedin"],
        "local_language": "English",
        "visa_norm": "remote",
        "location_keywords": [],
        "search_terms": BASE_TERMS + [
            "React Developer",
            "Frontend Developer",
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

    # Smaller Gulf markets.

    "kuwait": {
        "name": "Kuwait",
        "jaabz": "kuwait",
        "location": "Kuwait",
        "indeed_country": "kuwait",
        "sites": ["linkedin", "indeed", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": ["kuwait", "kuwait city", "hawalli", "salmiya", "farwaniya", "ahmadi"],
        "search_terms": GULF_TERMS,
    },

    "oman": {
        "name": "Oman",
        "jaabz": "oman",
        "location": "Oman",
        "indeed_country": "oman",
        "sites": ["linkedin", "indeed", "bayt"],
        "local_language": "Arabic",
        "visa_norm": "employer_sponsored",
        "location_keywords": ["oman", "muscat", "sohar", "salalah", "nizwa", "duqm", "seeb"],
        "search_terms": GULF_TERMS,
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


def skipped_location(location, key):
    """The skip reason when the location is in a region you do not want."""

    import re

    from sources.relevance import has_keyword

    profile = profile_of(key) or {}
    places = profile.get("skip_locations") or []
    text = str(location or "")

    # ", qc": a region code after a comma ("Laval, QC, Canada").
    codes = [p.lstrip(", ") for p in places if p.startswith(",")]
    names = [p for p in places if not p.startswith(",")]

    if any(re.search(r",\s*" + re.escape(code) + r"\b", text, re.IGNORECASE) for code in codes) \
            or has_keyword(text, names):
        return profile.get("skip_reason")

    return None


def profile_of(key):
    return COUNTRY_PROFILES.get(key or "")