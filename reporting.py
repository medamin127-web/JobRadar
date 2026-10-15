"""Everything JobRadar prints, plus the UTF-8 report file."""

import os
import sys
from contextlib import contextmanager
from datetime import datetime

import pandas as pd


class _Tee:
    """Print to the console AND to a UTF-8 report file.

    Redirecting Python output through PowerShell garbles characters such
    as the euro sign; the report in reports/ is always correct UTF-8.
    """

    def __init__(self, console, report):
        self.console = console
        self.report = report

    def write(self, data):
        try:
            self.console.write(data)
        except UnicodeEncodeError:
            self.console.write(
                data.encode("ascii", "replace").decode("ascii")
            )

        self.report.write(data)

    def flush(self):
        self.console.flush()
        self.report.flush()


@contextmanager
def report_to_file(reports_dir: str):
    """
    While active, everything printed also goes to reports/run_<time>.txt.
    stdout is restored afterwards.
    """

    os.makedirs(reports_dir, exist_ok=True)

    path = os.path.join(reports_dir, f"run_{datetime.now():%Y%m%d_%H%M%S}.txt")
    original = sys.stdout

    with open(path, "w", encoding="utf-8") as report:
        sys.stdout = _Tee(original, report)

        try:
            yield path
        finally:
            sys.stdout = original


def print_ranking(job_objects) -> None:

    print("\n" + "=" * 100)
    print("JOBRADAR MATCH RANKING")
    print("=" * 100)

    if not job_objects:
        print("No jobs found.")
        return

    for index, job in enumerate(job_objects, start=1):

        print(
            f"{index:2}. "
            f"{'NEW' if job.is_new else '   '} "
            f"{job.match_score if job.match_score is not None else 0:5.1f}/100 | "
            f"{job.application_bucket or 'unknown':19} | "
            f"Elig: {job.eligibility_status or 'unknown':8} | "
            f"Confidence: {job.confidence or 'unknown':8} | "
            f"Target: {job.target_category or 'unknown':14} | "
            f"{job.title} | "
            f"{job.company} | "
            f"{job.location}"
            f"{_age_text(job)}"
            f" | id {short_id(job.id)}"
        )


def short_id(job_id) -> str:
    """'li-4460378155' -> '4460378155' (what you type in track.py)."""
    text = str(job_id or "")
    return text[3:] if text.startswith("li-") else text


def _age_text(job) -> str:
    if job.age_days is None:
        return ""

    return " | today" if job.age_days <= 0 else f" | {job.age_days}d old"


def print_applications(applied) -> None:
    if not applied:
        return

    print("\n" + "=" * 100)
    print(f"YOUR APPLICATIONS ({len(applied)})")
    print("=" * 100)

    for job in applied:
        note = f" | {job.status_note}" if job.status_note else ""
        print(f"  - {job.title} | {job.company} | id {short_id(job.id)}{note}")


def _experience_text(job) -> str:
    min_years = job.experience_min_years
    max_years = job.experience_max_years

    if min_years is None and max_years is None:
        return "Not specified"

    if min_years is not None and max_years is not None:
        return f"{min_years} - {max_years} years"

    if min_years is not None:
        return f"{min_years}+ years"

    return f"Up to {max_years} years"


def print_details(job_objects) -> None:

    print("\n" + "=" * 100)
    print("JOBRADAR DATASET")
    print("=" * 100)

    if not job_objects:
        print("No jobs found.")
        return

    for job in job_objects:

        print(f"\n{job.title}{'   [NEW]' if job.is_new else ''}")
        print(f"Company: {job.company}")
        print(f"Id: {short_id(job.id)}   Posted/first seen: {job.age_days} days ago   Status: {job.status}")
        print(f"Found on: {job.found_on or job.site}   {job.job_url or ''}")
        print(f"Location: {job.location}")
        print(f"Match Score: {job.match_score}/100")
        print(f"Confidence: {job.confidence}")
        print(f"Coverage: {job.match_coverage}%")
        print(f"Target Category: {job.target_category or 'unknown'}")
        print(f"Target Reason: {job.target_reason or 'Not available'}")

        print(
            "Unknown dimensions: "
            f"{', '.join(job.unknown_match_dimensions) if job.unknown_match_dimensions else 'None'}"
        )

        print(f"  Role: {job.role_match_score}/100")
        print(f"  Skills: {job.skills_match_score}/100")
        print(f"  Experience: {job.experience_match_score}/100")
        print(f"  Seniority: {job.seniority_match_score}/100")

        print(f"Skills: {', '.join(job.skills) if job.skills else 'None'}")
        print(
            f"Matched skills: "
            f"{', '.join(job.matched_skills) if job.matched_skills else 'None'}"
        )
        print(
            f"Missing skills: "
            f"{', '.join(job.missing_skills) if job.missing_skills else 'None'}"
        )

        print(f"Experience requirement: {_experience_text(job)}")
        print(f"Seniority: {job.seniority or 'None'}")
        print(
            f"Application Bucket: {job.application_bucket} "
            f"({job.bucket_reason})"
        )
        print(f"Eligibility: {job.eligibility_status}")
        print(f"  Blockers: {', '.join(job.eligibility_blockers) or 'None'}")
        print(f"  Warnings: {', '.join(job.eligibility_warnings) or 'None'}")
        print(f"  Positives: {', '.join(job.eligibility_positives) or 'None'}")
        print(f"  Visa sponsorship: {job.visa_sponsorship_status} | {job.visa_sponsorship_evidence}")
        print(f"  Work authorization required: {job.work_authorization_required} | {job.work_authorization_evidence}")
        print(f"  Salary hint (max, EUR/year): {job.salary_hint_max_eur}")
        print(f"  Relocation: {job.relocation_support} | {job.relocation_evidence}")
        print(f"  German: {job.german_requirement} {job.german_level_required or ''} | {job.german_evidence}")
        print(f"  Job language: {job.job_language} | Work mode: {job.work_mode} | Remote scope: {job.remote_scope}")


def print_summary(job_objects, frame: pd.DataFrame, saved_path, tracking: dict = None) -> None:

    print(f"\nSaved {len(job_objects)} unique jobs to {saved_path}")

    for label, value in (tracking or {}).items():
        print(f"{label}: {value}")
    print(f"Columns: {len(frame.columns)}")
    print(f"Job objects created: {len(job_objects)}")

    if not job_objects:
        return

    print("\nTarget classification summary:")
    print(frame["target_category"].value_counts(dropna=False).to_string())

    print("\nApplication bucket summary:")
    print(
        pd.Series(
            [job.application_bucket for job in job_objects]
        ).value_counts().to_string()
    )