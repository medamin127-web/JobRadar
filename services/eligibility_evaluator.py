"""
Decide what the eligibility signals mean for THIS candidate, then
combine eligibility with technical fit into an application bucket.

Design rule: eligibility is a GATE, not another weighted score.
A perfect technical match you cannot legally take is a "skip".
"""

from countries import profile_of, skipped_location
from sources.relevance import is_tech_title, is_unpaid_title
from models import Job, Profile


# Used when a listing requires German but names no level ("German skills").
DEFAULT_REQUIRED_GERMAN_LEVEL = 3  # B1

# Below this data coverage (%), a job is sent to manual review instead of
# being recommended: the score is built on too many unknowns.
MIN_COVERAGE_TO_RECOMMEND = 60

# An ad shorter than this (characters) could not really be read: the site
# refused the text (LinkedIn 429) or the ad was removed.
SHORT_AD = 400

# An ad that states no years and no level is recommended from this skills
# score up (role score 50+ too); 50 to this = long shot; below = skipped.
UNSTATED_LEVEL_MIN_SCORE = 60

# Yearly salary (EUR) above which a role is unlikely to be junior-level.
SENIOR_SALARY_HINT_EUR = 80000

# Below this match score a job is skipped, whatever its visa signals:
# a visa is worthless for a job you are not qualified for.
MIN_SCORE_TO_CONSIDER = 40

# apply_now also needs a clearly good technical match.
MIN_SCORE_FOR_APPLY_NOW = 60

# A "Senior" title alone does not rule a job out: many senior ads state
# no years at all. A stretch job is still recommended when the score and
# the skills fit and the ad asks for at most ~1 year more than you have
# (experience score >= 75) or says nothing about years.
STRETCH_MIN_SCORE = 60
STRETCH_MIN_SKILLS = 50
STRETCH_MIN_EXPERIENCE_SCORE = 75

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

        # A remote job done from Tunisia needs no visa: what matters is
        # whether the employer hires people there (below).
        remote_job = job.country == "remote"

        if visa == "no" and remote_job:
            warnings.append("SAYS_NO_VISA_SPONSORSHIP")
        elif visa == "no":
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

        # What the job board itself says (Jaabz lists visa jobs only).
        # Weaker than the listing's own words, so only a "maybe".
        board_visa = job.source_hint == "visa" and visa == "unknown"
        board_relocation = job.source_hint == "relocation" and relocation == "unknown"

        if board_visa:
            positives.append("BOARD_LISTS_IT_AS_VISA_SPONSORED")

        if board_relocation:
            positives.append("BOARD_LISTS_IT_WITH_RELOCATION")

        # ---------------- Local hiring (mostly Gulf) ----------------

        if job.local_hire == "nationals_only":
            blockers.append("NATIONALS_ONLY")
        elif job.local_hire == "in_country_only":
            if sponsored:
                warnings.append("LOCAL_CANDIDATES_MENTIONED")
            else:
                blockers.append("LOCAL_CANDIDATES_ONLY")
        elif job.local_hire == "preferred":
            warnings.append("LOCAL_CANDIDATES_PREFERRED")

        # In the Gulf the employer normally arranges the work visa, so a
        # silent listing there is a cautious maybe (in Germany it is not).
        country = profile_of(job.country)
        employer_visa_norm = (
            country is not None
            and country.get("visa_norm") == "employer_sponsored"
            and visa == "unknown"
            and job.local_hire is None
        )

        if employer_visa_norm:
            positives.append("EMPLOYER_VISA_IS_THE_NORM_THERE")

        # ---------------- Official sponsor register (UK, NL) ----------------
        # Only registered employers can sponsor a Skilled Worker (UK) or
        # highly skilled migrant (NL) permit.

        on_register = job.sponsor_register == "listed"
        off_register = job.sponsor_register == "not_listed"

        if on_register:
            positives.append("ON_OFFICIAL_SPONSOR_REGISTER")
        elif off_register and sponsored:
            warnings.append("SAYS_SPONSOR_BUT_NOT_ON_REGISTER")
        elif off_register:
            # Only a warning: big employers often register under another
            # legal name (Deliveroo = "Roofoods Ltd"), and recruiters post
            # for clients. The job ranks lower; read the ad.
            warnings.append("NOT_FOUND_ON_SPONSOR_REGISTER")

        # ---------------- Remote ----------------

        worldwide_remote = (
            job.work_mode == "remote"
            and job.remote_scope == "worldwide"
        )

        open_to_you = remote_job and job.remote_open == "yes"

        if remote_job:
            if job.remote_open == "yes":
                positives.append("REMOTE_OPEN_TO_TUNISIA")
            elif job.remote_open == "no":
                blockers.append("REMOTE_NOT_OPEN_TO_TUNISIA")
            elif job.remote_open == "europe":
                # Tunisia shares Central European hours, but "Europe only"
                # usually means living in the EU.
                warnings.append("REMOTE_EUROPE_ONLY")
            else:
                warnings.append("REMOTE_REGION_UNCLEAR")

        elif job.work_mode == "remote":
            if job.remote_scope == "worldwide":
                positives.append("REMOTE_WORLDWIDE")
            elif job.remote_scope == "emea":
                positives.append("REMOTE_EMEA")
            elif job.remote_scope == "limited_countries":
                warnings.append("REMOTE_LIMITED_COUNTRIES")
            elif job.remote_scope in ("germany_only", "country_only", "eu_only"):
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

        # ---------------- Other languages (Arabic, Dutch...) ----------------

        for name, info in (job.other_languages or {}).items():
            flag = name.upper()
            yours = profile.language_level_value(name) or 0
            needs = info.get("requirement")

            if needs == "required":
                gap = (info.get("level_value") or 4) - yours

                if gap >= 2:
                    blockers.append(f"{flag}_REQUIRED")
                elif gap == 1:
                    warnings.append(f"{flag}_LEVEL_STRETCH")
                else:
                    positives.append(f"{flag}_REQUIRED_YOU_HAVE_IT")

            elif needs == "optional" and yours >= 4:
                positives.append(f"{flag}_IS_A_PLUS_YOU_HAVE_IT")

            elif needs == "not_required":
                positives.append(f"{flag}_NOT_REQUIRED")

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
            strong = sponsored or worldwide_remote or open_to_you
            medium = (
                on_register
                or relocation == "yes"
                or visa == "maybe"
                or board_visa
                or board_relocation
                or employer_visa_norm
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

        elif skipped_location(job.location, job.country):
            bucket = "skip"
            reason = "Region you do not target: " + skipped_location(job.location, job.country)

        elif is_unpaid_title(job.title):
            bucket = "skip"
            reason = "Volunteer / unpaid role."

        elif (
            job.title
            and not is_tech_title(job.title)
            and (job.role_match_score or 0) < 50
        ):
            # Search sites (Indeed UAE above all) also return jobs like
            # "Interior Designer" or "Planning Engineer".
            bucket = "skip"
            reason = "Not a software role (by its title)."

        elif category == "low_priority":
            bucket = "skip"
            reason = "Technical gap: " + (job.target_reason or "low priority")

        elif coverage < MIN_COVERAGE_TO_RECOMMEND and len((job.description or "").strip()) < SHORT_AD:
            # Nothing to judge: the site refused the text, or the ad is gone.
            bucket = "review"
            reason = (
                "The ad's text could not be read (the site refused it or the ad "
                "was removed); open the link to judge it yourself."
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
                ("Open to people in Tunisia (remote)" if job.country == "remote"
                 else "Strong eligibility signals (visa support)")
                + " and a relevant role; seniority is unclear, so read the listing."
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
                + ("whether they hire people in Tunisia" if job.country == "remote"
                   else "visa and language details")
                + " before applying."
            )

        elif (
            status == "possible"
            and category == "stretch_target"
            and score >= STRETCH_MIN_SCORE
            and (job.skills_match_score or 0) >= STRETCH_MIN_SKILLS
            and (
                job.experience_match_score is None
                or job.experience_match_score >= STRETCH_MIN_EXPERIENCE_SCORE
            )
        ):
            bucket = "apply_with_research"
            reason = (
                "Stretch: the title is above your level, but your skills fit "
                "and the ad asks for little or no extra experience. Worth "
                "applying; check visa and language details first."
            )

        elif status == "possible" and category == "stretch_target":
            bucket = "long_shot"
            reason = "Stretch role and eligibility not confirmed."

        elif status == "unlikely":
            bucket = "long_shot" if category == "good_target" else "skip"

            reason = "Probably needs German or a work permit you do not have."

        elif category == "needs_review" and status in ("likely", "possible"):
            # The ad states no years and no level ("Strong experience with
            # Java"): judge it on the skills and the role.
            if score >= UNSTATED_LEVEL_MIN_SCORE and (job.role_match_score or 0) >= 50:
                bucket = "apply_with_research"
                reason = (
                    "Good skills match. The ad does not say how much experience it "
                    "wants: check that"
                    + (", and whether they hire people in Tunisia," if job.country == "remote"
                       else ", and the visa side,")
                    + " before applying."
                )
            elif score >= 50 and (job.role_match_score or 0) >= 50:
                bucket = "long_shot"
                reason = "Partial skills match, and the ad does not say what level it wants."
            elif (job.role_match_score or 0) < 50 and (job.skills_match_score or 0) >= 60:
                bucket = "long_shot"
                reason = "The title is not one of your target roles, but your skills fit the ad."
            elif (job.role_match_score or 0) < 50:
                bucket = "skip"
                reason = "Not the kind of role you are looking for (by its title)."
            else:
                bucket = "skip"
                reason = f"Weak technical match ({score:.0f}/100) and no level stated."

        else:
            bucket = "review"
            reason = "Not enough information to decide; read the listing."

        job.application_bucket = bucket
        job.bucket_reason = reason

        return job