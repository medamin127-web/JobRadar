"""
Hand-labelling: measure how often JobRadar reads a listing correctly.

    python labels.py export      write data/labels/labels.csv
    python labels.py evaluate    compare your answers with JobRadar's

How to label
------------
1. Run `python labels.py export`. It analyzes every saved raw file (no
   scraping) and writes one row per job.
2. Open data/labels/labels.csv in Excel (Data > From Text/CSV, UTF-8).
   Read the description (last column) or open job_url.
3. For each `true_...` column, type the correct answer. The `pred_...`
   column next to it is JobRadar's guess; copy it when it is right.
   Leave a `true_...` cell EMPTY to skip it. Type `none` when the answer
   is "nothing stated" (e.g. no German level).
4. Save (keep the CSV format) and run `python labels.py evaluate`.

Re-running export keeps every answer you already typed and adds new jobs.
Allowed answers are listed in ANSWERS below.
"""

import contextlib
import io
import os
import sys

import pandas as pd

from config import OUTPUT_DIR
from pipeline import BUCKET_ORDER, process_jobs
from storage import fill_missing_descriptions, load_raw, raw_files

LABELS_DIR = os.path.join(os.path.dirname(OUTPUT_DIR), "labels")
LABELS_FILE = os.path.join(LABELS_DIR, "labels.csv")

RECOMMENDED_BUCKETS = {"apply_now", "apply_with_research"}

# field -> allowed answers (shown in the evaluation report)
ANSWERS = {
    "visa": "yes / maybe / no / unknown",
    "relocation": "yes / no / unknown",
    "work_permit_required": "yes / no",
    "german": "none_mentioned / not_required / optional / required / implied",
    "german_level": "A1 A2 B1 B2 C1 C2 / none",
    "seniority": "junior / mid / senior / lead / staff / principal / none",
    "min_years": "a number (2, 3.5) / none",
    "in_my_field": "yes / no   (is this the kind of role you do?)",
    "would_apply": "yes / no   (would you really apply, all things considered?)",
}

FIELDS = list(ANSWERS)


# ==================================================
# PREDICTIONS
# ==================================================

def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "none"

    if isinstance(value, bool):
        return "yes" if value else "no"

    if isinstance(value, float):
        return f"{value:g}"

    text = str(value).strip()
    return text.lower() if text else "none"


def predictions(job) -> dict:
    """JobRadar's answer for every labelled field."""

    return {
        "visa": _text(job.visa_sponsorship_status),
        "relocation": _text(job.relocation_support),
        "work_permit_required": _text(bool(job.work_authorization_required)),
        "german": _text(job.german_requirement),
        "german_level": _text(job.german_level_required),
        "seniority": _text(job.seniority),
        "min_years": _text(job.experience_min_years),
        "in_my_field": "yes" if (job.role_match_score or 0) >= 50 else "no",
        "would_apply": "yes" if job.application_bucket in RECOMMENDED_BUCKETS else "no",
    }


# ==================================================
# EXPORT
# ==================================================

def build_rows(job_objects, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    One row per job: predictions next to empty answer columns.
    Answers already present in `previous` (same id) are kept.
    """

    old_answers = {}

    if previous is not None and not previous.empty:
        for _, row in previous.iterrows():
            answers = {
                f"true_{f}": row.get(f"true_{f}", "")
                for f in FIELDS
            }
            old_answers[str(row["id"])] = (answers, row)

    rows = []

    for job in job_objects:
        row = {
            "id": str(job.id),
            "title": job.title,
            "company": job.company,
            "bucket": job.application_bucket,
            "match_score": job.match_score,
        }

        answers = old_answers.pop(str(job.id), ({}, None))[0]

        for field, value in predictions(job).items():
            row[f"pred_{field}"] = value
            answer = answers.get(f"true_{field}", "")
            row[f"true_{field}"] = "" if pd.isna(answer) else answer

        row.update({
            "visa_evidence": job.visa_sponsorship_evidence,
            "relocation_evidence": job.relocation_evidence,
            "work_permit_evidence": job.work_authorization_evidence,
            "german_evidence": job.german_evidence,
            "job_url": job.job_url,
            "description": (job.description or "")[:30000],
        })

        rows.append(row)

    frame = pd.DataFrame(rows)

    # Jobs you labelled earlier that are no longer in data/raw: keep them.
    leftovers = [
        row for answers, row in old_answers.values()
        if any(_is_answered(v) for v in answers.values())
    ]

    if leftovers:
        frame = pd.concat([frame, pd.DataFrame(leftovers)], ignore_index=True)

    return frame


def _is_answered(value) -> bool:
    return not (value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "")


def read_labels(path: str) -> pd.DataFrame:
    """Read the labels file, whatever Excel did to it (';' or ',', UTF-8 or ANSI)."""

    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(
                path, sep=None, engine="python", dtype=str,
                keep_default_na=False, encoding=encoding,
            )
        except UnicodeDecodeError:
            continue

    raise SystemExit(f"Could not read {path}: unknown text encoding.")


def export(path: str = LABELS_FILE) -> None:
    paths = raw_files()

    if not paths:
        raise SystemExit("No saved raw files in data/raw. Run scraper.py first.")

    from scraper import load_profile

    with contextlib.redirect_stdout(io.StringIO()):
        raw = fill_missing_descriptions(load_raw(paths))
        jobs = process_jobs(raw, load_profile())

    jobs.sort(key=lambda j: BUCKET_ORDER.get(j.application_bucket, 9))

    previous = read_labels(path) if os.path.exists(path) else None
    frame = build_rows(jobs, previous)

    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    except PermissionError:
        raise SystemExit(f"{path} is open in Excel. Close it and run export again.")

    answered = sum(
        any(_is_answered(row.get(f"true_{f}")) for f in FIELDS)
        for _, row in frame.iterrows()
    )

    print(f"Wrote {len(frame)} jobs to {os.path.normpath(path)} "
          f"({answered} already have answers).")
    print("Fill the true_... columns, save, then run: python labels.py evaluate")


# ==================================================
# EVALUATE
# ==================================================

def _same(field, predicted, answer) -> bool:
    predicted = str(predicted).strip().lower()
    answer = str(answer).strip().lower()

    if field == "min_years":
        try:
            return abs(float(predicted) - float(answer.replace(",", "."))) < 0.01
        except ValueError:
            return predicted == answer

    return predicted == answer


def evaluate(frame: pd.DataFrame) -> dict:
    """
    Per field: how many answers, how many JobRadar got right, and the
    mistakes. Also how well the recommendations match "would_apply".
    """

    results = {}

    for field in FIELDS:
        pred_col, true_col = f"pred_{field}", f"true_{field}"

        if true_col not in frame.columns:
            continue

        labelled = frame[frame[true_col].map(_is_answered)]
        mistakes = []

        for _, row in labelled.iterrows():
            if not _same(field, row[pred_col], row[true_col]):
                mistakes.append((row["title"], row["company"],
                                 row[pred_col], str(row[true_col]).strip()))

        results[field] = {
            "labelled": len(labelled),
            "correct": len(labelled) - len(mistakes),
            "mistakes": mistakes,
        }

    if "true_would_apply" in frame.columns:
        labelled = frame[frame["true_would_apply"].map(_is_answered)]
        predicted = labelled["pred_would_apply"].str.lower() == "yes"
        actual = labelled["true_would_apply"].str.strip().str.lower() == "yes"

        results["recommendations"] = {
            "recommended": int(predicted.sum()),
            "recommended_and_you_would_apply": int((predicted & actual).sum()),
            "you_would_apply": int(actual.sum()),
        }

    return results


def print_evaluation(results: dict) -> None:
    print("=" * 70)
    print("JOBRADAR LABEL EVALUATION")
    print("=" * 70)

    for field in FIELDS:
        stats = results.get(field)

        if not stats or not stats["labelled"]:
            print(f"\n{field:22} no answers yet   ({ANSWERS[field]})")
            continue

        accuracy = stats["correct"] / stats["labelled"] * 100
        print(f"\n{field:22} {stats['correct']}/{stats['labelled']} correct ({accuracy:.0f}%)")

        for title, company, predicted, answer in stats["mistakes"]:
            print(f"    - {title[:55]} | {company[:25]}: JobRadar said "
                  f"'{predicted}', you said '{answer}'")

    rec = results.get("recommendations")

    if rec and rec["you_would_apply"] + rec["recommended"]:
        print("\nRecommendations (apply_now + apply_with_research) vs would_apply:")
        print(f"    recommended by JobRadar:          {rec['recommended']}")
        print(f"    ...that you would apply to:       {rec['recommended_and_you_would_apply']}")
        print(f"    jobs you would apply to (total):  {rec['you_would_apply']}")
        missed = rec["you_would_apply"] - rec["recommended_and_you_would_apply"]
        print(f"    good jobs JobRadar did not recommend: {missed}")


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else ""

    if command == "export":
        export()
    elif command == "evaluate":
        if not os.path.exists(LABELS_FILE):
            raise SystemExit("No labels yet. Run: python labels.py export")
        print_evaluation(evaluate(read_labels(LABELS_FILE)))
    else:
        raise SystemExit("Usage: python labels.py export | evaluate")


if __name__ == "__main__":
    main()