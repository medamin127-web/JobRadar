"""
Regression tests built from real listings that JobRadar got wrong.
Each test names the job it came from.
"""

import unittest

from models import Job
from services import JobMatcher
from services.eligibility_analyzer import (
    analyze_german_requirement,
    analyze_relocation,
    analyze_visa,
)
from services.eligibility_evaluator import ApplicationBucketer, EligibilityEvaluator
from services.experience_analyzer import ExperienceAnalyzer
from services.experience_matcher import ExperienceMatcher
from services.match_scorer import MatchScorer
from services.seniority_matcher import SeniorityMatcher
from services.target_classifier import TargetClassifier
from pipeline import sort_jobs

from .helpers import make_profile


class TestVisaStatements(unittest.TestCase):

    def test_fullstack_talents_may_be_considered_is_maybe(self):
        for sentence in [
            "Visa sponsorship may be considered for exceptional candidates.",
            "Visa sponsorship may be considered for the right candidate.",
        ]:
            with self.subTest(sentence=sentence):
                self.assertEqual(analyze_visa(sentence)["visa_status"], "maybe")

    def test_spaceteams_german_refusal_is_no(self):
        text = (
            "einer gültigen Berechtigung zur Beschäftigung in Deutschland; "
            "ein Visa- oder Relocation-Sponsoring können wir für diese "
            "Position derzeit nicht anbieten."
        )
        self.assertEqual(analyze_visa(text)["visa_status"], "no")

    def test_german_work_permit_wording_is_a_requirement(self):
        text = "Du verfügst über eine gültige Berechtigung zur Beschäftigung in Deutschland."
        self.assertTrue(analyze_visa(text)["work_authorization_required"])

    def test_real_offers_stay_yes(self):
        for sentence in [
            "Competitive compensation, relocation, and visa support if needed.",
            "Relocation assistance is provided for those willing to relocate "
            "including visa sponsorship where applicable.",
            "We offer full visa and relocation support for international candidates",
            "A relocation package with visa support for those who need it.",
        ]:
            with self.subTest(sentence=sentence):
                self.assertEqual(analyze_visa(sentence)["visa_status"], "yes")


class TestRelocationStatements(unittest.TestCase):

    def test_wolt_may_not_support_relocation_is_no(self):
        text = (
            "We work in distributed teams, but may not be able to support "
            "fully remote work or relocation."
        )
        self.assertEqual(analyze_relocation(text)["relocation_support"], "no")

    def test_plain_support_is_still_yes(self):
        r = analyze_relocation("Relocation support is available, including help finding an apartment.")
        self.assertEqual(r["relocation_support"], "yes")


class TestGermanMentions(unittest.TestCase):

    def test_sap_german_law_is_not_a_language_requirement(self):
        text = "Candidates may need to be eligible for security clearance under German law."
        self.assertEqual(
            analyze_german_requirement(text, "en")["requirement"], "none_mentioned"
        )

    def test_german_language_requirement_still_detected(self):
        r = analyze_german_requirement("You need fluent German and English.", "en")
        self.assertEqual(r["requirement"], "required")


class TestExperienceCaps(unittest.TestCase):

    def setUp(self):
        self.analyzer = ExperienceAnalyzer()

    def test_deutsche_bank_graduate_cap_in_months(self):
        text = "Possess no more than 12 months full-time, relevant work experience."
        self.assertEqual(self.analyzer.extract_years(text), (None, 1.0))

    def test_cap_in_years_is_not_read_as_a_minimum(self):
        text = "You have no more than 2 years of professional experience."
        self.assertEqual(self.analyzer.extract_years(text), (None, 2.0))

    def test_minimum_unchanged(self):
        text = "At least 2 years of relevant experience."
        self.assertEqual(self.analyzer.extract_years(text), (2.0, None))

    def test_above_the_cap_is_low_priority(self):
        profile = make_profile()  # 1.25 years
        job = Job(title="Graduate Programme", experience_max_years=1.0)

        result = TargetClassifier.classify(
            job,
            profile,
            ExperienceMatcher.match(job, profile),
            SeniorityMatcher.match(job, profile),
        )

        self.assertEqual(result["target_category"], "low_priority")


class TestOffTargetDomains(unittest.TestCase):

    def setUp(self):
        self.profile = make_profile()

    def role(self, title, profile=None):
        return JobMatcher.match_role(Job(title=title), profile or self.profile)

    def test_off_target_titles(self):
        for title in [
            "Junior iOS Engineer - Payments",
            "Senior Flight Software Engineer",
            "Software Engineer Mainframe (m/w/d)",
            "Senior Development Engineer Embedded Software (all gender)",
            "SAP ABAP Entwickler - ICM (m/w/d)",
        ]:
            with self.subTest(title=title):
                result = self.role(title)
                self.assertLessEqual(result["score"], 15)

    def test_web_and_cross_platform_titles_are_fine(self):
        for title in [
            "Software Engineer - AI & Productivity Solutions",
            "Fullstack Engineer II, Dmarts – Quick Commerce",
            "Flutter Developer (iOS & Android)",
        ]:
            with self.subTest(title=title):
                self.assertGreaterEqual(self.role(title)["score"], 65)

    def test_a_field_in_your_target_roles_is_not_off_target(self):
        profile = make_profile(target_roles=["iOS Developer", "Software Engineer"])
        self.assertGreater(self.role("Junior iOS Engineer", profile)["score"], 15)


class TestSecondRunCases(unittest.TestCase):
    """From the run of 2026-10-14 after Phase 1a."""

    def test_hdi_mind_c1_after_both_languages_is_c1(self):
        text = "Teamgeist, Kommunikationsstärke und gute Deutsch- und Englischkenntnisse (mind C1)"
        self.assertEqual(analyze_german_requirement(text, "de")["level_value"], 5)

    def test_aracom_go_and_vue_detects_go(self):
        from services.job_analyzer import JobAnalyzer

        skills = JobAnalyzer().extract_skills("Senior Fullstack-Entwickler (m/w/d) – Go & Vue.js")
        self.assertIn("Go", skills)
        self.assertIn("Vue.js", skills)

    def test_go_as_an_english_word_is_not_a_skill(self):
        from services.job_analyzer import JobAnalyzer

        skills = JobAnalyzer().extract_skills("Ready to go? We build React apps and go live weekly.")
        self.assertNotIn("Go", skills)

    def test_softwareingenieur_is_a_software_role(self):
        result = JobMatcher.match_role(Job(title="Softwareingenieur (m/w/d)"), make_profile())
        self.assertGreaterEqual(result["score"], 65)

    def test_obvious_skills_are_implied(self):
        result = JobMatcher.match_skills(
            Job(skills=["SQL", "GitHub", "GitLab", "Docker"]), make_profile()
        )

        self.assertEqual(result["matched_skills"], ["github", "gitlab", "sql"])
        self.assertEqual(result["missing_skills"], ["docker"])


class TestYourLabels(unittest.TestCase):
    """From your first `labels.py evaluate` (2026-10-15)."""

    def test_westwing_german_is_a_plus_on_its_own_line(self):
        text = "Excellent written and verbal communication skills; German is a plus"
        self.assertEqual(analyze_german_requirement(text, "en")["requirement"], "optional")

    def test_simulator_software_is_your_field(self):
        result = JobMatcher.match_role(Job(title="Simulator Software Engineer (m/f/d)"), make_profile())
        self.assertGreaterEqual(result["score"], 65)

    def test_flight_software_is_still_off_target(self):
        result = JobMatcher.match_role(Job(title="Senior Flight Software Engineer"), make_profile())
        self.assertLessEqual(result["score"], 15)

    def stretch(self, **kwargs):
        values = dict(
            title="Senior Full Stack Engineer", description="x", has_description=True,
            visa_sponsorship_status="unknown", relocation_support="unknown",
            german_requirement="none_mentioned", work_mode="hybrid",
            remote_scope="unknown", work_authorization_required=False,
            english_working_language=False, international_friendly=False,
            target_category="stretch_target", match_score=66, match_coverage=80,
            role_match_score=90, skills_match_score=67,
            experience_match_score=None, seniority_match_score=50,
        )
        values.update(kwargs)
        return evaluate(Job(**values))

    def test_senior_title_without_years_and_good_skills_is_recommended(self):
        # LiveEO, Westwing, lemon.markets: you would apply.
        self.assertEqual(self.stretch().application_bucket, "apply_with_research")

    def test_senior_with_a_small_experience_gap_is_recommended(self):
        # Snke: 2+ years asked, you have 1.25 (experience score 75).
        job = self.stretch(experience_match_score=75, match_score=70, skills_match_score=60)
        self.assertEqual(job.application_bucket, "apply_with_research")

    def test_senior_with_weak_skills_stays_a_long_shot(self):
        # JetBrains AppGlass: Kotlin/.NET, 40% skills. You would not apply.
        job = self.stretch(match_score=59, skills_match_score=40)
        self.assertEqual(job.application_bucket, "long_shot")

    def test_senior_with_a_big_experience_gap_stays_a_long_shot(self):
        job = self.stretch(experience_match_score=55)  # ~2 years short
        self.assertEqual(job.application_bucket, "long_shot")


class TestRelocationRefusalMeansNoVisa(unittest.TestCase):

    def test_wolt_relocation_refused_and_no_visa_statement_is_visa_no(self):
        from services.eligibility_analyzer import EligibilityAnalyzer

        job = Job(title="Senior Software Engineer", description=(
            "We build great products for millions of customers in many countries. "
            "We work in distributed teams, but may not be able to support fully "
            "remote work or relocation. You will join a team of engineers working "
            "on the backend with Go and Kotlin and you will own features end to end."
        ))

        EligibilityAnalyzer.analyze(job)

        self.assertEqual(job.relocation_support, "no")
        self.assertEqual(job.visa_sponsorship_status, "no")

    def test_an_explicit_visa_offer_is_not_overruled(self):
        from services.eligibility_analyzer import EligibilityAnalyzer

        job = Job(title="Engineer", description=(
            "We offer visa sponsorship for this role. Relocation is not offered."
        ))

        EligibilityAnalyzer.analyze(job)

        self.assertEqual(job.visa_sponsorship_status, "yes")


class TestScoring(unittest.TestCase):

    def test_two_detected_skills_cannot_make_a_96(self):
        # Fullstack Talents: role 90, 2/2 skills, experience and seniority unknown.
        job = Job(title="Full-stack Engineer / Product Owner", skills=["Python", "TypeScript"])

        result = MatchScorer.score(job, make_profile())

        self.assertEqual(result["skills_score"], 100)   # raw: what matched
        self.assertLess(result["overall_score"], 80)    # was 96
        self.assertEqual(result["coverage"], 70)

    def test_many_matching_skills_still_score_high(self):
        job = Job(
            title="Junior Full Stack Developer",
            seniority="junior",
            experience_min_years=1,
            skills=["React", "TypeScript", "JavaScript", "Python", "Flask",
                    "PostgreSQL", "HTML", "CSS"],
        )

        self.assertGreaterEqual(MatchScorer.score(job, make_profile())["overall_score"], 90)


def evaluate(job, profile=None):
    profile = profile or make_profile()
    EligibilityEvaluator.evaluate(job, profile)
    ApplicationBucketer.assign(job)
    return job


class TestBuckets(unittest.TestCase):

    def base(self, **kwargs):
        values = dict(
            title="Developer", description="x", has_description=True,
            visa_sponsorship_status="unknown", relocation_support="unknown",
            german_requirement="none_mentioned", work_mode="unclear",
            remote_scope="unknown", work_authorization_required=False,
            english_working_language=False, international_friendly=False,
            match_coverage=80,
        )
        values.update(kwargs)
        return Job(**values)

    def test_n26_junior_ios_with_visa_is_skipped_not_apply_now(self):
        job = self.base(
            title="Junior iOS Engineer - Payments",
            visa_sponsorship_status="yes", relocation_support="yes",
            match_score=12, role_match_score=0, skills_match_score=0,
            seniority_match_score=100, target_category="good_target",
        )

        evaluate(job)

        self.assertEqual(job.eligibility_status, "likely")
        self.assertEqual(job.application_bucket, "skip")

    def test_junior_off_field_job_is_not_a_good_target(self):
        profile = make_profile()
        job = Job(title="Junior iOS Engineer", seniority="Junior",
                  role_match_score=0, skills_match_score=0, match_score=12)

        result = TargetClassifier.classify(
            job, profile,
            ExperienceMatcher.match(job, profile),
            SeniorityMatcher.match(job, profile),
        )

        self.assertEqual(result["target_category"], "needs_review")

    def test_trivago_visa_with_relevant_role_is_researched(self):
        job = self.base(
            visa_sponsorship_status="yes", relocation_support="yes",
            match_score=59, role_match_score=90, skills_match_score=40,
            target_category="needs_review", match_coverage=70,
        )

        self.assertEqual(evaluate(job).application_bucket, "apply_with_research")

    def test_maybe_visa_is_a_positive_but_not_likely(self):
        job = self.base(visa_sponsorship_status="maybe", match_score=72,
                        role_match_score=90, target_category="good_target")

        evaluate(job)

        self.assertIn("VISA_SPONSORSHIP_POSSIBLE", job.eligibility_positives)
        self.assertEqual(job.eligibility_status, "possible")

    def test_visa_yes_is_ranked_above_a_higher_score_in_the_same_bucket(self):
        recruiter = self.base(company="Recruiter", visa_sponsorship_status="maybe",
                              match_score=72, role_match_score=90,
                              target_category="good_target")
        employer = self.base(company="Employer", visa_sponsorship_status="yes",
                             match_score=59, role_match_score=90,
                             target_category="needs_review", match_coverage=70)

        jobs = [evaluate(recruiter), evaluate(employer)]
        self.assertEqual({j.application_bucket for j in jobs}, {"apply_with_research"})

        sort_jobs(jobs)

        self.assertEqual(jobs[0].company, "Employer")


if __name__ == "__main__":
    unittest.main()