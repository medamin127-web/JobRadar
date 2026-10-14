
import unittest
from types import SimpleNamespace

from services.target_classifier import TargetClassifier
from services.experience_matcher import ExperienceMatcher
from services.seniority_matcher import SeniorityMatcher


class TestTargetClassifier(unittest.TestCase):

    def setUp(self):
        """Create a candidate profile for each test."""
        self.profile = SimpleNamespace(
            experience_years=1.25
        )

    def make_job(
        self,
        experience_min_years=None,
        experience_max_years=None,
        seniority=None,
    ):
        """Create a simple job object for testing."""
        return SimpleNamespace(
            experience_min_years=experience_min_years,
            experience_max_years=experience_max_years,
            seniority=seniority,
        )

    def classify(self, job, profile=None):
        """Run the classifier with the matcher results."""
        if profile is None:
            profile = self.profile

        experience_result = ExperienceMatcher.match(
            job, profile
        )

        seniority_result = SeniorityMatcher.match(
            job, profile
        )

        return TargetClassifier.classify(
            job,
            profile,
            experience_result,
            seniority_result,
        )

    # --------------------------------------------------
    # Experience requirement tests
    # --------------------------------------------------

    def test_meets_minimum_experience(self):
        job = self.make_job(
            experience_min_years=1,
            seniority="junior",
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "good_target")

    def test_small_experience_gap_is_good_target(self):
        job = self.make_job(
            experience_min_years=1.5,
            seniority="junior",
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "good_target")

    def test_moderate_experience_gap_is_stretch_target(self):
        job = self.make_job(
            experience_min_years=3,
            seniority="mid",
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "stretch_target")

    def test_large_experience_gap_is_low_priority(self):
        job = self.make_job(
            experience_min_years=5,
            seniority="senior",
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "low_priority")

    def test_no_experience_requirement_uses_seniority(self):
        job = self.make_job(
            seniority="junior"
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "good_target")

    # --------------------------------------------------
    # Seniority tests
    # --------------------------------------------------

    def test_senior_job_is_stretch_target(self):
        job = self.make_job(
            seniority="senior"
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "stretch_target")

    def test_principal_job_is_low_priority(self):
        job = self.make_job(
            seniority="principal"
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "low_priority")

    def test_unknown_seniority_and_no_experience_is_needs_review(self):
        job = self.make_job()

        result = self.classify(job)

        self.assertEqual(result["target_category"], "needs_review")

    # --------------------------------------------------
    # Missing candidate information
    # --------------------------------------------------

    def test_unknown_candidate_experience_needs_review(self):
        profile = SimpleNamespace(
            experience_years=None
        )

        job = self.make_job(
            experience_min_years=2,
            seniority="junior",
        )

        result = self.classify(job, profile)

        self.assertEqual(result["target_category"], "needs_review")

    # --------------------------------------------------
    # Boundary tests
    # --------------------------------------------------

    def test_experience_gap_of_three_years_is_low_priority(self):
        job = self.make_job(
            experience_min_years=4.25,
            seniority="mid",
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "low_priority")

    def test_experience_gap_just_below_three_years_is_stretch(self):
        job = self.make_job(
            experience_min_years=4.24,
            seniority="mid",
        )

        result = self.classify(job)

        self.assertEqual(result["target_category"], "stretch_target")


if __name__ == "__main__":
    unittest.main(verbosity=2)
