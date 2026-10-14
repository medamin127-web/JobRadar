import unittest
from datetime import date

from models import Language, Profile, WorkExperience

from .helpers import make_profile


def job(role, start, end=None):
    return WorkExperience(company="X", role=role, start_date=start, end_date=end)


class TestExperienceFromDates(unittest.TestCase):

    TODAY = date(2026, 10, 14)

    def test_finished_role_counts_its_last_month(self):
        profile = Profile(work_history=[job("Developer", "2025-02", "2025-06")])

        self.assertEqual(profile.professional_years(self.TODAY), 0.42)  # 5 months

    def test_current_job_runs_until_today(self):
        profile = Profile(work_history=[job("Full Stack Developer", "2025-07")])

        self.assertEqual(profile.professional_years(self.TODAY), 1.25)

    def test_internships_are_not_professional_experience(self):
        profile = Profile(work_history=[
            job("Full Stack Developer", "2025-07"),
            job("Full Stack Developer Intern", "2025-02", "2025-06"),
            job("Stagiaire développeur", "2023-06", "2023-09"),
        ])

        self.assertEqual(profile.professional_years(self.TODAY), 1.25)
        self.assertEqual(profile.internship_years(self.TODAY), 0.75)  # 5 + 4 months
        self.assertEqual(profile.total_years(self.TODAY), 2.0)        # 24 months

    def test_overlapping_roles_are_counted_once(self):
        profile = Profile(work_history=[
            job("Developer", "2024-01", "2024-12"),
            job("Developer", "2024-07", "2025-06"),
        ])

        self.assertEqual(profile.professional_years(self.TODAY), 1.5)

    def test_experience_years_is_computed_when_not_given(self):
        profile = Profile(work_history=[job("Developer", "2020-01", "2021-12")])

        self.assertEqual(profile.experience_years, 2.0)

    def test_explicit_experience_years_wins(self):
        profile = Profile(
            experience_years=3,
            work_history=[job("Developer", "2020-01", "2021-12")],
        )

        self.assertEqual(profile.experience_years, 3)

    def test_unknown_when_there_is_no_history(self):
        self.assertIsNone(Profile().experience_years)

    def test_bad_date_gives_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM"):
            Profile(work_history=[job("Developer", "07/2025")])


class TestLanguages(unittest.TestCase):

    def test_levels_are_numbers(self):
        profile = Profile(languages=[
            Language(name="Arabic", level="Native"),
            Language(name="English", level="C1"),
            Language(name="German", level="A2"),
            Language(name="French"),
        ])

        self.assertEqual(profile.language_level_value("Arabic"), 6)
        self.assertEqual(profile.language_level_value("english"), 5)
        self.assertEqual(profile.language_level_value("German"), 2)
        self.assertIsNone(profile.language_level_value("French"))
        self.assertIsNone(profile.language_level_value("Spanish"))


if __name__ == "__main__":
    unittest.main()
