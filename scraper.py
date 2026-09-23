import pandas as pd

from models import Job
from sources import JobSpySource


# ==================================================
# SEARCH CONFIGURATION
# ==================================================

SEARCH_CONFIGS = [
    {
        "location": "Germany",
        "search_terms": [
            "Full Stack Developer",
            "Full Stack Engineer",
            "Software Engineer",
            "Web Developer",
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


RESULTS_PER_SEARCH = 10
HOURS_OLD = 72


# ==================================================
# JOBRADAR FIELDS
# ==================================================

JOB_COLUMNS = [
    "id",
    "site",
    "title",
    "company",
    "location",
    "job_url",
    "job_url_direct",
    "date_posted",
    "job_type",
    "is_remote",
    "work_from_home_type",
    "job_level",
    "job_function",
    "salary_source",
    "interval",
    "min_amount",
    "max_amount",
    "currency",
    "description",
    "skills",
    "experience_range",
    "company_industry",
    "company_url",
    "company_description",
    "search_term",
]


# ==================================================
# INITIALIZE SOURCE
# ==================================================

source = JobSpySource(
    sites=["linkedin"]
)


# ==================================================
# 1. SCRAPE JOBS
# ==================================================

all_jobs = []

for config in SEARCH_CONFIGS:

    location = config["location"]

    search_terms = config["search_terms"]

    print("\n" + "=" * 60)
    print(f"Location: {location}")
    print("=" * 60)

    for search_term in search_terms:

        print(
            f"\nSearching: {search_term} | {location}"
        )

        jobs = source.search(
            search_term=search_term,
            location=location,
            results_wanted=RESULTS_PER_SEARCH,
            hours_old=HOURS_OLD,
        )

        print(f"Found {len(jobs)} jobs")

        all_jobs.append(jobs)


# ==================================================
# 2. COMBINE RESULTS
# ==================================================

if all_jobs:

    jobs = pd.concat(
        all_jobs,
        ignore_index=True
    )

else:

    jobs = pd.DataFrame()


print(
    f"\nTotal jobs collected: {len(jobs)}"
)


# ==================================================
# 3. REMOVE DUPLICATES
# ==================================================

if not jobs.empty and "job_url" in jobs.columns:

    jobs = jobs.drop_duplicates(
        subset=["job_url"]
    )

print(
    f"Unique jobs after deduplication: {len(jobs)}"
)


# ==================================================
# 4. MAKE SURE REQUIRED COLUMNS EXIST
# ==================================================

for column in JOB_COLUMNS:

    if column not in jobs.columns:

        jobs[column] = None


# ==================================================
# 5. KEEP NORMALIZED COLUMNS
# ==================================================

jobs_clean = jobs[
    JOB_COLUMNS
].copy()


# ==================================================
# 6. CONVERT DATAFRAME ROWS INTO JOB OBJECTS
# ==================================================

job_objects = []

for _, row in jobs_clean.iterrows():

    job = Job(
        id=row["id"],
        site=row["site"],

        title=row["title"],
        company=row["company"],
        location=row["location"],

        job_url=row["job_url"],
        job_url_direct=row["job_url_direct"],

        date_posted=row["date_posted"],

        job_type=row["job_type"],
        is_remote=row["is_remote"],
        work_from_home_type=row["work_from_home_type"],

        job_level=row["job_level"],
        job_function=row["job_function"],

        salary_source=row["salary_source"],
        interval=row["interval"],
        min_amount=row["min_amount"],
        max_amount=row["max_amount"],
        currency=row["currency"],

        description=row["description"],
        skills=row["skills"],
        experience_range=row["experience_range"],

        company_industry=row["company_industry"],
        company_url=row["company_url"],
        company_description=row["company_description"],

        search_term=row["search_term"],
    )

    job_objects.append(job)


# ==================================================
# 7. SAVE CSV
# ==================================================

jobs_clean.to_csv(
    "jobs.csv",
    index=False
)


# ==================================================
# 8. DISPLAY RESULTS
# ==================================================

print("\nJobRadar dataset:\n")

if job_objects:

    for job in job_objects:

        print(
            f"{job.title} | "
            f"{job.company} | "
            f"{job.location}"
        )

else:

    print("No jobs found.")


# ==================================================
# 9. FINAL INFORMATION
# ==================================================

print(
    f"\nSaved {len(job_objects)} unique jobs to jobs.csv"
)

print(
    f"Columns: {len(jobs_clean.columns)}"
)

print(
    f"Job objects created: {len(job_objects)}"
)