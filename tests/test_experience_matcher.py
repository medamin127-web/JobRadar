import unittest

from models import Job, Profile
from services.experience_matcher import ExperienceMatcher


class TestExperienceMatcher(unittest.TestCase):

    def setUp(self):
        self.profile = Profile(experience_years=1.25)

    def match(self, **job_fields):
        return ExperienceMatcher.match(Job(**job_fields), self.profile)

    def test_meets_minimum(self):
        result = self.match(experience_min_years=1)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["match_type"], "meets_requirement")

    def test_slightly_below(self):
        result = self.match(experience_min_years=2)
        self.assertEqual(result["score"], 75)
        self.assertEqual(result["match_type"], "slightly_below")

    def test_far_below(self):
        result = self.match(experience_min_years=5)
        self.assertEqual(result["score"], 20)
        self.assertEqual(result["match_type"], "far_below")

    def test_not_specified_is_unknown_not_zero(self):
        result = self.match()
        self.assertIsNone(result["score"])
        self.assertEqual(result["match_type"], "not_specified")

    def test_range_is_met_by_the_minimum(self):
        result = self.match(experience_min_years=1, experience_max_years=3)
        self.assertEqual(result["score"], 100)

    def test_unknown_candidate_experience_is_not_a_mismatch(self):
        result = ExperienceMatcher.match(
            Job(experience_min_years=3), Profile(experience_years=None)
        )
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
