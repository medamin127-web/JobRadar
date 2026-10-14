import unittest

from services.experience_analyzer import ExperienceAnalyzer


class TestExtractYears(unittest.TestCase):

    CASES = [
        ("Requires 3-5 years of experience.", (3.0, 5.0)),
        ("At least 5 years of professional experience.", (5.0, None)),
        ("5+ years experience required.", (5.0, None)),
        ("5+ years of professional experience.", (5.0, None)),
        ("5+ years of professional backend development experience.", (5.0, None)),
        ("7 years+ of experience in software development.", (7.0, None)),
        (
            "3+ years of full software development life cycle, including "
            "coding standards, reviews, testing, and operations experience.",
            (3.0, None),
        ),
        ("Mindestens 3 Jahre Berufserfahrung.", (3.0, None)),
        ("3-5 Jahre Berufserfahrung.", (3.0, 5.0)),
        (
            "Du hast mindestens 5 Jahre Erfahrung in der Frontend-Entwicklung.",
            (5.0, None),
        ),
        ("Mindestens drei Jahre Berufserfahrung in der Entwicklung.", (3.0, None)),
        (
            "Mindestens fünf Jahre Berufserfahrung in der Frontend-Entwicklung.",
            (5.0, None),
        ),
        ("Ca. 3-5 Jahre Berufserfahrung als Full-Stack-Entwickler.", (3.0, 5.0)),
        ("5 ans d'expérience.", (5.0, None)),
        ("No experience requirement mentioned.", (None, None)),
    ]

    def test_years(self):
        analyzer = ExperienceAnalyzer()

        for text, expected in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(analyzer.extract_years(text), expected)


class TestExtractSeniority(unittest.TestCase):

    CASES = [
        ("Senior Software Engineer", "Senior"),
        ("Staff Full Stack Developer", "Staff"),
        ("Lead Software Engineer", "Lead"),
        ("Junior Web Developer", "Junior"),
        ("Full Stack Developer", None),
    ]

    def test_seniority(self):
        analyzer = ExperienceAnalyzer()

        for title, expected in self.CASES:
            with self.subTest(title=title):
                self.assertEqual(analyzer.extract_seniority(title), expected)


if __name__ == "__main__":
    unittest.main()
