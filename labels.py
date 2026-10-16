"""
Teach JobRadar what is right: you answer a few questions per job, then
JobRadar is scored against your answers.

    python labels.py label       answer questions, one job at a time
    python labels.py evaluate    see where JobRadar disagrees with you
                                 (re-analyzes first: no export needed)
    python labels.py review      go through each disagreement: who is right?

`label` shows one job (title, company, the key sentences, the start of the
description) and asks 4 questions. Press one key per question; press Enter
to accept JobRadar's guess shown in [brackets]. Your answers are saved
after every job, so you can stop any time with q and continue later.

Aim for about 20 jobs. The most useful ones come first.

(`python labels.py export` still writes data/labels/labels.csv without
asking anything, if you prefer to fill it in Excel.)
"""

import contextlib
import io
import os
import sys
import textwrap
import webbrowser

import pandas as pd

from config import OUTPUT_DIR, SEARCH_CONFIGS
from pipeline import BUCKET_ORDER, assign_countries, process_jobs

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


def export(path: str = LABELS_FILE, quiet: bool = False) -> None:
    from scraper import load_profile, open_store

    with contextlib.redirect_stdout(io.StringIO()), open_store() as store:
        raw = store.load()

        if raw.empty:
            raise SystemExit("The database is empty. Run scraper.py first.")

        jobs = process_jobs(assign_countries(raw, SEARCH_CONFIGS), load_profile())

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

    if quiet:
        return

    print(f"Wrote {len(frame)} jobs to {os.path.normpath(path)} "
          f"({answered} already have answers).")
    print("Fill the true_... columns, save, then run: python labels.py evaluate")


# ==================================================
# INTERACTIVE LABELLING
# ==================================================

# (field, question, {key: answer}) — the four questions asked per job.
QUESTIONS = [
    ("would_apply",
     "Would you really apply to this job?",
     {"y": "yes", "n": "no"}),
    ("in_my_field",
     "Is it the kind of role you do (web / full stack / backend / frontend)?",
     {"y": "yes", "n": "no"}),
    ("visa",
     "What does the AD TEXT say about VISA support? (only what is written)",
     {"y": "yes", "m": "maybe", "n": "no", "u": "unknown"}),
    ("german",
     "What does the AD TEXT say about GERMAN? (only what is written)",
     {"n": "none_mentioned", "o": "optional", "r": "required",
      "i": "implied", "x": "not_required"}),
]

KEY_HELP = {
    "visa": "y = offers visa help   m = maybe / case by case   "
            "n = refuses   u = says nothing",
    "german": "n = not mentioned   o = nice to have / a plus   r = required "
              "(or the whole ad is in German)   x = says not needed",
}


def _say(text: str = "", output=print) -> None:
    """print() that never crashes on an old Windows console."""
    try:
        output(text)
    except UnicodeEncodeError:
        output(text.encode("ascii", "replace").decode("ascii"))


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def show_job(row, number: int, total: int, output=print, full=False) -> None:
    _say("\n" + "=" * 78, output)
    _say(f"JOB {number}/{total}   {row.get('bucket', '')}   "
         f"score {row.get('match_score', '')}", output)
    _say(f"{_clean(row.get('title'))}", output)
    _say(f"{_clean(row.get('company'))}", output)
    _say(f"{row.get('job_url', '')}", output)
    _say("-" * 78, output)

    for label, column in [
        ("Visa sentence", "visa_evidence"),
        ("Relocation sentence", "relocation_evidence"),
        ("German sentence", "german_evidence"),
        ("Work permit sentence", "work_permit_evidence"),
    ]:
        text = _clean(row.get(column))

        if text and text.lower() not in ("none", "nan") and not text.startswith("No "):
            _say(f"{label}: {text}", output)

    description = _clean(row.get("description"))
    limit = None if full else 900
    shown = description if limit is None else description[:limit]

    _say("", output)
    _say(textwrap.fill(shown, width=78), output)

    if limit is not None and len(description) > limit:
        _say("... (press d to read the whole description)", output)


def ask_job(row, number, total, input_fn=input, output=print, open_url=webbrowser.open):
    """
    Ask the 4 questions for one job.

    Returns a dict of answers, or "skip" / "quit".
    """

    show_job(row, number, total, output)
    answers = {}

    for field, question, keys in QUESTIONS:
        guess = str(row.get(f"pred_{field}", "")).strip().lower()
        guess_key = next((k for k, v in keys.items() if v == guess), None)

        choices = "/".join(keys)
        default = f" [{guess_key}]" if guess_key else ""

        _say("", output)
        _say(f"{question}", output)

        if field in KEY_HELP:
            _say(f"   {KEY_HELP[field]}", output)

        while True:
            reply = input_fn(f"   {choices}{default}  (d=description o=open s=skip q=quit) > ")
            reply = reply.strip().lower()

            if reply == "" and guess_key:
                reply = guess_key

            if reply in keys:
                answers[f"true_{field}"] = keys[reply]
                break
            if reply == "d":
                show_job(row, number, total, output, full=True)
            elif reply == "o":
                if row.get("job_url"):
                    open_url(str(row["job_url"]))
            elif reply == "s":
                return "skip"
            elif reply == "q":
                return "quit"
            else:
                _say(f"   Please type one of: {choices}", output)

    return answers


def _needs_answers(row) -> bool:
    return not all(_is_answered(row.get(f"true_{field}")) for field, _, _ in QUESTIONS)


def label(path: str = LABELS_FILE, input_fn=input, output=print, refresh=True) -> None:
    if refresh:
        _say("Preparing jobs (this re-analyzes your saved data, no scraping)...", output)
        export(path, quiet=True)

    frame = read_labels(path)
    todo = [i for i in frame.index if _needs_answers(frame.loc[i])]
    done = len(frame) - len(todo)

    if not todo:
        _say("Every job already has answers. Run: python labels.py evaluate", output)
        return

    _say(f"\n{done} jobs answered, {len(todo)} to go. "
         "Aim for about 20. Press q any time to stop (answers are saved).", output)

    for count, index in enumerate(todo, start=1):
        result = ask_job(frame.loc[index], count, len(todo), input_fn, output)

        if result == "quit":
            break
        if result == "skip":
            continue

        for column, value in result.items():
            frame.at[index, column] = value

        _save(frame, path)
        done += 1
        _say(f"   Saved. ({done} answered)", output)

    _say("\nNext: python labels.py evaluate", output)


def review(path: str = LABELS_FILE, input_fn=input, output=print, refresh=True) -> None:
    """
    Walk through every disagreement between your answers and JobRadar.

    For each one: k = your answer stands (JobRadar is wrong),
    j = JobRadar is right (your answer is replaced), or type a new answer.
    """

    if refresh:
        _say("Preparing jobs (this re-analyzes your saved data, no scraping)...", output)
        export(path, quiet=True)

    frame = read_labels(path)

    disagreements = [
        (index, field, keys)
        for index in frame.index
        for field, _, keys in QUESTIONS
        if _is_answered(frame.at[index, f"true_{field}"])
        and not _same(field, frame.at[index, f"pred_{field}"], frame.at[index, f"true_{field}"])
    ]

    if not disagreements:
        _say("No disagreements left.", output)
        return

    _say(f"\n{len(disagreements)} disagreements. For each: k = you are right, "
         "j = JobRadar is right, or type a new answer. q = stop.", output)

    for count, (index, field, keys) in enumerate(disagreements, start=1):
        row = frame.loc[index]
        yours = str(row[f"true_{field}"]).strip().lower()
        theirs = str(row[f"pred_{field}"]).strip().lower()

        show_job(row, count, len(disagreements), output)
        question = next(q for f, q, _ in QUESTIONS if f == field)

        _say("", output)
        _say(question, output)

        if field in KEY_HELP:
            _say(f"   {KEY_HELP[field]}", output)

        _say(f"   You said: {yours}     JobRadar said: {theirs}", output)

        while True:
            reply = input_fn(f"   k/j or {'/'.join(keys)}  (d=description o=open s=skip q=quit) > ")
            reply = reply.strip().lower()

            if reply in ("k", "s"):
                break
            if reply == "j":
                frame.at[index, f"true_{field}"] = theirs
                break
            if reply in keys:
                frame.at[index, f"true_{field}"] = keys[reply]
                break
            if reply == "d":
                show_job(row, count, len(disagreements), output, full=True)
            elif reply == "o":
                if row.get("job_url"):
                    webbrowser.open(str(row["job_url"]))
            elif reply == "q":
                _save(frame, path)
                _say("\nSaved. Next: python labels.py evaluate", output)
                return
            else:
                _say("   Please type k, j or one of: " + "/".join(keys), output)

        _save(frame, path)

    _say("\nDone. Next: python labels.py evaluate", output)


def _save(frame, path) -> None:
    try:
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    except PermissionError:
        raise SystemExit(f"{path} is open in Excel. Close it and run label again.")


# ==================================================
# EVALUATE
# ==================================================

# Answers that mean the same thing in practice.
EQUIVALENT = {
    # An ad written in German with no stated level needs German.
    "german": {"implied": "required"},
}


def _same(field, predicted, answer) -> bool:
    predicted = str(predicted).strip().lower()
    answer = str(answer).strip().lower()

    same_as = EQUIVALENT.get(field, {})
    predicted = same_as.get(predicted, predicted)
    answer = same_as.get(answer, answer)

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

    unanswered = []

    for field in FIELDS:
        stats = results.get(field)

        if not stats or not stats["labelled"]:
            unanswered.append(field)
            continue

        accuracy = stats["correct"] / stats["labelled"] * 100
        print(f"\n{field:22} {stats['correct']}/{stats['labelled']} correct ({accuracy:.0f}%)")

        for title, company, predicted, answer in stats["mistakes"]:
            print(f"    - {title[:55]} | {company[:25]}: JobRadar said "
                  f"'{predicted}', you said '{answer}'")

    if len(unanswered) == len(FIELDS):
        print("\nNo answers yet. Run: python labels.py label")
        return

    if any(results.get(f, {}).get("mistakes") for f in FIELDS):
        print("\nTo check each disagreement one by one: python labels.py review")

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

    if command == "label":
        label()
    elif command == "review":
        review()
    elif command == "export":
        export()
    elif command == "evaluate":
        if not os.path.exists(LABELS_FILE):
            raise SystemExit("No labels yet. Run: python labels.py label")

        # Re-analyze first, so the scores reflect the current code and
        # profile (your answers are kept).
        print("Refreshing JobRadar's answers (no scraping)...")
        export(LABELS_FILE, quiet=True)
        print_evaluation(evaluate(read_labels(LABELS_FILE)))
    else:
        raise SystemExit("Usage: python labels.py label | evaluate | review | export")


if __name__ == "__main__":
    main()