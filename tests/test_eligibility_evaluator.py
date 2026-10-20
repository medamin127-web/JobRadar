import unittest

from models import Job, Profile, Language
from services.eligibility_evaluator import (
    ApplicationBucketer,
    EligibilityEvaluator,
)


def profile(german=None):
    return Profile(languages=[Language(name="German", level=german)])


def job(**kwargs):
    base = dict(
        title="Developer",
        description="x",
        has_description=True,
        visa_sponsorship_status="unknown",
        relocation_support="unknown",
        german_requirement="none_mentioned",
        work_mode="unclear",
        remote_scope="unknown",
        work_authorization_required=False,
        english_working_language=False,
        international_friendly=False,
        target_category="good_target",
        match_score=70,
        match_coverage=80,
        role_match_score=90,
        experience_match_score=100,
        seniority_match_score=100,
    )
    base.update(kwargs)
    return Job(**base)


def run(j, p=None):
    EligibilityEvaluator.evaluate(j, p or profile())
    ApplicationBucketer.assign(j)
    return j


class TestEvaluator(unittest.TestCase):

    def test_explicit_no_sponsorship_blocks(self):
        j = run(job(visa_sponsorship_status="no"))
        self.assertEqual(j.eligibility_status, "blocked")
        self.assertEqual(j.application_bucket, "skip")

    def test_work_authorization_required_blocks(self):
        j = run(job(work_authorization_required=True))
        self.assertIn("WORK_AUTHORIZATION_REQUIRED", j.eligibility_blockers)

    def test_work_authorization_with_sponsorship_only_warns(self):
        j = run(job(work_authorization_required=True,
                    visa_sponsorship_status="yes"))
        self.assertNotEqual(j.eligibility_status, "blocked")

    def test_remote_germany_only_blocks(self):
        j = run(job(work_mode="remote", remote_scope="germany_only"))
        self.assertEqual(j.eligibility_status, "blocked")

    def test_remote_worldwide_is_likely(self):
        j = run(job(work_mode="remote", remote_scope="worldwide"))
        self.assertEqual(j.eligibility_status, "likely")
        self.assertEqual(j.application_bucket, "apply_now")

    def test_german_required_with_unknown_level_only_warns(self):
        j = run(job(german_requirement="required", german_level_value=5),
                profile(german=None))
        self.assertNotEqual(j.eligibility_status, "blocked")
        self.assertIn("GERMAN_C1_PLUS_UNVERIFIED", j.eligibility_warnings)

    def test_german_gap_of_two_blocks(self):
        j = run(job(german_requirement="required", german_level_value=5),
                profile(german="B1"))
        self.assertIn("GERMAN_LEVEL_TOO_HIGH", j.eligibility_blockers)

    def test_german_gap_of_one_is_a_stretch_warning(self):
        j = run(job(german_requirement="required", german_level_value=4),
                profile(german="B1"))
        self.assertIn("GERMAN_LEVEL_STRETCH", j.eligibility_warnings)
        self.assertNotEqual(j.eligibility_status, "blocked")

    def test_german_level_met(self):
        j = run(job(german_requirement="required", german_level_value=4),
                profile(german="B2"))
        self.assertIn("GERMAN_LEVEL_OK", j.eligibility_positives)

    def test_silence_is_never_likely(self):
        j = run(job())
        self.assertEqual(j.eligibility_status, "possible")
        self.assertNotEqual(j.application_bucket, "apply_now")

    def test_relocation_support_alone_is_possible_not_likely(self):
        # Relocation help is not visa help (e.g. a bonus for moving
        # within Germany). Only an explicit visa statement is "likely".
        j = run(job(relocation_support="yes"))
        self.assertEqual(j.eligibility_status, "possible")
        self.assertIn("RELOCATION_SUPPORT", j.eligibility_positives)
        # Apply now needs an explicit visa (or remote-from-Tunisia) signal.
        self.assertEqual(j.application_bucket, "apply_with_research")

    def test_visa_support_without_warnings_is_likely(self):
        j = run(job(visa_sponsorship_status="yes"))
        self.assertEqual(j.eligibility_status, "likely")
        self.assertEqual(j.application_bucket, "apply_now")

    def test_german_ad_without_statement_is_unlikely(self):
        j = run(job(german_requirement="implied"))
        self.assertEqual(j.eligibility_status, "unlikely")
        self.assertEqual(j.application_bucket, "long_shot")

    def test_low_priority_technical_fit_is_skipped(self):
        j = run(job(visa_sponsorship_status="yes",
                    target_category="low_priority",
                    target_reason="needs 5 years"))
        self.assertEqual(j.application_bucket, "skip")

    def test_missing_data_lowers_ranking_score(self):
        full = run(job(match_score=80, match_coverage=100))
        thin = run(job(match_score=80, match_coverage=40))
        self.assertGreater(full.ranking_score, thin.ranking_score)

    def test_no_description_is_unknown(self):
        j = run(job(has_description=False))
        self.assertEqual(j.eligibility_status, "unknown")


class TestBucketRules(unittest.TestCase):

    def test_stretch_with_unconfirmed_eligibility_is_long_shot(self):
        j = run(job(target_category="stretch_target"))
        self.assertEqual(j.application_bucket, "long_shot")

    def test_stretch_with_positive_eligibility_is_researched(self):
        j = run(job(target_category="stretch_target", visa_sponsorship_status="yes"))
        self.assertEqual(j.application_bucket, "apply_with_research")

    def test_thin_data_goes_to_review(self):
        j = run(job(relocation_support="yes", match_coverage=40))
        self.assertEqual(j.application_bucket, "review")

    def test_german_ad_without_level_does_not_block_a2(self):
        j = run(job(german_requirement="implied"), profile(german="A2"))
        self.assertNotEqual(j.eligibility_status, "blocked")
        self.assertIn("GERMAN_AD_NO_LEVEL_STATED", j.eligibility_warnings)

    def test_required_german_without_level_stretches_a2(self):
        j = run(job(german_requirement="required", german_level_value=None),
                profile(german="A2"))
        self.assertIn("GERMAN_LEVEL_STRETCH", j.eligibility_warnings)

    def test_limited_countries_remote_warns(self):
        j = run(job(work_mode="remote", remote_scope="limited_countries"))
        self.assertIn("REMOTE_LIMITED_COUNTRIES", j.eligibility_warnings)


class TestRealWorldRegressions(unittest.TestCase):
    """Cases found in a real run of the scraper."""

    def test_unknown_experience_and_seniority_is_not_apply_now(self):
        j = run(job(relocation_support="yes",
                    experience_match_score=None,
                    seniority_match_score=None))
        self.assertEqual(j.application_bucket, "apply_with_research")

    def test_high_salary_in_title_warns_and_demotes(self):
        j = run(job(relocation_support="yes", salary_hint_max_eur=160000))
        self.assertIn("SALARY_ABOVE_JUNIOR_RANGE", j.eligibility_warnings)
        self.assertNotEqual(j.application_bucket, "apply_now")

    def test_junior_title_ignores_salary_hint(self):
        j = run(job(relocation_support="yes", salary_hint_max_eur=85000,
                    seniority="Junior"))
        self.assertNotIn("SALARY_ABOVE_JUNIOR_RANGE", j.eligibility_warnings)

    def test_strong_eligibility_with_unclear_seniority_is_researched(self):
        j = run(job(target_category="needs_review", match_score=61,
                    visa_sponsorship_status="yes", relocation_support="yes"))
        self.assertEqual(j.application_bucket, "apply_with_research")

    def test_irrelevant_role_with_visa_is_not_recommended(self):
        # Before 5a this went to "review"; an unrelated role is skipped now.
        j = run(job(target_category="needs_review", match_score=61,
                    role_match_score=0, relocation_support="yes"))
        self.assertEqual(j.application_bucket, "skip")


if __name__ == "__main__":
    unittest.main()