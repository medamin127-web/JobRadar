"""
Decide what the eligibility signals mean for THIS candidate, then
combine eligibility with technical fit into an application bucket.

Design rule: eligibility is a GATE, not another weighted score.
A perfect technical match you cannot legally take is a "skip".
"""

from models import Job, Profile


# Used when a listing requires German but names no level ("German skills").
DEFAULT_REQUIRED_GERMAN_LEVEL = 3  # B1

# Below this data coverage (%), a job is sent to manual review instead of
# being recommended: the score is built on too many unknowns.
MIN_COVERAGE_TO_RECOMMEND = 60

# Yearly salary (EUR) above which a role is unlikely to be junior-level.
SENIOR_SALARY_HINT_EUR = 80000

# Below this match score a job is skipped, whatever its visa signals:
# a visa is worthless for a job you are not qualified for.
MIN_SCORE_TO_CONSIDER = 40

# apply_now also needs a clearly good technical match.
MIN_SCORE_FOR_APPLY_NOW = 60

BUCKET_ORDER = {
    "apply_now": 0,
    "apply_with_research": 1,
    "long_shot": 2,
    "review": 3,
    "skip": 4,
}


class EligibilityEvaluator:

    @classmethod
    def evaluate(cls, job: Job, profile: Profile) -> Job:
        blockers: list[str] = []
        warnings: list[str] = []
        positives: list[str] = []

        visa = job.visa_sponsorship_status
        relocation = job.relocation_support
        sponsored = visa == "yes"

        # ---------------- Visa / work authorization ----------------

        if visa == "no":
            blockers.append("NO_VISA_SPONSORSHIP")

        if visa == "mixed":
            warnings.append("VISA_STATEMENTS_CONFLICT")

        if sponsored:
            positives.append("VISA_SPONSORSHIP_OFFERED")

        if visa == "maybe":
            positives.append("VISA_SPONSORSHIP_POSSIBLE")

        if job.work_authorization_required and not sponsored:
            blockers.append("WORK_AUTHORIZATION_REQUIRED")
        elif job.work_authorization_required and sponsored:
            warnings.append("WORK_AUTHORIZATION_ALSO_MENTIONED")

        if relocation == "yes":
            positives.append("RELOCATION_SUPPORT")

        # ---------------- Remote ----------------

        worldwide_remote = (
            job.work_mode == "remote"
            and job.remote_scope == "worldwide"
        )

        if job.work_mode == "remote":
            if job.remote_scope == "worldwide":
                positives.append("REMOTE_WORLDWIDE")
            elif job.remote_scope == "emea":
                positives.append("REMOTE_EMEA")
            elif job.remote_scope == "limited_countries":
                warnings.append("REMOTE_LIMITED_COUNTRIES")
            elif job.remote_scope in ("germany_only", "eu_only"):
                if not sponsored and relocation != "yes":
                    blockers.append("REMOTE_REGION_RESTRICTED")
                else:
                    warnings.append("REMOTE_REGION_RESTRICTED")
            else:
                warnings.append("REMOTE_SCOPE_UNCLEAR")

        # ---------------- German language ----------------

        candidate_german = profile.language_level_value("German")
        requirement = job.german_requirement

        if requirement == "implied":
            # The ad is written in German but states no level. Not a
            # proven blocker, but a clear warning for a beginner.
            if candidate_german is None or candidate_german < 3:
                warnings.append("GERMAN_AD_NO_LEVEL_STATED")

        elif requirement == "required":
            required = job.german_level_value

            if candidate_german is None:
                if required is not None and required >= 5:
                    warnings.append("GERMAN_C1_PLUS_UNVERIFIED")
                else:
                    warnings.append("GERMAN_LEVEL_UNVERIFIED")
            else:
                needed = required or DEFAULT_REQUIRED_GERMAN_LEVEL
                gap = needed - candidate_german

                if gap >= 2:
                    blockers.append("GERMAN_LEVEL_TOO_HIGH")
                elif gap == 1:
                    warnings.append("GERMAN_LEVEL_STRETCH")
                else:
                    positives.append("GERMAN_LEVEL_OK")

        elif requirement in ("optional", "not_required"):
            positives.append("GERMAN_NOT_REQUIRED")

        if job.english_working_language:
            positives.append("ENGLISH_WORKING_LANGUAGE")

        if job.international_friendly:
            positives.append("INTERNATIONAL_FRIENDLY")

        # ---------------- Salary hint ----------------

        if (
            job.salary_hint_max_eur
            and job.salary_hint_max_eur >= SENIOR_SALARY_HINT_EUR
            and job.seniority != "Junior"
        ):
            warnings.append("SALARY_ABOVE_JUNIOR_RANGE")

        # ---------------- Status ----------------

        if not job.has_description:
            status = "unknown"
        elif blockers:
            status = "blocked"
        else:
            # Only an explicit visa statement (or worldwide remote work)
            # makes a job "likely". Relocation help alone is not visa
            # help: a relocation bonus is often meant for people who
            # already live in Germany.
            strong = sponsored or worldwide_remote
            medium = (
                relocation == "yes"
                or visa == "maybe"
                or job.international_friendly
                or job.english_working_language
                or (
                    job.work_mode == "remote"
                    and job.remote_scope == "emea"
                )
            )

            if strong:
                status = "possible" if warnings else "likely"
            elif medium:
                status = "possible"
            elif requirement in ("required", "implied"):
                status = "unlikely"
            else:
                # Silence is not a yes: a listing that says nothing about
                # visas stays "possible", never "likely".
                status = "possible"

        job.eligibility_status = status
        job.eligibility_blockers = blockers
        job.eligibility_warnings = warnings
        job.eligibility_positives = positives

        return job


class ApplicationBucketer:
    """
    Technical fit x eligibility -> what to do with the job.
    """

    @classmethod
    def assign(cls, job: Job) -> Job:
        coverage = job.match_coverage if job.match_coverage is not None else 0
        score = job.match_score or 0

        # Missing data must not push a job up the ranking.
        job.ranking_score = round(score * (0.6 + 0.4 * coverage / 100), 1)

        status = job.eligibility_status
        category = job.target_category

        if status == "blocked":
            bucket = "skip"
            reason = "Blocked: " + ", ".join(job.eligibility_blockers)

        elif category == "low_priority":
            bucket = "skip"
            reason = "Technical gap: " + (job.target_reason or "low priority")

        elif coverage < MIN_COVERAGE_TO_RECOMMEND:
            bucket = "review"
            reason = (
                f"Too little data extracted (coverage {coverage:.0f}%); "
                "read the listing before trusting the score."
            )

        elif score < MIN_SCORE_TO_CONSIDER:
            bucket = "skip"
            reason = (
                f"Weak technical match ({score:.0f}/100): the role or "
                "skills are outside your profile."
            )

        elif (
            status == "likely"
            and category == "good_target"
            and score >= MIN_SCORE_FOR_APPLY_NOW
            and not (
                job.experience_match_score is None
                and job.seniority_match_score is None
            )
        ):
            bucket = "apply_now"
            reason = "Good technical fit and eligibility signals are positive."

        elif status == "likely" and category == "good_target":
            bucket = "apply_with_research"
            reason = (
                "Positive eligibility, but either the match is only moderate "
                "or experience and seniority are unknown; read the listing "
                "before applying."
            )

        elif (
            status == "likely"
            and category == "needs_review"
            and score >= 55
            and (job.role_match_score or 0) >= 50
        ):
            bucket = "apply_with_research"
            reason = (
                "Strong eligibility signals (visa support) and a relevant "
                "role; seniority is unclear, so read the listing."
            )

        elif status == "likely" and category == "stretch_target" and score >= 55:
            bucket = "apply_with_research"
            reason = (
                "Stretch role (above your level) but eligibility signals are "
                "positive; worth a careful application."
            )

        elif status == "possible" and category == "good_target" and score >= 55:
            bucket = "apply_with_research"
            reason = (
                "Good technical fit; eligibility not confirmed, so check "
                "visa and language details before applying."
            )

        elif status == "possible" and category == "stretch_target":
            bucket = "long_shot"
            reason = "Stretch role and eligibility not confirmed."

        elif status == "unlikely":
            bucket = "long_shot" if category == "good_target" else "skip"
            reason = "Probably needs German or unsupported work authorization."

        else:
            bucket = "review"
            reason = "Not enough information to decide; read the listing."

        job.application_bucket = bucket
        job.bucket_reason = reason

        return job