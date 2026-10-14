"""
Re-run the eligibility layer on an existing jobs CSV WITHOUT scraping.

Useful after you change candidate_profile.py (for example after changing
your German level) or after improving the analyzers:

    python rescore_csv.py                          # data/output/jobs.csv
    python rescore_csv.py data/output/jobs.csv out.csv

Technical scores (match_score, target_category...) are taken from the CSV
as they are. Only the eligibility fields and application buckets are
recomputed.
"""

import dataclasses
import os
import sys

import pandas as pd

from config import OUTPUT_DIR, OUTPUT_FILE
from models import Job
from pipeline import order_columns
from scraper import load_profile
from services.eligibility_analyzer import EligibilityAnalyzer
from services.eligibility_evaluator import (
    BUCKET_ORDER,
    ApplicationBucketer,
    EligibilityEvaluator,
)

LIST_COLUMNS = {
    "skills",
    "matched_skills",
    "missing_skills",
    "unknown_match_dimensions",
    "eligibility_blockers",
    "eligibility_warnings",
    "eligibility_positives",
}


def main() -> None:
    profile = load_profile()

    source = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    )
    target = (
        sys.argv[2]
        if len(sys.argv) > 2
        else os.path.join(OUTPUT_DIR, "jobs_rescored.csv")
    )

    frame = pd.read_csv(source, encoding="utf-8-sig")
    job_fields = {f.name for f in dataclasses.fields(Job)}

    jobs = []

    for row in frame.to_dict("records"):
        values = {
            key: (None if pd.isna(value) else value)
            for key, value in row.items()
            if key in job_fields and key not in LIST_COLUMNS
        }

        job = Job(**values)

        EligibilityAnalyzer.analyze(job)
        EligibilityEvaluator.evaluate(job, profile)
        ApplicationBucketer.assign(job)

        # Keep the original list columns for the CSV.
        job.skills = row.get("skills")
        job.matched_skills = row.get("matched_skills")
        job.missing_skills = row.get("missing_skills")

        jobs.append(job)

    jobs.sort(
        key=lambda j: (
            BUCKET_ORDER.get(j.application_bucket, 9),
            -(j.ranking_score or 0),
        )
    )

    result = order_columns(pd.DataFrame([j.to_dict() for j in jobs]))
    result.to_csv(target, index=False, encoding="utf-8-sig")

    print(f"Rescored {len(jobs)} jobs -> {target}\n")
    print(result["application_bucket"].value_counts().to_string())
    print()

    for job in jobs:
        if job.application_bucket in ("apply_now", "apply_with_research"):
            print(
                f"[{job.application_bucket}] {job.match_score:.0f} | "
                f"{job.title} | {job.company} | {job.location}\n"
                f"    {job.bucket_reason}\n"
                f"    warnings: {', '.join(job.eligibility_warnings) or '-'}"
            )


if __name__ == "__main__":
    main()
