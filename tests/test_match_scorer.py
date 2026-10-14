import unittest

from models import Job
from services.match_scorer import MatchScorer

from .helpers import make_profile


class TestMatchScorer(unittest.TestCase):

    def setUp(self):
        self.profile = make_profile()

    def test_junior_job_that_fits_scores_high(self):
        job = Job(
            title="Junior Full Stack Developer",
            seniority="junior",
            experience_min_years=1,
            skills=["React", "Python", "Flask", "PostgreSQL"],
        )

        result = MatchScorer.score(job, self.profile)

        self.assertEqual(result["overall_score"], 97)
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["coverage"], 100)
        self.assertEqual(result["missing_skills"], [])

    def test_senior_job_with_many_gaps_scores_low(self):
        job = Job(
            title="Senior React Developer",
            seniority="senior",
            experience_min_years=5,
            skills=["React", "TypeScript", "Next.js", "Docker", "AWS"],
        )

        result = MatchScorer.score(job, self.profile)

        self.assertEqual(result["overall_score"], 54)
        self.assertEqual(result["matched_skills"], ["react", "typescript"])
        self.assertEqual(result["experience_score"], 20)

    def test_unrelated_job_scores_very_low(self):
        job = Job(
            title="Marketing Manager",
            seniority="mid",
            experience_min_years=3,
            skills=["Marketing", "SEO", "Google Ads"],
        )

        result = MatchScorer.score(job, self.profile)

        self.assertLess(result["overall_score"], 25)
        self.assertEqual(result["role_score"], 0)
        self.assertEqual(result["skills_score"], 0)

    def test_unknown_dimensions_lower_the_coverage(self):
        job = Job(title="Software Engineer")  # no skills, years or seniority

        result = MatchScorer.score(job, self.profile)

        self.assertEqual(result["coverage"], 30)
        self.assertEqual(result["confidence"], "very_low")
        self.assertEqual(
            sorted(result["unknown_dimensions"]),
            ["experience", "seniority", "skills"],
        )


if __name__ == "__main__":
    unittest.main()
