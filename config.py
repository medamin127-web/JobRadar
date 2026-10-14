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
# FOLDERS (all of data/ and reports/ are git-ignored)
# ==================================================

RAW_DIR = "data/raw"          # raw scrape of every run (description cache)
OUTPUT_DIR = "data/output"    # jobs.csv
REPORTS_DIR = "reports"       # full text report of every run (UTF-8)
OUTPUT_FILE = "jobs.csv"
