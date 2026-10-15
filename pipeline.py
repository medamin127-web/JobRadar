"""
The JobRadar pipeline as plain functions. Importing this file does nothing.

    collect_jobs()  ->  raw DataFrame from a source
    process_jobs()  ->  de-duplicate, normalize, analyze, score, sort
    jobs_to_frame() ->  DataFrame ready for the CSV
"""

import random
import re
import time

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
from sources.relevance import in_target_countries, is_tech_title


CONFIDENCE_RANK = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "very_low": 0,
}

# Columns you read first; the rest follow in their natural order.
FRONT_COLUMNS = [
    "application_bucket",
    "is_new",
    "age_days",
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
    "status",
    "status_note",
    "id",
]


def order_columns(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = [c for c in FRONT_COLUMNS if c in frame.columns]
    ordered += [c for c in frame.columns if c not in ordered]

    return frame[ordered]


# ==================================================
# 1. COLLECT
# ==================================================

def collect_feeds(feeds, configs) -> pd.DataFrame:
    """
    Read every feed source (Arbeitnow, company career pages) and keep the
    tech jobs. Jobs from all countries are kept (stored for when you add
    countries); the ranking only shows your countries (in_target_countries).
    """

    frames = []

    for feed in feeds:
        print(f"\nReading feed: {feed.name}")

        try:
            jobs = feed.fetch()
        except Exception as error:
            print(f"  Skipped ({error})")
            continue

        total = len(jobs)

        if not jobs.empty:
            jobs = jobs[jobs["title"].map(is_tech_title)]
            in_yours = in_target_countries(jobs, configs).sum() if not jobs.empty else 0
        else:
            in_yours = 0

        print(f"  {total} jobs, {len(jobs)} tech roles kept, {in_yours} of them in your countries")

        if not jobs.empty:
            frames.append(jobs)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def collect_jobs(
    source,
    configs,
    results_per_search,
    hours_old,
    delay=(0, 0),
    rate_limit_wait=0,
    stop_after_rate_limited=2,
    sleep=time.sleep,
) -> pd.DataFrame:
    """
    Run every search of every config and return all results together.

    Between searches it pauses for a random number of seconds (delay).
    A refused search (HTTP 429) is retried once after rate_limit_wait
    seconds. After stop_after_rate_limited refused searches in a row it
    stops and returns what it has.
    """

    all_jobs = []
    searches = 0
    refused = []
    refused_in_a_row = 0

    def run(search_term, location, country=None):
        extra = {"country": country} if country else {}

        return source.search(
            search_term=search_term,
            location=location,
            results_wanted=results_per_search,
            hours_old=hours_old,
            **extra,
        )

    def was_refused():
        return getattr(source, "last_search_rate_limited", False)

    for config in configs:

        location = config["location"]

        print("\n" + "=" * 60)
        print(f"Location: {location}")
        print("=" * 60)

        for search_term in config["search_terms"]:

            if refused_in_a_row >= stop_after_rate_limited:
                break

            if searches:
                sleep(random.uniform(*delay))

            searches += 1

            site = getattr(source, "name", "")
            print(f"\nSearching{' ' + site if site else ''}: {search_term} | {location}")

            country = config.get("indeed_country")
            scraped = run(search_term, location, country)

            if was_refused():
                print(
                    f"The site refused this search (HTTP 429). "
                    f"Waiting {rate_limit_wait}s and retrying once..."
                )
                sleep(rate_limit_wait)
                scraped = run(search_term, location, country)

            if was_refused():
                refused.append(f"{search_term} | {location}")
                refused_in_a_row += 1
                print("Still refused. Skipping this search.")
            else:
                refused_in_a_row = 0
                print(f"Found {len(scraped)} jobs")

                failures = getattr(source, "last_description_failures", 0)

                if failures:
                    print(
                        f"  ({failures} job descriptions refused; "
                        "earlier runs may still have them)"
                    )

            if not scraped.empty:
                all_jobs.append(scraped)

        if refused_in_a_row >= stop_after_rate_limited:
            break

    jobs = (
        pd.concat(all_jobs, ignore_index=True)
        if all_jobs
        else pd.DataFrame()
    )

    print(f"\nTotal jobs collected: {len(jobs)}")

    if refused:
        print(f"Searches refused: {len(refused)}")

        for item in refused:
            print(f"  - {item}")

        if refused_in_a_row >= stop_after_rate_limited:
            print(
                "Stopped early: the site keeps refusing requests. "
                "Wait a few hours before scraping again, or use "
                "'python scraper.py --offline' to work with saved data."
            )

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

    jobs = merge_across_sites(jobs)

    print(f"Unique jobs after deduplication: {len(jobs)}")

    return jobs


# Gender tags and noise that differ between sites for the same job.
_TITLE_NOISE = re.compile(
    r"\((?:[mwfdx]\s*/\s*){1,3}[mwfdx]\)|\b(?:[mwfdx]/){2}[mwfdx]\b"
    r"|\(all genders?\)|\(all identities\)|\(gn\)|\*",
    re.IGNORECASE,
)
_COMPANY_NOISE = re.compile(
    r"\b(?:gmbh|ag|se|kg|inc|ltd|llc|co|group|germany|deutschland)\b",
    re.IGNORECASE,
)


def _simple(text, noise) -> str:
    import unicodedata

    text = str(text or "").lower().replace("ß", "ss")
    # "für" and "fur" (umlaut lost on one site) must compare equal.
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    text = noise.sub(" ", text)
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def merge_across_sites(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    One job posted on several sites (LinkedIn + Indeed + a career page)
    becomes one row: same company, same title (ignoring "(m/w/d)" etc.)
    and same city. The row with the longest description is kept, and
    `found_on` lists every site it was seen on.
    """

    if jobs.empty or not {"title", "company"} <= set(jobs.columns):
        return jobs

    jobs = jobs.copy()
    sites = jobs["site"] if "site" in jobs.columns else pd.Series([""] * len(jobs))
    # First word of the city: "Frankfurt" == "Frankfurt am Main".
    city = (
        jobs["location"].fillna("").astype(str).str.split(",").str[0]
        .map(lambda c: (_simple(c, _COMPANY_NOISE).split() or [""])[0])
        if "location" in jobs.columns else ""
    )

    # "(SGN)", "(Germany)" etc. after a company name are ignored.
    key = (
        jobs["company"].map(lambda c: _simple(re.sub(r"\(.*?\)", " ", str(c or "")), _COMPANY_NOISE))
        + "|" + jobs["title"].map(lambda t: _simple(t, _TITLE_NOISE))
        + "|" + city
    )

    length = (
        jobs["description"].fillna("").astype(str).str.len()
        if "description" in jobs.columns else 0
    )

    jobs["_key"] = key
    jobs["_length"] = length
    jobs["_site"] = sites.fillna("").astype(str)

    found_on = jobs.groupby("_key")["_site"].agg(
        lambda values: ", ".join(sorted({v for v in values if v}))
    )

    best = jobs.sort_values("_length", ascending=False).drop_duplicates("_key")
    best = best.sort_index()
    best["found_on"] = best["_key"].map(found_on)

    return best.drop(columns=["_key", "_length", "_site"]).reset_index(drop=True)


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


# ==================================================
# 7. TRACKING (database status, new / old)
# ==================================================

def attach_tracking(job_objects, info: dict, new_ids=()) -> None:
    """Copy first_seen / age / your status from the database onto each job."""

    new_ids = set(new_ids)

    for job in job_objects:
        details = info.get(job.id, {})

        job.is_new = job.id in new_ids
        job.first_seen = details.get("first_seen")
        job.age_days = details.get("age_days")
        job.status = details.get("status") or "open"
        job.status_note = details.get("status_note")


def split_by_status(job_objects):
    """
    -> (to_rank, applied, hidden)

    to_rank: jobs you have not acted on yet (the ranking)
    applied: jobs you applied to (listed separately)
    hidden:  not_interested / closed (left out)
    """

    to_rank, applied, hidden = [], [], []

    for job in job_objects:
        if job.status == "applied":
            applied.append(job)
        elif job.status in ("not_interested", "closed"):
            hidden.append(job)
        else:
            to_rank.append(job)

    return to_rank, applied, hidden


def jobs_to_frame(job_objects) -> pd.DataFrame:

    if not job_objects:
        return pd.DataFrame()

    return order_columns(
        pd.DataFrame([job.to_dict() for job in job_objects])
    )