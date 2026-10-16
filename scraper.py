"""
JobRadar entry point.

    python scraper.py                  scrape, save to the database, rank
    python scraper.py --countries uae,qatar
                                       search these countries this time
    python scraper.py --all-countries  search every country this time
    python scraper.py --offline        no scraping: rank what is in the database
    python scraper.py --raw FILE.csv   no scraping: analyze one raw CSV only

Countries take turns: each run searches COUNTRIES_PER_RUN of them (the
ones searched longest ago), so LinkedIn sees fewer requests per run. The
feeds (Arbeitnow, Jaabz, career pages) are read every run.

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
    ARBEITNOW_PAGES,
    COUNTRIES_PER_RUN,
    COUNTRY_PRIORITY,
    RELOCATEME_PAGES,
    JAABZ_PAGES,
    DB_PATH,
    GREENHOUSE_BOARDS,
    LEVER_COMPANIES,
    DELAY_BETWEEN_SEARCHES,
    HOURS_OLD,
    MAX_JOB_AGE_DAYS,
    REPORT_DETAIL_BUCKETS,
    REPORT_HIDE_BUCKETS,
    RATE_LIMIT_WAIT_SECONDS,
    REPORTS_DIR,
    RESULTS_PER_SEARCH,
    SEARCH_CONFIGS,
    SITES,
    STOP_AFTER_RATE_LIMITED,
)
from countries import COUNTRY_PROFILES, search_configs
from database import JobStore
import pandas as pd

from pipeline import (
    assign_countries,
    attach_tracking,
    collect_feeds,
    collect_jobs,
    jobs_to_frame,
    process_jobs,
    split_by_status,
)
from reporting import (
    print_applications,
    print_countries,
    print_details,
    print_ranking,
    print_summary,
    report_to_file,
)
from sources.relevance import in_target_countries
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


def build_source(site):
    # Imported here so the rest of the project (and the tests) work
    # even when JobSpy is not installed.
    from sources import JobSpySource

    return JobSpySource(sites=[site])


def build_feeds(known_ids=()):
    from sources import (
        ArbeitnowSource,
        GreenhouseSource,
        JaabzSource,
        LeverSource,
        RelocateMeSource,
    )

    feeds = []

    if ARBEITNOW_PAGES:
        feeds.append(ArbeitnowSource(max_pages=ARBEITNOW_PAGES))

    if JAABZ_PAGES:
        # Jobs already in the database are not downloaded again.
        countries = [
            (config["jaabz"], config["name"]) for config in SEARCH_CONFIGS if config.get("jaabz")
        ]
        feeds.append(JaabzSource(countries, max_pages=JAABZ_PAGES, known_ids=known_ids))

    if RELOCATEME_PAGES:
        feeds.append(RelocateMeSource(max_pages=RELOCATEME_PAGES, known_ids=known_ids))

    feeds += [GreenhouseSource(board) for board in GREENHOUSE_BOARDS]
    feeds += [LeverSource(company) for company in LEVER_COMPANIES]

    return feeds


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

    which = parser.add_mutually_exclusive_group()

    which.add_argument(
        "--countries",
        metavar="KEYS",
        help="search these countries this time, e.g. uae,qatar "
             f"(known: {', '.join(COUNTRY_PROFILES)})",
    )

    which.add_argument(
        "--all-countries",
        action="store_true",
        help="search every country in config.py this time",
    )

    return parser.parse_args(argv)


def requested_countries(args) -> list:
    """Country keys given with --countries (checked), or []."""

    if not args.countries:
        return []

    keys = [key.strip().lower() for key in args.countries.split(",") if key.strip()]
    search_configs(keys)  # stops with a clear message on an unknown key

    return keys


def ranking_configs(args) -> list:
    """Your countries plus any extra ones asked for with --countries."""

    yours = your_countries()
    extra = [key for key in requested_countries(args) if key not in yours]

    return SEARCH_CONFIGS + search_configs(extra)


def your_countries() -> list:
    """The country keys of config.py (COUNTRIES), in order."""

    return [config["key"] for config in SEARCH_CONFIGS]


def countries_this_run(args, store) -> list:
    if args.countries:
        return requested_countries(args)

    if args.all_countries:
        return your_countries()

    return store.countries_to_search(your_countries(), COUNTRIES_PER_RUN, COUNTRY_PRIORITY)


def scrape(configs, ranking=None, known_ids=()):
    frames = []
    ranking = ranking or configs

    # 1. Search sites (LinkedIn, Indeed, Bayt), one after the other, so a
    #    site that refuses requests does not stop the others. A site only
    #    runs in the countries whose profile lists it.
    for site in SITES:
        site_configs = [c for c in configs if site in c.get("sites", SITES)]

        if not site_configs:
            continue

        print("\n" + "#" * 60)
        print(f"SITE: {site}")
        print("#" * 60)

        frames.append(collect_jobs(
            build_source(site),
            site_configs,
            RESULTS_PER_SEARCH,
            HOURS_OLD,
            delay=DELAY_BETWEEN_SEARCHES,
            rate_limit_wait=RATE_LIMIT_WAIT_SECONDS,
            stop_after_rate_limited=STOP_AFTER_RATE_LIMITED,
        ))

    # 2. Feeds (Arbeitnow, company career pages).
    feeds = build_feeds(known_ids)

    if feeds:
        print("\n" + "#" * 60)
        print("FEEDS")
        print("#" * 60)
        frames.append(collect_feeds(feeds, ranking))

    frames = [frame for frame in frames if not frame.empty]
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    print(f"\nCollected from all sources: {len(raw)}")

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

    ranking = ranking_configs(args)

    if args.raw:
        print(f"Analyzing one raw file, no scraping: {args.raw}")
        raw = fill_missing_descriptions(load_raw([args.raw]), store.descriptions())
        return assign_countries(raw, ranking), set()

    new_ids = set()

    if args.offline:
        if store.count() == 0:
            raise SystemExit("The database is empty. Run python scraper.py first.")

        print("Offline mode: no scraping, ranking the jobs in the database.")
    else:
        chosen = countries_this_run(args, store)
        names = {config["key"]: config.get("name", config["key"]) for config in ranking}
        print("Countries searched this run: " + ", ".join(names[key] for key in chosen))

        rest = [key for key in your_countries() if key not in chosen]

        if rest:
            print(
                "Next runs: " + ", ".join(names[key] for key in rest)
                + "  (or: python scraper.py --all-countries)"
            )

        configs = [c for c in ranking if c["key"] in chosen]
        scraped = scrape(configs, ranking, known_ids=set(store.info()))
        store.mark_searched(chosen)

        # Recover descriptions LinkedIn refused to serve (HTTP 429)
        # from earlier runs, then remember everything.
        scraped = fill_missing_descriptions(scraped, store.descriptions())
        new_ids = store.save_scraped(scraped)

        print(f"New jobs (never seen before): {len(new_ids)}")

    raw = store.load(max_age_days=MAX_JOB_AGE_DAYS)
    recent = len(raw)

    if not raw.empty:
        raw = raw[in_target_countries(raw, ranking)].reset_index(drop=True)
        raw = assign_countries(raw, ranking)

    print(
        f"Jobs in the database: {store.count()}, "
        f"posted in the last {MAX_JOB_AGE_DAYS} days: {recent}, "
        f"in your countries: {len(raw)}"
    )

    return raw, new_ids


def main(argv=None) -> None:
    args = parse_args(argv)
    profile = load_profile()

    with report_to_file(REPORTS_DIR), open_store() as store:

        # 1. Collect (scrape + save, or load from the database)
        raw, new_ids = collect(args, store)

        # 2. De-duplicate, normalize, analyze, score, sort
        priorities = {config["key"]: config.get("priority", 1) for config in ranking_configs(args)}
        job_objects = process_jobs(raw, profile, priorities)

        # 3. Your status: hide what you applied to / dismissed
        attach_tracking(job_objects, store.info(), new_ids)
        to_rank, applied, hidden = split_by_status(job_objects)

        # 4. Save
        frame = jobs_to_frame(to_rank + applied)

        saved_path = None

        if not frame.empty:
            saved_path = save_csv_safely(frame)
            print(f"\nSaved results to {saved_path}")

        # 5. Report (the CSV above always has every job)
        listed = [j for j in to_rank if j.application_bucket not in REPORT_HIDE_BUCKETS]
        detailed = [j for j in to_rank if j.application_bucket in REPORT_DETAIL_BUCKETS]

        print_ranking(listed)

        if len(listed) < len(to_rank):
            print(f"\n({len(to_rank) - len(listed)} skipped jobs not listed: see {saved_path})")

        print_countries(to_rank)
        print_applications(applied)
        print_details(detailed)
        print_summary(to_rank, jobs_to_frame(to_rank), saved_path, {
            "New in this run": sum(1 for job in to_rank if job.is_new),
            "Applied (listed separately)": len(applied),
            "Hidden (not interested / closed)": len(hidden),
        })

        print("\nMark jobs with: python track.py applied <id>  |  no <id>  |  closed <id>")


if __name__ == "__main__":
    main()