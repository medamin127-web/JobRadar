from models import Job, Profile

from .matcher import JobMatcher
from .experience_matcher import ExperienceMatcher
from .seniority_matcher import SeniorityMatcher


class MatchScorer:
    ROLE_WEIGHT = 0.30
    SKILLS_WEIGHT = 0.40
    EXPERIENCE_WEIGHT = 0.20
    SENIORITY_WEIGHT = 0.10

    # A dimension the listing says nothing about counts as neutral (50)
    # instead of being dropped. Dropping it let a job with only role +
    # 2 detected skills score 96/100.
    UNKNOWN_SCORE = 50

    # Skill matches are pulled toward 50% as if the job listed this many
    # extra skills: 2/2 matched -> 75, 8/10 matched -> 75, 0/1 -> 17.
    # A few detected skills are weak evidence; many are strong evidence.
    SKILL_PRIOR_STRENGTH = 2

    @classmethod
    def _adjusted_skills_score(cls, skills_result):
        if skills_result["score"] is None:
            return None

        matched = len(skills_result.get("matched_skills", []))
        total = matched + len(skills_result.get("missing_skills", []))

        if total == 0:
            return skills_result["score"]

        k = cls.SKILL_PRIOR_STRENGTH

        return (matched + 0.5 * k) / (total + k) * 100

    @classmethod
    def score(cls, job: Job, profile: Profile):
        role_result = JobMatcher.match_role(job, profile)
        skills_result = JobMatcher.match_skills(job, profile)
        experience_result = ExperienceMatcher.match(job, profile)
        seniority_result = SeniorityMatcher.match(job, profile)

        dimensions = [
            ("role", role_result["score"], cls.ROLE_WEIGHT),
            ("skills", cls._adjusted_skills_score(skills_result), cls.SKILLS_WEIGHT),
            ("experience", experience_result["score"], cls.EXPERIENCE_WEIGHT),
            ("seniority", seniority_result["score"], cls.SENIORITY_WEIGHT),
        ]

        available_dimensions = [
            (name, score, weight)
            for name, score, weight in dimensions
            if score is not None
        ]

        available_weight = sum(
            weight for _, _, weight in available_dimensions
        )

        coverage = round(available_weight * 100)

        if coverage >= 90:
            confidence = "high"
        elif coverage >= 70:
            confidence = "medium"
        elif coverage >= 40:
            confidence = "low"
        else:
            confidence = "very_low"

        overall_score = round(
            sum(
                (cls.UNKNOWN_SCORE if score is None else score) * weight
                for _, score, weight in dimensions
            )
        )

        return {
            "overall_score": overall_score,
            "confidence": confidence,
            "coverage": coverage,
            "available_dimensions": [
                name for name, _, _ in available_dimensions
            ],
            "unknown_dimensions": [
                name for name, score, _ in dimensions
                if score is None
            ],

            "role_score": role_result["score"],
            "skills_score": skills_result["score"],
            "experience_score": experience_result["score"],
            "seniority_score": seniority_result["score"],

            "matched_skills": skills_result.get("matched_skills", []),
            "missing_skills": skills_result.get("missing_skills", []),

            "role_match_type": role_result.get("match_type"),
            "experience_match_type": experience_result.get("match_type"),
            "seniority_match_type": seniority_result.get("match_type"),

            "role_reason": role_result.get("reason"),
            "skills_reason": skills_result.get("reason"),
            "experience_reason": experience_result.get("reason"),
            "seniority_reason": seniority_result.get("reason"),
        }