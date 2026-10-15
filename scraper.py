"""
JobRadar entry point.

    python scraper.py                  scrape LinkedIn, save to the database, rank
    python scraper.py --offline        no scraping: rank what is in the database
    python scraper.py --raw FILE.csv   no scraping: analyze one raw CSV only

Every run ranks all saved jobs that are still current (posted within
MAX_JOB_AGE_DAYS) and that you have not marked applied / not interested /
closed (see track.py). Jobs found for the first time are marked NEW.

Offline mode is what you use after changing candidate_profile.py or the
analyzers, or while LinkedIn is refusing requests.

Searches are configured in config.py, your profile lives in
candidate_profile.py. Importing this file does nothing; everything
happens inside main().
"""

import argparse

from config import (
    DB_PATH,
    DELAY_BETWEEN_SEARCHES,
    HOURS_OLD,
    MAX_JOB_AGE_DAYS,
    RATE_LIMIT_WAIT_SECONDS,
    REPORTS_DIR,
    RESULTS_PER_SEARCH,
    SEARCH_CONFIGS,
    SITES,
    STOP_AFTER_RATE_LIMITED,
)
from database import JobStore
from pipeline import (
    attach_tracking,
    collect_jobs,
    jobs_to_frame,
    process_jobs,
    split_by_status,
)
from reporting import (
    print_applications,
    print_details,
    print_ranking,
    print_summary,
    report_to_file,
)
from storage import (
    fill_missing_descriptions,
    load_raw,
    raw_files,
    save_csv_safely,
    save_raw,
)


def load_profile():
    try:
        from candidate_profile import PROFILE
    except ModuleNotFoundError:
        raise SystemExit(
            "candidate_profile.py not found.\n"
            "Copy candidate_profile.example.py to candidate_profile.py "
            "and fill in your own details."
        )

    return PROFILE


def build_source():
    # Imported here so the rest of the project (and the tests) work
    # even when JobSpy is not installed.
    from sources import JobSpySource

    return JobSpySource(sites=SITES)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="JobRadar")

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--offline",
        action="store_true",
        help="do not scrape; rank the jobs saved in the database",
    )

    mode.add_argument(
        "--raw",
        metavar="FILE",
        help="do not scrape; re-analyze this one raw CSV",
    )

    return parser.parse_args(argv)


def scrape():
    raw = collect_jobs(
        build_source(),
        SEARCH_CONFIGS,
        RESULTS_PER_SEARCH,
        HOURS_OLD,
        delay=DELAY_BETWEEN_SEARCHES,
        rate_limit_wait=RATE_LIMIT_WAIT_SECONDS,
        stop_after_rate_limited=STOP_AFTER_RATE_LIMITED,
    )

    save_raw(raw)

    return raw


def open_store() -> JobStore:
    """Open the database; the first time, import the old data/raw files."""

    store = JobStore(DB_PATH)

    if store.count() == 0 and raw_files():
        added = store.import_raw_files(raw_files())
        print(f"First run with the database: imported {added} jobs from data/raw.")

    return store


def collect(args, store):
    """-> (raw jobs to analyze, ids that are new)"""

    if args.raw:
        print(f"Analyzing one raw file, no scraping: {args.raw}")
        raw = fill_missing_descriptions(load_raw([args.raw]), store.descriptions())
        return raw, set()

    new_ids = set()

    if args.offline:
        if store.count() == 0:
            raise SystemExit("The database is empty. Run python scraper.py first.")

        print("Offline mode: no scraping, ranking the jobs in the database.")
    else:
        scraped = scrape()

        # Recover descriptions LinkedIn refused to serve (HTTP 429)
        # from earlier runs, then remember everything.
        scraped = fill_missing_descriptions(scraped, store.descriptions())
        new_ids = store.save_scraped(scraped)

        print(f"New jobs (never seen before): {len(new_ids)}")

    raw = store.load(max_age_days=MAX_JOB_AGE_DAYS)

    print(
        f"Jobs in the database: {store.count()}, "
        f"posted in the last {MAX_JOB_AGE_DAYS} days: {len(raw)}"
    )

    return raw, new_ids


def main(argv=None) -> None:
    args = parse_args(argv)
    profile = load_profile()

    with report_to_file(REPORTS_DIR), open_store() as store:

        # 1. Collect (scrape + save, or load from the database)
        raw, new_ids = collect(args, store)

        # 2. De-duplicate, normalize, analyze, score, sort
        job_objects = process_jobs(raw, profile)

        # 3. Your status: hide what you applied to / dismissed
        attach_tracking(job_objects, store.info(), new_ids)
        to_rank, applied, hidden = split_by_status(job_objects)

        # 4. Save
        frame = jobs_to_frame(to_rank + applied)

        saved_path = None

        if not frame.empty:
            saved_path = save_csv_safely(frame)
            print(f"\nSaved results to {saved_path}")

        # 5. Report
        print_ranking(to_rank)
        print_applications(applied)
        print_details(to_rank)
        print_summary(to_rank, jobs_to_frame(to_rank), saved_path, {
            "New in this run": sum(1 for job in to_rank if job.is_new),
            "Applied (listed separately)": len(applied),
            "Hidden (not interested / closed)": len(hidden),
        })

        print("\nMark jobs with: python track.py applied <id>  |  no <id>  |  closed <id>")


if __name__ == "__main__":
    main()