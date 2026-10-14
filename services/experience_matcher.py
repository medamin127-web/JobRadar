
from models import Job, Profile


class ExperienceMatcher:

    @staticmethod
    def match(job: Job, profile: Profile):
        """Compare candidate experience with the job requirement."""

        candidate_years = profile.experience_years
        required_min = job.experience_min_years
        required_max = job.experience_max_years

        base_result = {
            "candidate_years": candidate_years,
            "required_min_years": required_min,
            "required_max_years": required_max,
        }

        # Unknown candidate experience must not count as a mismatch.
        if candidate_years is None:
            return {
                **base_result,
                "score": None,
                "match_type": "unknown",
                "reason": "Candidate experience is not available.",
            }

        # No explicit experience requirement in the listing.
        if required_min is None and required_max is None:
            return {
                **base_result,
                "score": None,
                "match_type": "not_specified",
                "reason": "Job does not specify an experience requirement.",
            }

        # A minimum requirement is the primary signal.
        if required_min is not None:

            if candidate_years >= required_min:
                return {
                    **base_result,
                    "score": 100,
                    "match_type": "meets_requirement",
                    "reason": (
                        f"Candidate has {candidate_years:.2f} years "
                        f"and meets the minimum requirement of "
                        f"{required_min:.1f} years."
                    ),
                }

            difference = required_min - candidate_years

            # More gradual scores distinguish different experience gaps.
            if difference <= 0.5:
                score, match_type = 85, "very_close"
            elif difference <= 1:
                score, match_type = 75, "slightly_below"
            elif difference <= 2:
                score, match_type = 55, "below_requirement"
            elif difference <= 3:
                score, match_type = 35, "significantly_below"
            elif difference <= 4:
                score, match_type = 20, "far_below"
            else:
                score, match_type = 10, "very_far_below"

            return {
                **base_result,
                "score": score,
                "match_type": match_type,
                "reason": (
                    f"Candidate has {candidate_years:.2f} years, "
                    f"{difference:.2f} years below the required "
                    f"minimum of {required_min:.1f} years."
                ),
            }

        # A maximum-only requirement.
        if required_max is not None:
            if candidate_years <= required_max:
                return {
                    **base_result,
                    "score": 100,
                    "match_type": "within_range",
                    "reason": (
                        f"Candidate has {candidate_years:.2f} years, "
                        f"within the stated maximum of "
                        f"{required_max:.1f} years."
                    ),
                }

            difference = candidate_years - required_max

            return {
                **base_result,
                "score": 75 if difference <= 2 else 50,
                "match_type": (
                    "slightly_above" if difference <= 2
                    else "above_range"
                ),
                "reason": (
                    f"Candidate has {candidate_years:.2f} years, "
                    f"{difference:.2f} years above the stated "
                    f"maximum of {required_max:.1f} years."
                ),
            }
