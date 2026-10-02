from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Job:
    """
    Normalized JobRadar representation of a job listing.
    """

    # -------------------------------
    # Identity
    # -------------------------------

    id: Optional[str] = None
    site: Optional[str] = None

    # -------------------------------
    # Basic information
    # -------------------------------

    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None

    job_url: Optional[str] = None
    job_url_direct: Optional[str] = None

    date_posted: Optional[str] = None

    # -------------------------------
    # Employment
    # -------------------------------

    job_type: Optional[str] = None
    is_remote: Optional[bool] = None
    work_from_home_type: Optional[str] = None

    job_level: Optional[str] = None
    job_function: Optional[str] = None

    # -------------------------------
    # Salary
    # -------------------------------

    salary_source: Optional[str] = None
    interval: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: Optional[str] = None

    # -------------------------------
    # Requirements
    # -------------------------------

    description: Optional[str] = None
    skills: Optional[list[str]] = None
    experience_range: Optional[str] = None
    experience_min_years: Optional[float] = None
    experience_max_years: Optional[float] = None
    seniority: Optional[str] = None


    # -------------------------------
    # Company
    # -------------------------------

    company_industry: Optional[str] = None
    company_url: Optional[str] = None
    company_description: Optional[str] = None

    # -------------------------------
    # JobRadar metadata
    # -------------------------------

    search_term: Optional[str] = None

    def to_dict(self):
        """
        Convert the Job object into a dictionary.
        """
        return asdict(self)