"""
Template profile. Copy this file to candidate_profile.py and fill in your
own details. candidate_profile.py is git-ignored so your personal data
never goes into the repository.

    copy candidate_profile.example.py candidate_profile.py      (PowerShell)
"""

from models import Language, Profile, WorkExperience


PROFILE = Profile(
    name="Your Name",
    current_country="Your country",

    # Job titles you want. Used to score how well a posting's title fits.
    target_roles=[
        "Full Stack Developer",
        "Software Engineer",
        "Web Developer",
    ],

    # experience_years is computed from work_history below
    # (regular jobs only, internships excluded). You can still set
    # experience_years=2.5 here to override it.

    work_history=[
        WorkExperience(
            company="Example Company",
            role="Full Stack Developer",
            start_date="2024-01",   # YYYY-MM
            end_date=None,          # None = still working here
            location="City, Country",
            skills=["React", "Python"],
            description=["What you built there."],
        ),
        WorkExperience(
            company="Another Company",
            role="Full Stack Developer Intern",   # "intern" in the role
            start_date="2023-06",                 # = counted as internship,
            end_date="2023-09",                   # not as professional years
        ),
    ],

    # Spelling matters: use the names JobRadar detects in job posts
    # (see SKILL_PATTERNS in services/job_analyzer.py).
    skills=[
        "React",
        "TypeScript",
        "JavaScript",
        "HTML",
        "CSS",
        "Python",
        "PostgreSQL",
        "Git",
        "REST API",
    ],

    education=["Your degree"],
    certifications=["Your certificate"],

    # Levels use CEFR: A1, A2, B1, B2, C1, C2 or Native.
    # The German level decides which German-language jobs are blocked.
    languages=[
        Language(name="English", level="C1", certification="TOEIC"),
        Language(name="German", level="A2"),
    ],

    relocation=True,
    remote=True,
)
