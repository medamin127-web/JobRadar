"""
Keep track of what you did with each job.

    python track.py                        what to look at now + your applications
    python track.py applied <id> ["note"]  you applied (note: date, contact, ...)
    python track.py no <id>                not interested: hide it
    python track.py closed <id>            posting closed: hide it
    python track.py open <id>              undo: back to the ranking
    python track.py show <id>              everything saved about one job

<id> is the number shown in the ranking ("id 4460378155"). The last 6
digits are enough when they are unique.
"""

import os
import sys

import pandas as pd

from config import DB_PATH, OUTPUT_DIR, OUTPUT_FILE
from database import JobStore
from reporting import short_id

RECOMMENDED = ("apply_now", "apply_with_research")

COMMANDS = {
    "applied": "applied",
    "no": "not_interested",
    "closed": "closed",
    "open": "open",
}

LABELS = {
    "applied": "marked as APPLIED",
    "not_interested": "hidden (not interested)",
    "closed": "hidden (closed)",
    "open": "back in the ranking",
}


def _find_one(store, reference, output=print):
    matches = store.find(reference)

    if not matches:
        output(f"No job with id {reference}. Copy the id from the ranking (e.g. 4460378155).")
        return None

    if len(matches) > 1:
        output(f"{len(matches)} jobs end with {reference}; type more digits:")
        for job in matches:
            output(f"  {short_id(job['id'])}  {job['title']} | {job['company']}")
        return None

    return matches[0]


def set_status(store, command, reference, note=None, output=print) -> bool:
    job = _find_one(store, reference, output)

    if job is None:
        return False

    status = COMMANDS[command]
    store.set_status(job["id"], status, note)
    output(f"{job['title']} | {job['company']}: {LABELS[status]}")

    return True


def show(store, reference, output=print) -> None:
    job = _find_one(store, reference, output)

    if job is None:
        return

    output(f"{job['title']} | {job['company']} | {job['location']}")
    output(f"id {short_id(job['id'])} | posted {job['date_posted']} | "
           f"first seen {job['first_seen'][:10]} | last seen {job['last_seen'][:10]}")
    output(f"status: {job['status']}" + (f" ({job['status_note']})" if job["status_note"] else ""))
    output(job["job_url"] or "")


def overview(store, results_path=None, output=print) -> None:
    """Recommended jobs from the last run that you have not acted on yet."""

    results_path = results_path or os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    statuses = {row["id"]: row["status"] for row in store.connection.execute("SELECT id, status FROM jobs")}

    output("=" * 78)
    output("TO LOOK AT (recommended, not acted on yet)")
    output("=" * 78)

    if os.path.exists(results_path):
        frame = pd.read_csv(results_path, encoding="utf-8-sig")
        todo = frame[
            frame["application_bucket"].isin(RECOMMENDED)
            & frame["id"].map(lambda i: statuses.get(i, "open") == "open")
        ]

        if todo.empty:
            output("Nothing new. Run python scraper.py for fresh jobs.")

        for _, job in todo.iterrows():
            new = "NEW " if str(job.get("is_new")).lower() == "true" else "    "
            output(f"{new}{short_id(job['id']):>12}  {job['match_score']:>3.0f}  "
                   f"{job['title']} | {job['company']}")
            output(f"{'':18}{job['job_url']}")
    else:
        output("No results yet. Run python scraper.py first.")

    applied = store.by_status("applied")

    output("")
    output("=" * 78)
    output(f"YOUR APPLICATIONS ({len(applied)})")
    output("=" * 78)

    for job in applied:
        note = f" | {job['status_note']}" if job["status_note"] else ""
        output(f"{short_id(job['id']):>12}  {job['title']} | {job['company']} "
               f"| {str(job['status_updated'])[:10]}{note}")

    output("")
    output("Mark a job: python track.py applied <id> | no <id> | closed <id>")


def main(argv=None, output=print) -> None:
    argv = sys.argv[1:] if argv is None else argv

    with JobStore(DB_PATH) as store:
        if not argv:
            overview(store, output=output)
        elif argv[0] in COMMANDS and len(argv) >= 2:
            note = " ".join(argv[2:]) or None
            set_status(store, argv[0], argv[1], note, output)
        elif argv[0] == "show" and len(argv) == 2:
            show(store, argv[1], output)
        else:
            output(__doc__)


if __name__ == "__main__":
    main()