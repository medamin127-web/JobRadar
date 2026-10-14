"""
The JobRadar pipeline as plain functions. Importing this file does nothing.

    collect_jobs()  ->  raw DataFrame from a source
    process_jobs()  ->  de-duplicate, normalize, analyze, score, sort
    jobs_to_frame() ->  DataFrame ready for the CSV
"""

import pandas as pd

from services import (
    ExperienceAnalyzer,
    JobAnalyzer,
    JobNormalizer,
)
from services.eligibility_analyzer import EligibilityAnalyzer
from services.eligibility_evaluator import (
    BUCKET_ORDER,
    ApplicationBucketer,
    EligibilityEvaluator,
)
from services.experience_matcher import ExperienceMatcher
from services.match_scorer import MatchScorer
from services.seniority_matcher import SeniorityMatcher
from services.target_classifier import TargetClassifier


CONFIDENCE_RANK = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "very_low": 0,
}

# Columns you read first; the rest follow in their natural order.
FRONT_COLUMNS = [
    "application_bucket",
    "eligibility_status",
    "match_score",
    "ranking_score",
    "title",
    "company",
    "location",
    "bucket_reason",
    "eligibility_blockers",
    "eligibility_warnings",
    "visa_sponsorship_status",
    "relocation_support",
    "german_requirement",
    "german_level_required",
    "work_mode",
    "remote_scope",
    "job_url",
]


def order_columns(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = [c for c in FRONT_COLUMNS if c in frame.columns]
    ordered += [c for c in frame.columns if c not in ordered]

    return frame[ordered]


# ==================================================
# 1. COLLECT
# ==================================================

def collect_jobs(source, configs, results_per_search, hours_old) -> pd.DataFrame:
    """Run every search of every config and return all results together."""

    all_jobs = []

    for config in configs:

        location = config["location"]

        print("\n" + "=" * 60)
        print(f"Location: {location}")
        print("=" * 60)

        for search_term in config["search_terms"]:

            print(f"\nSearching: {search_term} | {location}")

            scraped = source.search(
                search_term=search_term,
                location=location,
                results_wanted=results_per_search,
                hours_old=hours_old,
            )

            print(f"Found {len(scraped)} jobs")

            if not scraped.empty:
                all_jobs.append(scraped)

    jobs = (
        pd.concat(all_jobs, ignore_index=True)
        if all_jobs
        else pd.DataFrame()
    )

    print(f"\nTotal jobs collected: {len(jobs)}")

    return jobs


# ==================================================
# 2. DE-DUPLICATE
# ==================================================

def deduplicate(jobs: pd.DataFrame) -> pd.DataFrame:

    if not jobs.empty and "job_url" in jobs.columns:
        jobs = jobs.drop_duplicates(subset=["job_url"]).reset_index(drop=True)

    # The same posting often appears under several URLs (one per region).
    # Treat same company + title + opening text as one job.
    if not jobs.empty and {"title", "company", "description"} <= set(jobs.columns):

        duplicate_key = (
            jobs["company"].fillna("").str.lower().str.strip()
            + "|"
            + jobs["title"].fillna("").str.lower().str.strip()
            + "|"
            + jobs["description"]
            .fillna("")
            .str.lower()
            .str.replace(r"\s+", " ", regex=True)
            .str[:400]
        )

        jobs = jobs[~duplicate_key.duplicated()].reset_index(drop=True)

    print(f"Unique jobs after deduplication: {len(jobs)}")

    return jobs


# ==================================================
# 3. ANALYZE
# ==================================================

def analyze_jobs(job_objects) -> None:
    """Extract skills, experience, seniority and eligibility signals."""

    analyzer = JobAnalyzer()
    experience_analyzer = ExperienceAnalyzer()

    for job in job_objects:
        analyzer.analyze(job)
        experience_analyzer.analyze(job)
        EligibilityAnalyzer.analyze(job)


# ==================================================
# 4. SCORE
# ==================================================

def score_jobs(job_objects, profile) -> None:
    """Match every job against the candidate profile."""

    for job in job_objects:

        result = MatchScorer.score(job, profile)

        job.match_score = result["overall_score"]
        job.confidence = result["confidence"]
        job.match_coverage = result["coverage"]

        job.role_match_score = result["role_score"]
        job.skills_match_score = result["skills_score"]
        job.experience_match_score = result["experience_score"]
        job.seniority_match_score = result["seniority_score"]

        job.matched_skills = result["matched_skills"]
        job.missing_skills = result["missing_skills"]

        job.unknown_match_dimensions = [
            dimension
            for dimension in ["role", "skills", "experience", "seniority"]
            if result.get(f"{dimension}_score") is None
        ]

        experience_result = ExperienceMatcher.match(job, profile)
        seniority_result = SeniorityMatcher.match(job, profile)

        target = TargetClassifier.classify(
            job,
            profile,
            experience_result,
            seniority_result,
        )

        job.target_category = target["target_category"]
        job.target_reason = target.get("target_reason") or target.get("reason")
        job.application_priority = target.get("application_priority")

        # Eligibility: can YOU actually take this job?
        EligibilityEvaluator.evaluate(job, profile)
        ApplicationBucketer.assign(job)


# ==================================================
# 5. SORT
# ==================================================

# Inside a bucket, explicit visa support outranks a higher score.
VISA_RANK = {
    "yes": 0,
    "maybe": 1,
}


def sort_jobs(job_objects) -> None:
    """Bucket first, then visa evidence, then score (penalized for missing data)."""

    job_objects.sort(
        key=lambda job: (
            BUCKET_ORDER.get(job.application_bucket, 9),
            VISA_RANK.get(job.visa_sponsorship_status, 2),
            -(job.ranking_score if job.ranking_score is not None else 0),
            -CONFIDENCE_RANK.get(job.confidence, 0),
        )
    )


# ==================================================
# 6. EVERYTHING AFTER COLLECTING
# ==================================================

def process_jobs(jobs: pd.DataFrame, profile) -> list:
    """Raw DataFrame -> sorted list of fully analyzed Job objects."""

    jobs = deduplicate(jobs)

    job_objects = JobNormalizer().normalize_dataframe(jobs)

    print(f"Normalized jobs: {len(job_objects)}")

    analyze_jobs(job_objects)
    score_jobs(job_objects, profile)
    sort_jobs(job_objects)

    return job_objects


def jobs_to_frame(job_objects) -> pd.DataFrame:

    if not job_objects:
        return pd.DataFrame()

    return order_columns(
        pd.DataFrame([job.to_dict() for job in job_objects])
    )