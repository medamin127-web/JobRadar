import unittest

from models import Job
from services import JobMatcher

from .helpers import make_profile


class TestRoleMatching(unittest.TestCase):

    def setUp(self):
        self.profile = make_profile()

    def role(self, title):
        return JobMatcher.match_role(Job(title=title), self.profile)

    def test_exact_target_role(self):
        for title in ["Full Stack Engineer", "Python Developer",
                      "Node.js Developer", "React Developer"]:
            with self.subTest(title=title):
                result = self.role(title)
                self.assertEqual(result["score"], 100)
                self.assertEqual(result["match_type"], "exact")

    def test_same_family(self):
        for title in ["Senior Full Stack Developer",
                      "Python Backend Developer",
                      "Angular Frontend Developer"]:
            with self.subTest(title=title):
                self.assertEqual(self.role(title)["score"], 90)

    def test_technology_role_maps_to_software_engineering(self):
        for title in ["Java Developer", "Vue.js Developer", "PHP Developer"]:
            with self.subTest(title=title):
                result = self.role(title)
                self.assertEqual(result["score"], 75)
                self.assertEqual(result["match_type"], "technology_to_software")

    def test_unrelated_role(self):
        result = self.role("Marketing Manager")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["match_type"], "no_match")

    def test_missing_title(self):
        self.assertEqual(JobMatcher.match_role(Job(), self.profile)["score"], 0)


class TestSkillMatching(unittest.TestCase):

    def setUp(self):
        self.profile = make_profile()

    def skills(self, *skills):
        return JobMatcher.match_skills(Job(skills=list(skills)), self.profile)

    def test_all_skills_match(self):
        result = self.skills("React", "Python", "Flask", "PostgreSQL", "REST API")
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["missing_skills"], [])

    def test_partial_match_lists_matched_and_missing(self):
        result = self.skills("React", "Python", "Docker", "AWS", "Kubernetes", "TypeScript")
        self.assertEqual(result["score"], 50)
        self.assertEqual(result["matched_skills"], ["python", "react", "typescript"])
        self.assertEqual(result["missing_skills"], ["aws", "docker", "kubernetes"])

    def test_no_match(self):
        self.assertEqual(self.skills("Marketing", "Sales")["score"], 0)

    def test_no_detected_skills_is_unknown_not_zero(self):
        self.assertIsNone(JobMatcher.match_skills(Job(skills=[]), self.profile)["score"])


if __name__ == "__main__":
    unittest.main()
