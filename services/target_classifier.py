from models import Job, Profile

from .seniority_matcher import SeniorityMatcher


class TargetClassifier:
    """
    Classify how realistic a job is for the candidate.

    Categories:
        good_target
        stretch_target
        low_priority
        needs_review

    Application priority is a separate recommendation:
        high
        medium
        low
    """

    @classmethod
    def classify(
        cls,
        job: Job,
        profile: Profile,
        experience_result: dict,
        seniority_result: dict,
    ) -> dict:

        candidate_years = profile.experience_years
        
        if candidate_years is None:
            return {
                "target_category": "needs_review",
                "target_reason": (
                    "Candidate experience is unavailable, so the job's "
                    "realistic fit needs manual review."
                ),
                "application_priority": "low",
            }
            
        required_min = job.experience_min_years
        required_max = getattr(job, "experience_max_years", None)

        job_level = SeniorityMatcher._normalize_level(job.seniority)
        candidate_level = seniority_result.get("candidate_seniority")

        job_value = SeniorityMatcher._level_value(job_level)
        candidate_value = SeniorityMatcher._level_value(candidate_level)

        role_score = getattr(job, "role_match_score", None)
        skills_score = getattr(job, "skills_match_score", None)
        match_score = getattr(job, "match_score", None)

        # Use technical alignment only as supporting evidence.
        technical_scores = [
            score
            for score in (role_score, skills_score)
            if score is not None
        ]
        technical_alignment = (
            sum(technical_scores) / len(technical_scores)
            if technical_scores
            else None
        )

        category = None
        reason = None

        # 1. Explicit experience requirements take precedence.

        # A maximum alone is a cap (graduate programmes): above it,
        # the job is not open to you.
        if (
            required_min is None
            and required_max is not None
            and candidate_years > required_max
        ):
            category = "low_priority"
            reason = (
                f"The job accepts at most {required_max:g} years of "
                f"experience; you have {candidate_years:g}."
            )

        # Internships and student jobs need you to be enrolled at a
        # university; you have graduated.
        if category is None and job_level == "intern":
            category = "low_priority"
            reason = (
                "Internship / working-student position: these require "
                "being enrolled as a student."
            )

        if (
            category is None
            and candidate_years is not None
            and required_min is not None
        ):
            gap = required_min - candidate_years

            if gap >= 3:
                category = "low_priority"
                reason = (
                    f"The job requires at least {required_min:g} years, "
                    f"versus your {candidate_years:g} years."
                )

            elif gap >= 0.5:
                category = "stretch_target"
                reason = (
                    f"You are {gap:.1f} years below the stated "
                    "minimum experience requirement."
                )

        # 2. If experience did not decide the result, compare seniority.
        if category is None and (
            job_value is not None and candidate_value is not None
        ):
            seniority_gap = job_value - candidate_value

            if seniority_gap >= 3:
                category = "low_priority"
                reason = (
                    "The job seniority is significantly above "
                    "your current career level."
                )

            elif seniority_gap >= 1:
                category = "stretch_target"
                reason = "The job seniority is above your current career level."

        # 3. When requirements are unclear, use role and skill alignment.
        if category is None:
            requirements_unknown = (
                required_min is None and job_value is None
            )

            if requirements_unknown:
                if (
                    role_score is not None
                    and skills_score is not None
                    and role_score >= 70
                    and skills_score >= 60
                ):
                    category = "good_target"
                    reason = (
                        "The role and skills align well with your profile, "
                        "and no major experience or seniority mismatch "
                        "was detected. Verify the full job description."
                    )

                elif (
                    technical_alignment is not None
                    and technical_alignment >= 75
                ):
                    category = "needs_review"
                    reason = (
                        "Technical alignment looks promising, but there "
                        "is not enough information about experience or "
                        "seniority to classify this confidently."
                    )

                else:
                    category = "needs_review"
                    reason = (
                        "Experience or seniority requirements are unclear, "
                        "and the available technical evidence is not "
                        "strong enough for a confident classification."
                    )

            elif (
                technical_alignment is not None
                and technical_alignment < 50
            ):
                # Level fits, but the job is in another field
                # (e.g. a junior iOS role for a web developer).
                category = "needs_review"
                reason = (
                    "Your level fits, but the role and skills overlap "
                    "with your profile is weak."
                )

            else:
                category = "good_target"
                reason = (
                    "No major experience gap or seniority mismatch "
                    "was detected by the current rules."
                )

        # 4. Application priority is distinct from target category.
        if category == "low_priority":
            priority = "low"

        elif category == "good_target":
            priority = (
                "high"
                if match_score is not None and match_score >= 70
                else "medium"
            )

        elif category == "stretch_target":
            priority = (
                "high"
                if (
                    match_score is not None
                    and match_score >= 75
                    and technical_alignment is not None
                    and technical_alignment >= 70
                )
                else "medium"
            )

        else:  # needs_review
            priority = (
                "medium"
                if match_score is not None and match_score >= 70
                else "low"
            )

        return {
            "target_category": category,
            "target_reason": reason,
            "application_priority": priority,
        }