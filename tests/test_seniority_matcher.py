import unittest

from models import Job, Profile
from services.seniority_matcher import SeniorityMatcher


class TestSeniorityMatcher(unittest.TestCase):
    """A candidate with 1.25 years is estimated as junior."""

    def setUp(self):
        self.profile = Profile(experience_years=1.25)

    def match(self, seniority):
        return SeniorityMatcher.match(Job(seniority=seniority), self.profile)

    def test_levels(self):
        cases = [
            ("junior", 100, "same_level"),
            ("mid", 75, "adjacent_level"),
            ("senior", 50, "two_levels_apart"),
            ("lead", 25, "large_mismatch"),
            ("principal", 25, "large_mismatch"),
        ]

        for level, score, match_type in cases:
            with self.subTest(level=level):
                result = self.match(level)
                self.assertEqual(result["score"], score)
                self.assertEqual(result["match_type"], match_type)
                self.assertEqual(result["candidate_seniority"], "junior")

    def test_unknown_job_level_is_unknown_not_zero(self):
        result = self.match(None)
        self.assertIsNone(result["score"])
        self.assertEqual(result["match_type"], "not_specified")


if __name__ == "__main__":
    unittest.main()
