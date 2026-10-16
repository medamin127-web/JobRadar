"""
JobRadar settings: what to search, where, and where files go.

Edit this file to change searches. Nothing here runs anything.
"""

# ==================================================
# SEARCHES
# ==================================================

from countries import search_configs

# Countries to search, from the profiles in countries.py. Ready there:
#   germany, uae, saudi_arabia, qatar, kuwait, oman, bahrain
COUNTRIES = ["saudi_arabia", "qatar", "germany", "uae"]

# Countries you prefer. Priority 2 = searched about twice as often as the
# others, and their jobs rank a little higher (+5 points) inside the same
# bucket. Countries not listed have priority 1.
COUNTRY_PRIORITY = {"saudi_arabia": 2, "qatar": 2}

# LinkedIn refuses requests (HTTP 429) when one run makes too many
# searches. So each run searches only this many countries: the ones most
# overdue (time since their last search x their priority). The ranking always shows every country.
# 0 = all countries every run.  Override once with:
#   python scraper.py --countries uae,qatar
COUNTRIES_PER_RUN = 2

SEARCH_CONFIGS = search_configs(COUNTRIES, COUNTRY_PRIORITY)

# ==================================================
# SOURCES
# ==================================================

# Search sites, through JobSpy. A site runs only in the countries whose
# profile lists it (Bayt is Gulf only). Possible: "linkedin", "indeed",
# "bayt", "glassdoor", "google".
SITES = ["linkedin", "indeed", "bayt"]

# Arbeitnow: a German job board with a free API (no search: JobRadar reads
# its newest pages and keeps the tech jobs).
ARBEITNOW_PAGES = 5          # 0 = off

# Company career pages. Add a company's Greenhouse token or Lever name
# (from its careers URL) and check it first with:  python sources_check.py
GREENHOUSE_BOARDS = [         # e.g. ["n26"]
    "n26", "getyourguide", "hellofresh", "celonis", "contentful", "sumup",
    "traderepublic", "raisin", "commercetools", "solarisbank",
]
LEVER_COMPANIES = []         # e.g. ["somecompany"]

# Jaabz (jaabz.com): jobs with visa sponsorship. JobRadar reads its list
# for each of your countries (up to this many pages each, one request per
# new tech job). 0 = off.
JAABZ_PAGES = 2

# Relocate.me: jobs that all come with a relocation package (visa help,
# flight, moving money). Small board, mostly Europe. 0 = off.
RELOCATEME_PAGES = 5

RESULTS_PER_SEARCH = 10
HOURS_OLD = 72

# ==================================================
# BEING GENTLE WITH LINKEDIN (HTTP 429 = "too many requests")
# ==================================================

# Random pause between two searches, in seconds.
DELAY_BETWEEN_SEARCHES = (6, 15)

# When a search is refused: wait this long, then retry it once.
RATE_LIMIT_WAIT_SECONDS = 90

# Stop scraping after this many refused searches in a row and process
# what was collected. Scraping again usually works after a few hours.
STOP_AFTER_RATE_LIMITED = 2

# ==================================================
# FOLDERS (all of data/ and reports/ are git-ignored)
# ==================================================

RAW_DIR = "data/raw"          # raw scrape of every run (description cache)
OUTPUT_DIR = "data/output"    # jobs.csv
REPORTS_DIR = "reports"       # full text report of every run (UTF-8)
OUTPUT_FILE = "jobs.csv"
DB_PATH = "data/jobradar.db"  # every job ever seen + your status for it

# ==================================================
# WHICH SAVED JOBS ARE SHOWN
# ==================================================

# Jobs posted longer ago than this are probably filled or closed: they stay
# in the database but are left out of the ranking.
MAX_JOB_AGE_DAYS = 30

# The printed report lists every job except these buckets (all jobs are
# always in data/output/jobs.csv) ...
REPORT_HIDE_BUCKETS = ("skip",)

# ... and prints full details only for these.
REPORT_DETAIL_BUCKETS = ("apply_now", "apply_with_research", "long_shot")