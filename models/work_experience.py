import re
from dataclasses import dataclass, field
from typing import Optional


# Roles that are internships / student jobs rather than regular employment.
_INTERNSHIP = re.compile(
    r"\b(?:intern|internship|stagiaire|stage|praktikum|praktikant(?:in)?"
    r"|werkstudent(?:in)?|trainee)\b",
    re.IGNORECASE,
)


@dataclass
class WorkExperience:
    """
    Represents one professional experience in the candidate profile.

    Dates use the "YYYY-MM" format. An empty end_date means "present".
    """

    company: str

    role: str

    start_date: str

    end_date: Optional[str] = None

    location: Optional[str] = None

    skills: list[str] = field(
        default_factory=list
    )

    description: list[str] = field(
        default_factory=list
    )

    @property
    def is_internship(self) -> bool:
        return bool(_INTERNSHIP.search(self.role or ""))

    def to_dict(self):
        return {
            "company": self.company,
            "role": self.role,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "location": self.location,
            "skills": self.skills,
            "description": self.description,
            "is_internship": self.is_internship,
        }
