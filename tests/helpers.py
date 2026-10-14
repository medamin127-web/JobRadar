"""Shared test fixtures. Tests never depend on your real candidate_profile.py."""

from models import Language, Profile


def make_profile(**overrides) -> Profile:
    values = dict(
        name="Test Candidate",
        experience_years=1.25,
        target_roles=[
            "Full Stack Developer",
            "Full Stack Engineer",
            "Software Engineer",
            "Web Developer",
            "Frontend Developer",
            "Backend Developer",
            "React Developer",
            "Python Developer",
            "Node.js Developer",
        ],
        skills=[
            "React", "Vue.js", "Node.js", "Flask", "Laravel", "Symfony",
            "JavaScript", "TypeScript", "HTML", "CSS", "Python", "PHP",
            "Java", "PostgreSQL", "MongoDB", "MySQL", "Neo4j", "Flutter",
            "Git", "Linux", "REST API",
        ],
        languages=[
            Language(name="English", level="C1"),
            Language(name="German", level="A2"),
        ],
    )
    values.update(overrides)

    return Profile(**values)
