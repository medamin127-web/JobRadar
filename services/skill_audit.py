from collections import Counter

from models import Job
from services import JobAnalyzer, JobNormalizer
import pandas as pd


CSV_FILE = "jobs.csv"


# ==================================================
# LOAD DATA
# ==================================================

jobs_df = pd.read_csv(CSV_FILE)

normalizer = JobNormalizer()
analyzer = JobAnalyzer()

jobs = normalizer.normalize_dataframe(jobs_df)


# ==================================================
# ANALYZE JOBS
# ==================================================

for job in jobs:
    analyzer.analyze(job)


# ==================================================
# COUNT SKILLS
# ==================================================

skill_counter = Counter()

for job in jobs:
    if not job.skills:
        continue

    for skill in job.skills:
        skill_counter[skill] += 1


# ==================================================
# DISPLAY RESULTS
# ==================================================

print("\n" + "=" * 60)
print("SKILL FREQUENCY")
print("=" * 60)

for skill, count in skill_counter.most_common():
    percentage = (count / len(jobs)) * 100

    print(
        f"{skill:<20} "
        f"{count:>3} jobs "
        f"({percentage:>5.1f}%)"
    )


# ==================================================
# DISPLAY JOBS WITHOUT SKILLS
# ==================================================

print("\n" + "=" * 60)
print("JOBS WITHOUT EXTRACTED SKILLS")
print("=" * 60)

jobs_without_skills = [
    job
    for job in jobs
    if not job.skills
]

for job in jobs_without_skills:
    print(
        f"- {job.title} | {job.company}"
    )


# ==================================================
# SUMMARY
# ==================================================

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

print(f"Total jobs: {len(jobs)}")
print(f"Unique skills found: {len(skill_counter)}")
print(
    f"Jobs with at least one skill: "
    f"{len(jobs) - len(jobs_without_skills)}"
)
print(
    f"Jobs without skills: "
    f"{len(jobs_without_skills)}"
)

print("\n" + "=" * 60)
print("JOBS WITHOUT EXTRACTED SKILLS — DETAILS")
print("=" * 60)

for job in jobs_without_skills:
    print(f"\nTITLE: {job.title}")
    print(f"COMPANY: {job.company}")
    print("\nDESCRIPTION:")
    print(job.description)