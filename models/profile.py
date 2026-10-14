import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .work_experience import WorkExperience
from .language import Language
from .cefr import parse_level


_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


def _month_index(value: str) -> int:
    """
    Convert "YYYY-MM" into a month counter.
    """

    match = _MONTH.match(str(value).strip())

    if not match or not 1 <= int(match.group(2)) <= 12:
        raise ValueError(
            f"Invalid date {value!r}: use the YYYY-MM format "
            '(for example "2025-07").'
        )

    return int(match.group(1)) * 12 + (int(match.group(2)) - 1)


def _span(start_date: str, end_date: Optional[str], today: date):
    """
    Months [start, end) covered by a role.

    A finished role counts its last month ("2025-02" to "2025-06" is
    5 months, so a job starting in "2025-07" follows it with no gap).
    A role with no end date runs up to the current month.
    """

    start = _month_index(start_date)

    if end_date is None:
        end = today.year * 12 + (today.month - 1)
    else:
        end = _month_index(end_date) + 1

    return start, end


def _merged_months(spans: list[tuple[int, int]]) -> int:
    """
    Total months covered by the spans, counting overlaps only once.
    """

    total = 0
    current_start = None
    current_end = None

    for start, end in sorted(spans):
        if end <= start:
            continue

        if current_end is None or start > current_end:
            if current_end is not None:
                total += current_end - current_start

            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)

    if current_end is not None:
        total += current_end - current_start

    return total


@dataclass
class Profile:
    """
    JobRadar representation of the candidate profile.
    """

    # ==================================================
    # IDENTITY / LOCATION
    # ==================================================

    name: Optional[str] = None

    current_country: Optional[str] = None

    # ==================================================
    # TARGET ROLES
    # ==================================================

    target_roles: list[str] = field(
        default_factory=list
    )

    # ==================================================
    # EXPERIENCE
    # ==================================================

    # Years of professional experience used for matching.
    #
    # Leave it as None and it is computed from work_history
    # (regular jobs only, internships excluded). Set a number
    # only if you want to override the computed value.
    experience_years: Optional[float] = None

    work_history: list[WorkExperience] = field(
        default_factory=list
    )

    # ==================================================
    # TECHNICAL SKILLS
    # ==================================================

    skills: list[str] = field(
        default_factory=list
    )

    # ==================================================
    # EDUCATION
    # ==================================================

    education: list[str] = field(
        default_factory=list
    )

    # ==================================================
    # CERTIFICATIONS
    # ==================================================

    certifications: list[str] = field(
        default_factory=list
    )

    # ==================================================
    # LANGUAGES
    # ==================================================

    languages: list[Language] = field(
        default_factory=list
    )

    # ==================================================
    # PREFERENCES
    # ==================================================

    relocation: bool = True

    remote: bool = True

    def __post_init__(self):
        if self.experience_years is None and self.work_history:
            self.experience_years = self.professional_years()

    # ==================================================
    # EXPERIENCE FROM DATES
    # ==================================================

    def _years(self, internships: Optional[bool], today: Optional[date]) -> float:
        today = today or date.today()

        spans = [
            _span(job.start_date, job.end_date, today)
            for job in self.work_history
            if internships is None or job.is_internship == internships
        ]

        return round(_merged_months(spans) / 12, 2)

    def professional_years(self, today: Optional[date] = None) -> float:
        """Years in regular jobs (internships excluded)."""
        return self._years(False, today)

    def internship_years(self, today: Optional[date] = None) -> float:
        """Years spent in internships."""
        return self._years(True, today)

    def total_years(self, today: Optional[date] = None) -> float:
        """Every role together, overlaps counted once."""
        return self._years(None, today)

    def language_level_value(self, name: str) -> Optional[int]:
        """
        CEFR level of a language as a number (A1=1 ... C2=6),
        or None when the level is not filled in.
        """

        for language in self.languages:
            if language.name.lower() == name.lower():
                return parse_level(language.level)

        return None

    def to_dict(self):
        return {
            "name": self.name,
            "current_country": self.current_country,
            "target_roles": self.target_roles,
            "experience_years": self.experience_years,
            "internship_years": self.internship_years(),
            "total_years": self.total_years(),
            "work_history": [
                experience.to_dict()
                for experience in self.work_history
            ],
            "skills": self.skills,
            "education": self.education,
            "certifications": self.certifications,
            "languages": [
                language.to_dict()
                for language in self.languages
            ],
            "relocation": self.relocation,
            "remote": self.remote,
        }
