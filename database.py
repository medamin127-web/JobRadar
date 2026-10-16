"""
JobRadar's memory: a small SQLite database (data/jobradar.db).

It keeps every job ever scraped, when it was first and last seen, the best
description found so far, and YOUR status for it:

    open             default: not acted on yet
    applied          you applied (kept in a separate list)
    not_interested   hidden from the ranking
    closed           the posting is gone / no longer accepting applications

SQLite is built into Python: there is nothing to install, and the whole
database is one file you can copy or delete.
"""

import json
import math
import os
import re
import sqlite3
from datetime import date, datetime

import pandas as pd

from config import DB_PATH

STATUSES = ("open", "applied", "not_interested", "closed")
HIDDEN_STATUSES = {"not_interested", "closed"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    site            TEXT,
    title           TEXT,
    company         TEXT,
    location        TEXT,
    job_url         TEXT,
    date_posted     TEXT,
    description     TEXT,
    raw             TEXT NOT NULL,      -- the full scraped row, as JSON
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',
    status_note     TEXT,
    status_updated  TEXT
);

-- When each country was last searched (to take turns between countries).
CREATE TABLE IF NOT EXISTS country_runs (
    country         TEXT PRIMARY KEY,
    last_searched   TEXT NOT NULL
);
"""

_RAW_FILE_TIME = re.compile(r"jobs_raw_(\d{8})_(\d{6})")


def _clean(value):
    """Make one cell JSON-friendly (NaN -> None, dates -> text)."""

    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):  # numpy number / bool
        return value.item()

    return value


def _has_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _job_id(row: dict):
    job_id = row.get("id")

    if _has_text(job_id):
        return job_id.strip()

    url = row.get("job_url")
    return url.strip() if _has_text(url) else None


def time_from_raw_filename(path: str):
    """'jobs_raw_20261013_131151.csv' -> '2026-10-13T13:11:51' (or None)."""

    match = _RAW_FILE_TIME.search(os.path.basename(path))

    if not match:
        return None

    return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S").isoformat()


class JobStore:

    def __init__(self, path: str = DB_PATH):
        directory = os.path.dirname(path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ==================================================
    # SAVING SCRAPED JOBS
    # ==================================================

    def save_scraped(self, frame: pd.DataFrame, seen_at: str = None) -> set:
        """
        Add new jobs and refresh known ones. Returns the ids that are new.

        A known job keeps its first_seen date and your status. Its
        description is replaced only by a longer one, so a refused
        (empty) description never overwrites a good one.
        """

        if frame is None or frame.empty:
            return set()

        seen_at = seen_at or datetime.now().isoformat(timespec="seconds")
        new_ids = set()

        with self.connection:
            for record in frame.to_dict("records"):
                row = {key: _clean(value) for key, value in record.items()}
                job_id = _job_id(row)

                if not job_id:
                    continue

                description = row.get("description") if _has_text(row.get("description")) else None
                existing = self.connection.execute(
                    "SELECT description, first_seen, last_seen FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()

                if existing is None:
                    self.connection.execute(
                        """INSERT INTO jobs (id, site, title, company, location, job_url,
                               date_posted, description, raw, first_seen, last_seen)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            job_id, row.get("site"), row.get("title"), row.get("company"),
                            row.get("location"), row.get("job_url"), row.get("date_posted"),
                            description, json.dumps(row, ensure_ascii=False),
                            seen_at, seen_at,
                        ),
                    )
                    new_ids.add(job_id)
                    continue

                old_description = existing["description"] or ""
                better = description and len(description) > len(old_description)

                self.connection.execute(
                    """UPDATE jobs SET
                           last_seen = MAX(last_seen, ?),
                           first_seen = MIN(first_seen, ?),
                           description = CASE WHEN ? THEN ? ELSE description END,
                           raw = CASE WHEN ? THEN ? ELSE raw END
                       WHERE id = ?""",
                    (
                        seen_at, seen_at,
                        bool(better), description,
                        bool(better), json.dumps(row, ensure_ascii=False),
                        job_id,
                    ),
                )

        return new_ids

    def import_raw_files(self, paths) -> int:
        """Load old data/raw CSV files (first run after the upgrade)."""

        added = 0

        for path in sorted(paths):
            try:
                frame = pd.read_csv(path)
            except Exception as error:
                print(f"Could not read {path}: {error}")
                continue

            added += len(self.save_scraped(frame, seen_at=time_from_raw_filename(path)))

        return added

    def count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    # ==================================================
    # READING
    # ==================================================

    def load(self, max_age_days: int = None, today: date = None) -> pd.DataFrame:
        """
        Every saved job as a raw DataFrame (the same columns the scraper
        returns) plus first_seen, last_seen, status, status_note, age_days.

        max_age_days leaves out jobs posted (or, without a date, first
        seen) longer ago than that.
        """

        today = today or date.today()
        rows = []

        for job in self.connection.execute("SELECT * FROM jobs ORDER BY first_seen DESC"):
            record = json.loads(job["raw"])
            record["id"] = job["id"]
            record["description"] = job["description"]

            age = _age_days(job["date_posted"] or job["first_seen"], today)

            if max_age_days is not None and age is not None and age > max_age_days:
                continue

            record.update({
                "first_seen": job["first_seen"],
                "last_seen": job["last_seen"],
                "status": job["status"],
                "status_note": job["status_note"],
                "age_days": age,
            })
            rows.append(record)

        return pd.DataFrame(rows)

    def descriptions(self) -> dict:
        """id -> saved description (to fill descriptions LinkedIn refused)."""

        return {
            row["id"]: row["description"]
            for row in self.connection.execute(
                "SELECT id, description FROM jobs WHERE description IS NOT NULL"
            )
        }

    def info(self) -> dict:
        """id -> first_seen / status / status_note / age_days."""

        today = date.today()

        return {
            row["id"]: {
                "first_seen": row["first_seen"],
                "status": row["status"],
                "status_note": row["status_note"],
                "age_days": _age_days(row["date_posted"] or row["first_seen"], today),
            }
            for row in self.connection.execute(
                "SELECT id, first_seen, status, status_note, date_posted FROM jobs"
            )
        }

    # ==================================================
    # TAKING TURNS BETWEEN COUNTRIES
    # ==================================================

    def countries_to_search(self, keys, how_many: int, priorities=None, now=None) -> list:
        """
        The `how_many` most overdue countries: never searched first, then
        by (hours since the last search) x priority, so a priority-2
        country comes back about twice as often. Ties keep the order of
        `keys`. 0 or less = all of them.
        """

        keys = list(keys)

        if how_many <= 0 or how_many >= len(keys):
            return keys

        priorities = priorities or {}
        now = now or datetime.now()
        last = self.last_searched()

        def overdue(key):
            when = last.get(key)

            if not when:
                return float("inf")

            hours = (now - datetime.fromisoformat(when)).total_seconds() / 3600
            return max(hours, 0) * priorities.get(key, 1)

        ordered = sorted(keys, key=lambda key: (-overdue(key), keys.index(key)))

        return ordered[:how_many]

    def mark_searched(self, keys, when: str = None) -> None:
        when = when or datetime.now().isoformat(timespec="seconds")

        with self.connection:
            for key in keys:
                self.connection.execute(
                    "INSERT INTO country_runs (country, last_searched) VALUES (?, ?) "
                    "ON CONFLICT(country) DO UPDATE SET last_searched = excluded.last_searched",
                    (key, when),
                )

    def last_searched(self) -> dict:
        return {
            row["country"]: row["last_searched"]
            for row in self.connection.execute("SELECT * FROM country_runs")
        }

    # ==================================================
    # YOUR STATUS
    # ==================================================

    def find(self, reference: str) -> list:
        """
        Jobs matching a reference: the full id ("li-4460378155"), the
        LinkedIn number ("4460378155") or its last digits ("378155").
        """

        reference = str(reference).strip()

        exact = self.connection.execute(
            "SELECT * FROM jobs WHERE id = ? OR id = ?", (reference, f"li-{reference}")
        ).fetchall()

        if exact:
            return exact

        if len(reference) < 4:
            return []

        return self.connection.execute(
            "SELECT * FROM jobs WHERE id LIKE ?", (f"%{reference}",)
        ).fetchall()

    def set_status(self, job_id: str, status: str, note: str = None) -> None:
        if status not in STATUSES:
            raise ValueError(f"Unknown status {status!r}; use one of {STATUSES}")

        with self.connection:
            self.connection.execute(
                "UPDATE jobs SET status = ?, status_note = ?, status_updated = ? WHERE id = ?",
                (status, note, datetime.now().isoformat(timespec="seconds"), job_id),
            )

    def by_status(self, status: str) -> list:
        return self.connection.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY status_updated DESC", (status,)
        ).fetchall()


def _age_days(value, today: date):
    if not _has_text(value):
        return None

    try:
        return (today - date.fromisoformat(value[:10])).days
    except ValueError:
        return None