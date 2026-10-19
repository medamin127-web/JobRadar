"""
The ranked jobs, computed once like `python scraper.py --offline` and kept
in memory. The dashboard reads this snapshot; "Refresh" builds it again
(after a scrape, for example).
"""

import contextlib
import io
import threading
from datetime import datetime, timedelta

from config import MAX_JOB_AGE_DAYS, SEARCH_CONFIGS
from countries import COUNTRY_PROFILES

# Jobs first seen within this long of the newest one came from the latest run.
NEW_WINDOW = timedelta(hours=3)

BUCKETS = ["apply_now", "apply_with_research", "long_shot", "review", "skip"]


class Snapshot:

    def __init__(self, jobs, built_at, last_run=None):
        self.jobs = jobs                              # ranked, best first
        self.by_id = {job.id: job for job in jobs}
        self.built_at = built_at
        self.last_run = last_run


def _parse(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def mark_new(jobs) -> datetime | None:
    """job.is_new = first seen in the latest run. Returns that run's time."""

    seen = [d for d in (_parse(job.first_seen) for job in jobs) if d]

    if not seen:
        return None

    latest = max(seen)

    for job in jobs:
        first = _parse(job.first_seen)
        job.is_new = bool(first and first >= latest - NEW_WINDOW)

    return latest


def build(store=None, profile=None, quiet=True) -> Snapshot:
    """Load the database and rank every job (no scraping, no downloads)."""

    import sponsors
    from pipeline import assign_countries, attach_tracking, process_jobs
    from sources.relevance import in_target_countries

    if profile is None:
        from scraper import load_profile

        profile = load_profile()

    own_store = store is None

    if own_store:
        from scraper import open_store

        store = open_store()

    output = io.StringIO()

    try:
        with contextlib.redirect_stdout(output) if quiet else contextlib.nullcontext():
            raw = store.load(max_age_days=MAX_JOB_AGE_DAYS)

            if not raw.empty:
                raw = raw[in_target_countries(raw, SEARCH_CONFIGS)].reset_index(drop=True)
                raw = assign_countries(raw, SEARCH_CONFIGS)

            priorities = {config["key"]: config.get("priority", 1) for config in SEARCH_CONFIGS}
            registers = sponsors.load_for(SEARCH_CONFIGS, auto_update=False, output=lambda *a: None)
            jobs = process_jobs(raw, profile, priorities, registers) if not raw.empty else []
            attach_tracking(jobs, store.info())
            last_run = mark_new(jobs)
    finally:
        if own_store:
            store.close()

    return Snapshot(jobs, datetime.now(), last_run)


class SnapshotHolder:
    """One snapshot shared by all requests; rebuilt on demand."""

    def __init__(self, builder=build):
        self.builder = builder
        self.snapshot = None
        self.lock = threading.Lock()

    def get(self) -> Snapshot:
        with self.lock:
            if self.snapshot is None:
                self.snapshot = self.builder()
            return self.snapshot

    def refresh(self) -> Snapshot:
        with self.lock:
            self.snapshot = self.builder()
            return self.snapshot


def country_label(key) -> str:
    if not key:
        return "Other"
    return COUNTRY_PROFILES.get(key, {}).get("name", key)