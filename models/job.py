from dataclasses import dataclass, asdict
from dataclasses import field
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


    match_score: Optional[float] = None
    
    role_match_score: Optional[float] = None
    skills_match_score: Optional[float] = None
    experience_match_score: Optional[float] = None
    seniority_match_score: Optional[float] = None

    matched_skills: Optional[list[str]] = None
    missing_skills: Optional[list[str]] = None
    
    confidence: Optional[str] = None
    
    
    # -------------------------------
    # Target classification
    # -------------------------------

    target_category: Optional[str] = None
    target_reason: Optional[str] = None
    application_priority: str | None = None
    
    # -------------------------------
    # Match metadata
    # -------------------------------

    match_coverage: Optional[float] = None
    unknown_match_dimensions: Optional[list[str]] = None

    # -------------------------------
    # Eligibility signals (extracted from the listing)
    # -------------------------------

    job_language: Optional[str] = None  # de | en | mixed

    german_requirement: Optional[str] = None
    german_level_required: Optional[str] = None
    german_level_value: Optional[int] = None
    german_evidence: Optional[str] = None
    english_working_language: Optional[bool] = None

    visa_sponsorship_status: Optional[str] = None  # yes | no | mixed | unknown
    visa_sponsorship_evidence: Optional[str] = None
    work_authorization_required: Optional[bool] = None
    work_authorization_evidence: Optional[str] = None

    relocation_support: Optional[str] = None  # yes | no | unknown
    relocation_evidence: Optional[str] = None

    work_mode: Optional[str] = None  # remote | hybrid | unclear
    remote_scope: Optional[str] = None
    international_friendly: Optional[bool] = None
    has_description: Optional[bool] = None
    salary_hint_max_eur: Optional[float] = None

    # -------------------------------
    # Eligibility decision (depends on the candidate)
    # -------------------------------

    eligibility_status: Optional[str] = None
    eligibility_blockers: list[str] = field(default_factory=list)
    eligibility_warnings: list[str] = field(default_factory=list)
    eligibility_positives: list[str] = field(default_factory=list)

    application_bucket: Optional[str] = None
    bucket_reason: Optional[str] = None
    ranking_score: Optional[float] = None
    
     
    def to_dict(self):
        """
        Convert the Job object into a dictionary.
        """
        return asdict(self)