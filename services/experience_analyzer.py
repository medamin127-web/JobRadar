
import re

from models import Job


class ExperienceAnalyzer:
    """
    Extracts experience requirements from a job.

    Version 3:
    - Detects seniority primarily from the job title.
    - Extracts explicit years of professional experience
      from the job description.
    - Supports English, German and French.
    - Avoids interpreting arbitrary numbers in the description
      as years of professional experience.
    - For German, prefers explicit "Berufserfahrung" wording
      to avoid confusing company experience with candidate experience.
    """

    # ==================================================
    # SENIORITY PATTERNS
    # ==================================================

    SENIORITY_PATTERNS = {

        "Principal": [
            r"\bprincipal\b",
        ],

        "Staff": [
            r"\bstaff\s+(?:software\s+)?engineer\b",
            r"\bstaff\s+(?:software\s+)?developer\b",
        ],

        "Lead": [
            r"\btech\s+lead\b",
            r"\bteam\s+lead\b",
            r"\btechnical\s+lead\b",
            r"\blead\s+(?:software\s+)?engineer\b",
            r"\blead\s+(?:software\s+)?developer\b",
        ],

        "Senior": [
            r"\bsenior\b",
            r"\bsr\.?\b",
            r"\berfahrene[rn]?\b",
        ],

        "Junior": [
            r"\bjunior\b",
            r"\bentry[\s-]?level\b",
            r"\bgraduate\b",
            r"\bberufseinsteiger\b",
        ],

        "Intern": [
            r"\bintern\b",
            r"\binternship\b",
            r"\bstagiaire\b",
            r"\bpraktikant\b",
        ],

        "Mid": [
            r"\bmid[\s-]?level\b",
            r"\bintermediate\b",
        ],
    }

    # ==================================================
    # EXPERIENCE PATTERNS
    # ==================================================

    EXPERIENCE_PATTERNS = [

        # ---------------------------------------------
        # English
        # ---------------------------------------------

        # 5 years of experience
        # 5 years experience
        # 5+ years of experience
        r"\b(\d+(?:[.,]\d+)?)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?experience\b",

        # experience of 5 years
        r"\bexperience\s+of\s+(\d+(?:[.,]\d+)?)\s*\+?\s*years?\b",

        # at least 5 years of experience
        r"\bat\s+least\s+(\d+(?:[.,]\d+)?)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?experience\b",

        # ---------------------------------------------
        # German
        # ---------------------------------------------

        # 5 Jahre Berufserfahrung
        r"\b(\d+(?:[.,]\d+)?)\s*\+?\s*jahre?\s+berufserfahrung\b",

        # mindestens 5 Jahre Berufserfahrung
        r"\bmindestens\s+(\d+(?:[.,]\d+)?)\s*\+?\s*jahre?\s+berufserfahrung\b",

        # NOTE:
        # We intentionally do NOT match generic:
        #
        # 35 Jahre Erfahrung
        #
        # because this can describe the company's experience
        # rather than the candidate's experience.

        # ---------------------------------------------
        # French
        # ---------------------------------------------

        # 5 ans d'expérience
        r"\b(\d+(?:[.,]\d+)?)\s*\+?\s*ans?\s+d['’]expérience\b",

        # au moins 5 ans d'expérience
        r"\bau\s+moins\s+(\d+(?:[.,]\d+)?)\s*\+?\s*ans?\s+d['’]expérience\b",
    ]

    # ==================================================
    # EXPERIENCE RANGE PATTERNS
    # ==================================================

    EXPERIENCE_RANGE_PATTERNS = [

        # ---------------------------------------------
        # English
        # ---------------------------------------------

        # 3-5 years of experience
        r"\b(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)\s*years?\s+(?:of\s+)?(?:professional\s+)?experience\b",

        # 3 to 5 years of experience
        r"\b(\d+(?:[.,]\d+)?)\s+to\s+(\d+(?:[.,]\d+)?)\s*years?\s+(?:of\s+)?(?:professional\s+)?experience\b",

        # ---------------------------------------------
        # German
        # ---------------------------------------------

        # 3-5 Jahre Berufserfahrung
        r"\b(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)\s*jahre?\s+berufserfahrung\b",

        # 3 bis 5 Jahre Berufserfahrung
        r"\b(\d+(?:[.,]\d+)?)\s+bis\s+(\d+(?:[.,]\d+)?)\s*jahre?\s+berufserfahrung\b",

        # ---------------------------------------------
        # French
        # ---------------------------------------------

        # 3 à 5 ans d'expérience
        r"\b(\d+(?:[.,]\d+)?)\s*à\s*(\d+(?:[.,]\d+)?)\s*ans?\s+d['’]expérience\b",
    ]

    # ==================================================
    # ANALYZE
    # ==================================================

    def analyze(self, job: Job) -> Job:

        description = job.description or ""
        title = job.title or ""

        min_years, max_years = self.extract_years(
            description
        )

        seniority = self.extract_seniority(
            title
        )

        job.experience_min_years = min_years
        job.experience_max_years = max_years
        job.seniority = seniority

        return job

    # ==================================================
    # EXPERIENCE
    # ==================================================

    def extract_years(self, text: str):

        if not text:
            return None, None

        text = text.lower()

        # ---------------------------------------------
        # 1. Explicit ranges
        # ---------------------------------------------

        for pattern in self.EXPERIENCE_RANGE_PATTERNS:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:

                minimum = self._to_number(
                    match.group(1)
                )

                maximum = self._to_number(
                    match.group(2)
                )

                return minimum, maximum

        # ---------------------------------------------
        # 2. Explicit minimum / exact experience
        # ---------------------------------------------

        for pattern in self.EXPERIENCE_PATTERNS:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:

                years = self._to_number(
                    match.group(1)
                )

                if years is not None:
                    return years, None

        return None, None

    # ==================================================
    # SENIORITY
    # ==================================================

    def extract_seniority(self, title: str):

        if not title:
            return None

        title = title.lower()

        # More specific levels first.
        priority = [
            "Principal",
            "Staff",
            "Lead",
            "Senior",
            "Junior",
            "Intern",
            "Mid",
        ]

        for level in priority:

            patterns = self.SENIORITY_PATTERNS[level]

            for pattern in patterns:

                if re.search(
                    pattern,
                    title,
                    flags=re.IGNORECASE,
                ):
                    return level

        return None

    # ==================================================
    # HELPERS
    # ==================================================

    @staticmethod
    def _to_number(value):

        if value is None:
            return None

        try:
            return float(
                value.replace(",", ".")
            )

        except (TypeError, ValueError):
            return None

    # ==================================================
    # DEBUG
    # ==================================================

    def debug_experience_matches(self, text: str):

        if not text:
            return

        text = text.lower()

        print("\nEXPERIENCE MATCHES:")

        for pattern in (
            self.EXPERIENCE_RANGE_PATTERNS
            + self.EXPERIENCE_PATTERNS
        ):

            matches = re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            for match in matches:

                start = max(
                    0,
                    match.start() - 100
                )

                end = min(
                    len(text),
                    match.end() + 100
                )

                print("\n--- MATCH ---")

                print(
                    text[start:end]
                )

