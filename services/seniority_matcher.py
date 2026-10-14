from models import Job, Profile


SENIORITY_LEVELS = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "staff": 4,
    "principal": 5,
}


class SeniorityMatcher:

    @staticmethod
    def _normalize_level(level):
        """
        Normalize different seniority names.
        """

        if not level:
            return None

        level = level.lower().strip()

        aliases = {
            "entry": "junior",
            "entry level": "junior",
            "entry-level": "junior",

            "graduate": "junior",

            "mid-level": "mid",
            "mid level": "mid",
            "middle": "mid",

            "sr": "senior",

            "lead": "lead",
            "team lead": "lead",

            "staff": "staff",

            "principal": "principal",
        }

        return aliases.get(level, level)

    @classmethod
    def _level_value(cls, level):

        level = cls._normalize_level(level)

        if level is None:
            return None

        return SENIORITY_LEVELS.get(level)

    @classmethod
    def match(
        cls,
        job: Job,
        profile: Profile,
    ):
        """
        Compare job seniority with candidate experience.

        The first version uses the candidate's total
        experience as the primary signal.
        """

        job_level = cls._normalize_level(
            job.seniority
        )

        # --------------------------------------------------
        # Job has no detected seniority
        # --------------------------------------------------

        if job_level is None:

            return {
                "score": None,
                "job_seniority": None,
                "candidate_seniority": None,
                "match_type": "not_specified",
                "reason": (
                    "Job seniority could not be determined."
                ),
            }

        candidate_years = profile.experience_years

        if candidate_years is None:
            return {
                "score": None,
                "job_seniority": job_level,
                "candidate_seniority": None,
                "match_type": "unknown",
                "reason": (
                    "Candidate experience is not available; "
                    "seniority compatibility cannot be assessed."
                ),
            }

        # --------------------------------------------------
        # Estimate candidate seniority from experience
        #
        # This is intentionally conservative.
        # --------------------------------------------------

        if candidate_years < 1:

            candidate_level = "intern"

        elif candidate_years < 2:

            candidate_level = "junior"

        elif candidate_years < 5:

            candidate_level = "mid"

        elif candidate_years < 8:

            candidate_level = "senior"

        else:

            candidate_level = "lead"

        job_value = cls._level_value(
            job_level
        )

        candidate_value = cls._level_value(
            candidate_level
        )

        # --------------------------------------------------
        # Unknown job level
        # --------------------------------------------------

        if job_value is None:

            return {
                "score": 100,
                "job_seniority": job_level,
                "candidate_seniority": candidate_level,
                "match_type": "unknown_job_level",
                "reason": (
                    "Job seniority was detected but "
                    "is not recognized by the matcher."
                ),
            }

        # --------------------------------------------------
        # Exact level
        # --------------------------------------------------

        if job_value == candidate_value:

            return {
                "score": 100,
                "job_seniority": job_level,
                "candidate_seniority": candidate_level,
                "match_type": "same_level",
                "reason": (
                    f"Job is {job_level}-level and the "
                    f"candidate is estimated at {candidate_level}-level."
                ),
            }

        difference = abs(
            job_value - candidate_value
        )

        # --------------------------------------------------
        # One level apart
        # --------------------------------------------------

        if difference == 1:

            return {
                "score": 75,
                "job_seniority": job_level,
                "candidate_seniority": candidate_level,
                "match_type": "adjacent_level",
                "reason": (
                    f"Job is {job_level}-level while the "
                    f"candidate is estimated at "
                    f"{candidate_level}-level."
                ),
            }

        # --------------------------------------------------
        # Two levels apart
        # --------------------------------------------------

        if difference == 2:

            return {
                "score": 50,
                "job_seniority": job_level,
                "candidate_seniority": candidate_level,
                "match_type": "two_levels_apart",
                "reason": (
                    f"Job is {job_level}-level while the "
                    f"candidate is estimated at "
                    f"{candidate_level}-level."
                ),
            }

        # --------------------------------------------------
        # Large mismatch
        # --------------------------------------------------

        return {
            "score": 25,
            "job_seniority": job_level,
            "candidate_seniority": candidate_level,
            "match_type": "large_mismatch",
            "reason": (
                f"Job is {job_level}-level while the "
                f"candidate is estimated at "
                f"{candidate_level}-level."
            ),
        }