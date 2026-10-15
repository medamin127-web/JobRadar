"""
JobRadar entry point.

    python scraper.py                  scrape LinkedIn, then analyze and rank
    python scraper.py --offline        no scraping: re-analyze every saved raw file
    python scraper.py --raw FILE.csv   no scraping: re-analyze one saved raw file

Offline mode is what you use after changing candidate_profile.py or the
analyzers, or while LinkedIn is refusing requests.

Searches are configured in config.py, your profile lives in
candidate_profile.py. Importing this file does nothing; everything
happens inside main().
"""

import argparse

from config import (
    DELAY_BETWEEN_SEARCHES,
    HOURS_OLD,
    RATE_LIMIT_WAIT_SECONDS,
    REPORTS_DIR,
    RESULTS_PER_SEARCH,
    SEARCH_CONFIGS,
    SITES,
    STOP_AFTER_RATE_LIMITED,
)
from pipeline import collect_jobs, jobs_to_frame, process_jobs
from reporting import (
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
        help="do not scrape; re-analyze every file in data/raw",
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


def load_saved(args):
    paths = [args.raw] if args.raw else raw_files()

    if not paths:
        raise SystemExit("No saved raw files found in data/raw.")

    print(f"Offline mode: analyzing {len(paths)} saved raw file(s), no scraping.")

    raw = load_raw(paths)

    print(f"Total saved jobs loaded: {len(raw)}")

    return raw


def main(argv=None) -> None:
    args = parse_args(argv)
    profile = load_profile()

    with report_to_file(REPORTS_DIR):

        # 1. Collect (or load saved data)
        raw = load_saved(args) if (args.offline or args.raw) else scrape()

        # Recover descriptions LinkedIn refused to serve (HTTP 429)
        # using copies saved by earlier runs.
        raw = fill_missing_descriptions(raw)

        # 2. De-duplicate, normalize, analyze, score, sort
        job_objects = process_jobs(raw, profile)

        # 3. Save
        frame = jobs_to_frame(job_objects)

        saved_path = None

        if not frame.empty:
            saved_path = save_csv_safely(frame)
            print(f"\nSaved results to {saved_path}")

        # 4. Report
        print_ranking(job_objects)
        print_details(job_objects)
        print_summary(job_objects, frame, saved_path)


if __name__ == "__main__":
    main()