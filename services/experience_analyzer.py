import re

from models import Job


class ExperienceAnalyzer:
    """Extract experience requirements and seniority from job listings."""

    SENIORITY_PATTERNS = {
        "Principal": [r"\bprincipal\b"],
        "Staff": [r"\bstaff\b"],
        "Lead": [
            r"\btech(?:nical)?\s+lead\b",
            r"\bteam\s+lead\b",
            r"\blead\b",
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
            r"\bpraktikant\w*\b",
            r"\bpraktikum\b",
            r"\bwerkstudent\w*\b",
            r"\bworking student\b",
            r"\bstudentische\w*\b",
            r"\bthesis\b",
            r"\babschlussarbeit\b",
        ],
        "Mid": [
            r"\bmid[\s-]?level\b",
            r"\bintermediate\b",
        ],
    }

    # Numeric values and common written-out numbers.
    NUMBER = (
        r"(one|two|three|four|five|six|seven|eight|nine|ten|"
        r"ein|eine|einen|einem|einer|zwei|drei|vier|fünf|fuenf|"
        r"sechs|sieben|acht|neun|zehn|"
        r"un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|"
        r"\d+(?:[.,]\d+)?)"
    )

    NUMBER_2 = NUMBER

    EXPERIENCE_RANGE_PATTERNS = [
        # English: 3-5 years of experience
        rf"\b{NUMBER}\s*[-–—]\s*{NUMBER_2}\s*\+?\s*years?\s+(?:(?:of\s+)?(?:professional\s+)?)experience\b",
        rf"\b{NUMBER}\s+to\s+{NUMBER_2}\s+years?\s+(?:(?:of\s+)?(?:professional\s+)?)experience\b",

        # German: 3-5 Jahre Berufserfahrung
        rf"\b{NUMBER}\s*[-–—]\s*{NUMBER_2}\s*jahre?\s+berufserfahrung\b",
        rf"\b{NUMBER}\s+bis\s+{NUMBER_2}\s*jahre?\s+berufserfahrung\b",

        # French: 3-5 ans d'expérience
        rf"\b{NUMBER}\s*[-–—]\s*{NUMBER_2}\s*ans?\s+d['’]expérience\b",
        rf"\b{NUMBER}\s+à\s+{NUMBER_2}\s*ans?\s+d['’]expérience\b",
    ]

    # Maximum experience ("no more than 12 months of experience"), used by
    # graduate programmes. Checked before the minimum patterns, which would
    # otherwise read "no more than 2 years of experience" as "2+ years".
    EXPERIENCE_CAP_PATTERNS = [
        rf"\b(?:no more than|not more than|at most|a maximum of|maximum of"
        rf"|less than|fewer than|höchstens|maximal|weniger als)\s+{NUMBER}\s*"
        rf"(months?|monate?n?|years?|jahre?n?)\b[^.!?;]{{0,80}}"
        rf"\b(?:experience|erfahrung|berufserfahrung)\b",
    ]

    EXPERIENCE_PATTERNS = [
        # English: allow words between "years" and "experience".
        # Handles "5+ years of professional backend development experience"
        # and "3+ years of ... life cycle ... operations experience".
        rf"\b(?:at\s+least\s+)?{NUMBER}\s*\+?\s*years?\s*\+?\b[^.!?;]{{0,180}}\bexperience\b",

        # Also support "experience of 5 years".
        rf"\bexperience\s+of\s+{NUMBER}\s*\+?\s*years?\s*\+?\b",

        # German: Berufserfahrung or Erfahrung, including written numbers.
        # Handles "mindestens drei Jahre Berufserfahrung"
        # and "mindestens 5 Jahre Erfahrung in der Frontend-Entwicklung".
        rf"\b(?:mindestens\s+)?{NUMBER}\s*\+?\s*jahre?\s*\+?\b[^.!?;]{{0,180}}\b(?:berufserfahrung|erfahrung)\b",

        # French: allow intervening words after "ans".
        rf"\b(?:au\s+moins\s+)?{NUMBER}\s*\+?\s*ans?\s*\+?\b[^.!?;]{{0,180}}\bexpérience\b",
    ]

    WORD_NUMBERS = {
        "one": 1, "un": 1, "une": 1,
        "ein": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1,
        "two": 2, "deux": 2, "zwei": 2,
        "three": 3, "trois": 3, "drei": 3,
        "four": 4, "quatre": 4, "vier": 4,
        "five": 5, "cinq": 5, "fünf": 5, "fuenf": 5,
        "six": 6, "sechs": 6,
        "seven": 7, "sept": 7, "sieben": 7,
        "eight": 8, "huit": 8, "acht": 8,
        "nine": 9, "neuf": 9, "neun": 9,
        "ten": 10, "dix": 10, "zehn": 10,
    }

    def analyze(self, job: Job) -> Job:
        description = job.description or ""
        title = job.title or ""

        min_years, max_years = self.extract_years(description)

        job.experience_min_years = min_years
        job.experience_max_years = max_years
        job.seniority = self.extract_seniority(title)

        return job

    def extract_years(self, text: str):
        if not text:
            return None, None

        text = re.sub(r"\s+", " ", text.lower())

        # Check ranges first so "3-5 years" isn't reduced to "3 years".
        for pattern in self.EXPERIENCE_RANGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                minimum = self._to_number(match.group(1))
                maximum = self._to_number(match.group(2))

                if (
                    minimum is not None
                    and maximum is not None
                    and minimum <= maximum
                ):
                    return minimum, maximum

        # Then a maximum ("no more than 12 months of experience").
        for pattern in self.EXPERIENCE_CAP_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                amount = self._to_number(match.group(1))

                if amount is not None:
                    if match.group(2).startswith(("month", "monat")):
                        amount = round(amount / 12, 2)

                    return None, amount

        # Then check single minimum requirements.
        for pattern in self.EXPERIENCE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                years = self._to_number(match.group(1))

                if years is not None:
                    return years, None

        return None, None

    def extract_seniority(self, title: str):
        if not title:
            return None

        title = title.lower()

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
            for pattern in self.SENIORITY_PATTERNS[level]:
                if re.search(pattern, title, re.IGNORECASE):
                    return level

        return None

    @classmethod
    def _to_number(cls, value):
        if value is None:
            return None

        value = value.strip().lower()

        if value in cls.WORD_NUMBERS:
            return float(cls.WORD_NUMBERS[value])

        try:
            return float(value.replace(",", "."))
        except (TypeError, ValueError):
            return None

    def debug_experience_matches(self, text: str):
        if not text:
            return

        text = re.sub(r"\s+", " ", text.lower())

        print("\nEXPERIENCE MATCHES:")

        for pattern in (
            self.EXPERIENCE_RANGE_PATTERNS
            + self.EXPERIENCE_CAP_PATTERNS
            + self.EXPERIENCE_PATTERNS
        ):
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)

                print("\n--- MATCH ---")
                print(text[start:end])