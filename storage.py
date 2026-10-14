"""Reading and writing files: raw scrapes, description cache, result CSV."""

import glob
import os
from datetime import datetime

import pandas as pd

from config import OUTPUT_DIR, OUTPUT_FILE, RAW_DIR


def save_raw(jobs: pd.DataFrame, raw_dir: str = RAW_DIR) -> None:
    """
    Keep a timestamped copy of everything scraped, so you can re-score
    later without scraping again (LinkedIn rate-limits).
    """

    if jobs.empty:
        return

    os.makedirs(raw_dir, exist_ok=True)

    jobs.to_csv(
        os.path.join(raw_dir, f"jobs_raw_{datetime.now():%Y%m%d_%H%M%S}.csv"),
        index=False,
    )


def fill_missing_descriptions(jobs: pd.DataFrame, raw_dir: str = RAW_DIR):
    """Recover descriptions LinkedIn refused to serve (429) from earlier runs."""

    if jobs.empty or "id" not in jobs.columns or "description" not in jobs.columns:
        return jobs

    cache = {}

    for path in sorted(glob.glob(os.path.join(raw_dir, "jobs_raw_*.csv"))):
        try:
            old = pd.read_csv(path, usecols=["id", "description"])
        except Exception:
            continue

        for job_id, text in zip(old["id"], old["description"]):
            if isinstance(text, str) and text.strip():
                cache[job_id] = text

    missing = jobs["description"].isna() | (
        jobs["description"].astype(str).str.strip() == ""
    )

    recovered = 0

    for index in jobs.index[missing]:
        text = cache.get(jobs.at[index, "id"])

        if text:
            jobs.at[index, "description"] = text
            recovered += 1

    print(
        f"Descriptions missing: {int(missing.sum())}, "
        f"recovered from earlier runs: {recovered}"
    )

    return jobs


def save_csv_safely(
    frame: pd.DataFrame,
    directory: str = OUTPUT_DIR,
    name: str = OUTPUT_FILE,
) -> str:
    """Save the CSV; if the file is locked (open in Excel), use a timestamped name."""

    os.makedirs(directory, exist_ok=True)

    path = os.path.join(directory, name)

    try:
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return path
    except PermissionError:
        stem, extension = os.path.splitext(name)

        fallback = os.path.join(
            directory,
            f"{stem}_{datetime.now():%Y%m%d_%H%M%S}{extension}",
        )

        frame.to_csv(fallback, index=False, encoding="utf-8-sig")

        print(
            f"\nWARNING: {path} is open in another program. "
            f"Saved to {fallback} instead."
        )

        return fallback
