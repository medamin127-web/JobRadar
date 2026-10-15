"""
JobRadar settings: what to search, where, and where files go.

Edit this file to change searches. Nothing here runs anything.
"""

# ==================================================
# SEARCHES
# ==================================================

SEARCH_CONFIGS = [
    {
        "location": "Germany",
        "search_terms": [
            "Full Stack Developer",
            "Full Stack Engineer",
            "Software Engineer",
            "Web Developer",

            # Targeted searches for international applicants
            "Software Engineer visa sponsorship",
            "Developer visa sponsorship",
            "Software Engineer relocation",
            "Developer relocation Germany",
            "Software Engineer EU Blue Card",
        ],
    },

    # Later:
    #
    # {
    #     "location": "Netherlands",
    #     "search_terms": [
    #         "Full Stack Developer",
    #         "Full Stack Engineer",
    #         "Software Engineer",
    #         "Web Developer",
    #     ],
    # },
]

# Job sites that JobSpy should query.
SITES = ["linkedin"]

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