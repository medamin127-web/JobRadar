import pandas as pd

from models import Job
from services import (
    JobNormalizer,
    JobAnalyzer,
    ExperienceAnalyzer,
)
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
# INITIALIZE
# ==================================================

source = JobSpySource(
    sites=["linkedin"]
)

normalizer = JobNormalizer()
analyzer = JobAnalyzer()
experience_analyzer = ExperienceAnalyzer()


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

        print(
            f"Found {len(jobs)} jobs"
        )

        all_jobs.append(jobs)


# ==================================================
# 2. COMBINE RAW RESULTS
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
# 4. NORMALIZE
# ==================================================

job_objects = normalizer.normalize_dataframe(
    jobs
)



print(
    f"Normalized jobs: {len(job_objects)}"
)

# ==================================================
# 4.5. ANALYZE JOBS
# ==================================================

for job in job_objects:
    analyzer.analyze(job)
    experience_analyzer.analyze(job)

# ==================================================
# 5. CONVERT NORMALIZED JOBS TO DATAFRAME
# ==================================================

if job_objects:

    jobs_clean = pd.DataFrame(
        [
            job.to_dict()
            for job in job_objects
        ]
    )

else:

    jobs_clean = pd.DataFrame()


# ==================================================
# 6. SAVE
# ==================================================

jobs_clean.to_csv(
    "jobs.csv",
    index=False
)


# ==================================================
# 7. DISPLAY RESULTS
# ==================================================

print(
    "\nJobRadar dataset:\n"
)


if job_objects:

   for job in job_objects:

    print(f"\n{job.title}")
    print(f"Company: {job.company}")
    print(f"Location: {job.location}")

    print(
        f"Skills: "
        f"{', '.join(job.skills) if job.skills else 'None'}"
    )

    print(
        f"Experience: "
        f"{job.experience_min_years}"
        f"{'+' if job.experience_min_years and not job.experience_max_years else ''}"
        f"{' - ' + str(job.experience_max_years) if job.experience_max_years else ''} years"
    )

    print(
        f"Seniority: "
        f"{job.seniority or 'None'}"
    )

else:

    print(
        "No jobs found."
    )


# ==================================================
# 8. FINAL INFORMATION
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