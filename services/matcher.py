import re

from models import Job, Profile


# Fields whose titles often contain "Software Engineer" / "Developer" but
# that are outside a web/full-stack profile. When the title names one of
# them, the generic role match is overruled. A field stops counting as
# off-target as soon as one of your target_roles mentions it.
OFF_TARGET_DOMAINS = {
    "native iOS": r"\bios\b|\bswift\b",
    "native Android": r"\bandroid\b",
    "embedded / firmware": r"\bembedded\b|\bfirmware\b",
    "flight software": r"\bflight software\b|\bavionics\b|\bspacecraft\b",
    "SAP / ABAP": r"\babap\b|\bsap\s+(?:developer|entwickler|berater|consultant|basis)",
    "mainframe": r"\bmainframe\b|\bcobol\b",
    "hardware / sensors": r"\bfpga\b|\bhardware\b|\bcalibration\b",
    "Salesforce": r"\bsalesforce\b",
}

# Cross-platform mobile titles are fine for a Flutter developer.
CROSS_PLATFORM = re.compile(r"\bflutter\b|\breact native\b", re.IGNORECASE)

OFF_TARGET_ROLE_SCORE = 15


# Skills that come with another skill you list, so you don't have to list
# the obvious ones (and they don't show up as "missing").
# Keys and values use the normalized spelling (lowercase, "-" and "/"
# become spaces).
IMPLIED_SKILLS = {
    "postgresql": ["sql"],
    "mysql": ["sql"],
    "sql server": ["sql"],
    "git": ["github", "gitlab"],
    "typescript": ["javascript"],
    "react": ["javascript", "html", "css"],
    "vue.js": ["javascript", "html", "css"],
    "angular": ["typescript", "javascript", "html", "css"],
    "next.js": ["react", "javascript"],
    "node.js": ["javascript"],
    "express.js": ["node.js", "javascript"],
    "laravel": ["php"],
    "symfony": ["php"],
    "flask": ["python"],
    "django": ["python"],
    "fastapi": ["python"],
    "spring boot": ["spring", "java"],
}


ROLE_FAMILIES = {
    "full_stack": [
        "full stack",
        "fullstack",
    ],

    "frontend": [
        "frontend",
        "front end",
        "front-end",
    ],

    "backend": [
        "backend",
        "back end",
        "back-end",
    ],

    "software_engineering": [
        "software engineer",
        "software developer",
        "software development",
        "softwareentwickler",
        "softwareentwicklerin",
        "software entwickler",
        "softwareingenieur",
        "software ingenieur",
        "anwendungsentwickler",
        "applikationsentwickler",
        "application developer",
        # At startups a "product engineer" builds the product end to end.
        "product engineer",
    ],

    "web_development": [
        "web developer",
        "website developer",
        "web engineer",
        "web application developer",
        "web app developer",
        "webentwickler",
        "webentwicklerin",
    ],

    "mobile": [
        "mobile developer",
        "mobile engineer",
        "flutter developer",
        "android developer",
        "android engineer",
        "ios developer",
        "ios engineer",
        "flutter engineer",
    ],
}


TECH_ROLE_FAMILIES = {
    "react": [
        "react developer",
        "react engineer",
        "react.js developer",
        "reactjs developer",
    ],

    "vue": [
        "vue developer",
        "vue engineer",
        "vue.js developer",
        "vuejs developer",
    ],

    "angular": [
        "angular developer",
        "angular engineer",
    ],

    "python": [
        "python developer",
        "python engineer",
        "python programmer",
        "python software developer",
        "python software engineer",
    ],

    "node": [
        "node developer",
        "node engineer",
        "node.js developer",
        "nodejs developer",
        "node.js engineer",
        "nodejs engineer",
    ],

    "java": [
        "java developer",
        "java engineer",
        "java programmer",
        "java software developer",
        "java software engineer",
    ],

    "php": [
        "php developer",
        "php engineer",
        "php programmer",
    ],

    "flutter": [
        "flutter developer",
        "flutter engineer",
    ],
}


SPECIALIZATIONS = {
    "react": [
        "react",
        "react.js",
        "reactjs",
    ],

    "vue": [
        "vue",
        "vue.js",
        "vuejs",
    ],

    "angular": [
        "angular",
    ],

    "python": [
        "python",
    ],

    "node": [
        "node",
        "node.js",
        "nodejs",
    ],

    "java": [
        "java",
    ],

    "php": [
        "php",
    ],

    "flutter": [
        "flutter",
    ],
}


RELATED_FAMILIES = {
    "full_stack": {
        "frontend",
        "backend",
        "software_engineering",
        "web_development",
    },

    "frontend": {
        "full_stack",
        "web_development",
        "software_engineering",
    },

    "backend": {
        "full_stack",
        "software_engineering",
    },

    "software_engineering": {
        "full_stack",
        "backend",
        "frontend",
        "web_development",
    },

    "web_development": {
        "full_stack",
        "frontend",
        "software_engineering",
    },

    "mobile": {
        "software_engineering",
    },
}


class JobMatcher:

    # =========================================================
    # TEXT NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize_text(value: str) -> str:

        if not value:
            return ""

        value = value.lower()

        value = value.replace("-", " ")
        value = value.replace("/", " ")

        return " ".join(value.split())

    @classmethod
    def _contains_any(cls, text: str, values: list[str]) -> bool:

        normalized_values = [
            cls._normalize_text(value)
            for value in values
        ]

        return any(
            value in text
            for value in normalized_values
        )

    # =========================================================
    # ROLE DETECTION
    # =========================================================

    @classmethod
    def _detect_role_family(cls, title: str):

        normalized_title = cls._normalize_text(title)

        # Order matters.
        # Full Stack must be checked before Frontend/Backend.
        for family, patterns in ROLE_FAMILIES.items():

            if cls._contains_any(
                normalized_title,
                patterns
            ):
                return family

        return None

    @classmethod
    def _detect_tech_role(cls, title: str):

        normalized_title = cls._normalize_text(title)

        for technology, patterns in TECH_ROLE_FAMILIES.items():

            if cls._contains_any(
                normalized_title,
                patterns
            ):
                return technology

        return None

    @classmethod
    def _detect_specializations(cls, title: str):

        normalized_title = cls._normalize_text(title)

        detected = []

        for technology, patterns in SPECIALIZATIONS.items():

            if cls._contains_any(
                normalized_title,
                patterns
            ):
                detected.append(technology)

        return detected

    @classmethod
    def _detect_candidate_role(cls, role: str):

        normalized_role = cls._normalize_text(role)

        family = cls._detect_role_family(
            normalized_role
        )

        technology = cls._detect_tech_role(
            normalized_role
        )

        specializations = cls._detect_specializations(
            normalized_role
        )

        return {
            "family": family,
            "technology": technology,
            "specializations": specializations,
        }

    # =========================================================
    # ROLE MATCHING
    # =========================================================

    @classmethod
    def match_role(cls, job: Job, profile: Profile):

        job_title = cls._normalize_text(
            job.title or ""
        )

        if not job_title:

            return {
                "score": 0,
                "matched_role": None,
                "match_type": "no_title",
                "job_family": None,
                "job_technology": None,
                "candidate_family": None,
                "candidate_technology": None,
                "reason": "Job has no title.",
            }

        job_family = cls._detect_role_family(
            job_title
        )

        job_technology = cls._detect_tech_role(
            job_title
        )

        best_match = {
            "score": 0,
            "matched_role": None,
            "match_type": "no_match",
            "job_family": job_family,
            "job_technology": job_technology,
            "candidate_family": None,
            "candidate_technology": None,
            "reason": (
                "No candidate target role "
                "matches the job title."
            ),
        }

        for candidate_role in profile.target_roles:

            candidate_info = cls._detect_candidate_role(
                candidate_role
            )

            candidate_family = candidate_info[
                "family"
            ]

            candidate_technology = candidate_info[
                "technology"
            ]

            score, match_type, reason = (
                cls._compare_role_families(
                    job_title=job_title,
                    candidate_role=candidate_role,
                    job_family=job_family,
                    candidate_family=candidate_family,
                    job_technology=job_technology,
                    candidate_technology=candidate_technology,
                )
            )

            if score > best_match["score"]:

                best_match = {
                    "score": score,
                    "matched_role": candidate_role,
                    "match_type": match_type,
                    "job_family": job_family,
                    "job_technology": job_technology,
                    "candidate_family": candidate_family,
                    "candidate_technology": candidate_technology,
                    "reason": reason,
                }

        domain = cls._off_target_domain(job.title or "", profile)

        if domain and best_match["score"] > OFF_TARGET_ROLE_SCORE:
            best_match = {
                **best_match,
                "score": OFF_TARGET_ROLE_SCORE,
                "match_type": "off_target_domain",
                "reason": (
                    f"The title points to {domain} work, which is outside "
                    "your target roles."
                ),
            }

        return best_match

    @staticmethod
    def _off_target_domain(title: str, profile: Profile):
        """Name of the off-target field the title belongs to, or None."""

        targets = " | ".join(profile.target_roles or [])

        for domain, pattern in OFF_TARGET_DOMAINS.items():
            if not re.search(pattern, title, re.IGNORECASE):
                continue

            if re.search(pattern, targets, re.IGNORECASE):
                continue

            if domain.startswith("native") and CROSS_PLATFORM.search(title):
                continue

            return domain

        return None

    @classmethod
    def expand_skills(cls, skills) -> set[str]:
        """Your skills plus the ones they imply (normalized names)."""

        expanded = {
            cls._normalize_text(skill)
            for skill in skills or []
            if skill
        }

        for skill in list(expanded):
            expanded.update(IMPLIED_SKILLS.get(skill, []))

        return expanded

    @classmethod
    def _compare_role_families(
        cls,
        job_title: str,
        candidate_role: str,
        job_family,
        candidate_family,
        job_technology,
        candidate_technology,
    ):

        normalized_candidate = cls._normalize_text(
            candidate_role
        )

        # -----------------------------------------------------
        # 1. Exact title
        # -----------------------------------------------------

        if job_title == normalized_candidate:

            return (
                100,
                "exact",
                "Job title exactly matches a candidate target role.",
            )

        # -----------------------------------------------------
        # 2. Same technology-specific role
        #
        # Example:
        # Python Developer
        # Python Developer
        # -----------------------------------------------------

        if (
            job_technology
            and candidate_technology
            and job_technology == candidate_technology
        ):

            return (
                95,
                "technology_role",
                (
                    f"Both roles are "
                    f"{job_technology}-specific developer roles."
                ),
            )

        # -----------------------------------------------------
        # 3. Same broad family
        # -----------------------------------------------------

        if (
            job_family
            and candidate_family
            and job_family == candidate_family
        ):

            if (
                job_technology
                and candidate_technology
                and job_technology == candidate_technology
            ):

                return (
                    95,
                    "family_specialization",
                    (
                        "Job and candidate role share "
                        "the same family and technology "
                        "specialization."
                    ),
                )

            return (
                90,
                "same_family",
                (
                    "Job and candidate role belong "
                    "to the same role family."
                ),
            )

        # -----------------------------------------------------
        # 4. Technology-specific role -> Software Engineer
        #
        # Java Developer
        #        ↓
        # Software Engineer
        # -----------------------------------------------------

        if (
            job_technology
            and candidate_family == "software_engineering"
        ):

            return (
                75,
                "technology_to_software",
                (
                    "Technology-specific developer role "
                    "is related to software engineering."
                ),
            )

        if (
            candidate_technology
            and job_family == "software_engineering"
        ):

            return (
                75,
                "software_to_technology",
                (
                    "Software engineering role is related "
                    "to the candidate's technology-specific role."
                ),
            )

        # -----------------------------------------------------
        # 5. Related families
        # -----------------------------------------------------

        if (
            job_family
            and candidate_family
            and candidate_family
            in RELATED_FAMILIES.get(
                job_family,
                set()
            )
        ):

            return (
                65,
                "related_family",
                (
                    "Job and candidate role belong "
                    "to related role families."
                ),
            )

        return (
            0,
            "no_match",
            (
                "Job and candidate role are not "
                "sufficiently related."
            ),
        )

    # =========================================================
    # SKILL MATCHING
    # =========================================================

    @classmethod
    def match_skills(
        cls,
        job: Job,
        profile: Profile
    ):

        job_skills = {
            cls._normalize_text(skill)
            for skill in (job.skills or [])
            if skill
        }

        candidate_skills = cls.expand_skills(profile.skills)

        if not job_skills:

            return {
                "score": None,
                "matched_skills": [],
                "missing_skills": [],
                "match_type": "not_specified",
                "reason": "No job skills were detected.",
            }

        matched_skills = sorted(
            job_skills.intersection(
                candidate_skills
            )
        )

        missing_skills = sorted(
            job_skills - candidate_skills
        )

        score = round(
            len(matched_skills)
            / len(job_skills)
            * 100
        )

        if score == 100:

            reason = (
                "All detected job skills match "
                "the candidate profile."
            )

        elif score == 0:

            reason = (
                "No candidate skills match the job."
            )

        else:

            reason = (
                f"{len(matched_skills)} of "
                f"{len(job_skills)} job skills "
                f"match the candidate profile."
            )

        return {
            "score": score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "reason": reason,
        }