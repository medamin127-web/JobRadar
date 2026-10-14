"""
JobRadar entry point.

    python scraper.py

Searches are configured in config.py, your profile lives in
candidate_profile.py. Importing this file does nothing; everything
happens inside main().
"""

from config import (
    HOURS_OLD,
    REPORTS_DIR,
    RESULTS_PER_SEARCH,
    SEARCH_CONFIGS,
    SITES,
)
from pipeline import collect_jobs, jobs_to_frame, process_jobs
from reporting import (
    print_details,
    print_ranking,
    print_summary,
    report_to_file,
)
from storage import fill_missing_descriptions, save_csv_safely, save_raw


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


def main() -> None:
    profile = load_profile()

    with report_to_file(REPORTS_DIR):

        # 1. Collect
        raw = collect_jobs(
            build_source(),
            SEARCH_CONFIGS,
            RESULTS_PER_SEARCH,
            HOURS_OLD,
        )

        save_raw(raw)

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
