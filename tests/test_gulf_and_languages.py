"""Gulf hiring rules (nationals only, in-country only, employer visas)
and languages other than German (Arabic, Dutch, French...)."""

import unittest

from models import Job, Language, Profile
from services.eligibility_analyzer import (
    EligibilityAnalyzer,
    analyze_local_hire,
    analyze_other_languages,
    analyze_visa,
)
from services.eligibility_evaluator import ApplicationBucketer, EligibilityEvaluator


def you():
    return Profile(languages=[
        Language(name="Arabic", level="Native"),
        Language(name="English", level="C1"),
        Language(name="French", level="C1"),
        Language(name="German", level="A2"),
    ])


def evaluate(description, country=None, source_hint=None, location="Dubai"):
    job = Job(
        title="Full Stack Developer",
        location=location,
        description=description,
        country=country,
        source_hint=source_hint,
        target_category="good_target",
        match_score=70,
        match_coverage=80,
        role_match_score=90,
        experience_match_score=100,
        seniority_match_score=100,
    )
    EligibilityAnalyzer.analyze(job)
    EligibilityEvaluator.evaluate(job, you())
    ApplicationBucketer.assign(job)
    return job


FILLER = (
    "We are a fast growing software company building products for our clients. "
    "You will build web applications with React and Node.js. "
)


class TestOtherLanguages(unittest.TestCase):

    def check(self, text, expected):
        found = analyze_other_languages(text)
        self.assertEqual(
            {name: (info["requirement"], info["level_value"]) for name, info in found.items()},
            expected,
            text,
        )

    def test_required_with_level(self):
        self.check("Fluent English and Arabic is a must.", {"Arabic": ("required", 5)})
        self.check("Excellent written and spoken English and Arabic (C1).", {"Arabic": ("required", 5)})
        self.check("Bilingual (Arabic / English) is required.", {"Arabic": ("required", 5)})
        self.check("German and Dutch at B2 level required.", {"Dutch": ("required", 4)})
        self.check("Good command of the Dutch language.", {"Dutch": ("required", 4)})

    def test_optional_and_not_required(self):
        self.check("Dutch is a plus.", {"Dutch": ("optional", None)})
        self.check("Strong communication skills in English; Arabic would be an advantage.",
                   {"Arabic": ("optional", None)})
        self.check("Arabic speakers are encouraged to apply.", {"Arabic": ("optional", None)})
        self.check("Arabic is not required.", {"Arabic": ("not_required", None)})
        self.check("Fluent English required, Arabic preferred.", {"Arabic": ("optional", None)})

    def test_not_about_the_language(self):
        self.check("Experience building Arabic RTL interfaces is required.", {})
        self.check("We serve French clients across Europe.", {})
        self.check("Join the French Tech ecosystem, a plus for your career.", {})
        self.check("Our Dutch market is growing.", {})

    def test_strongest_statement_wins(self):
        self.check("Arabic is a plus. Native Arabic speaker required for client calls.",
                   {"Arabic": ("required", 6)})


class TestLocalHire(unittest.TestCase):

    def kind(self, text):
        return analyze_local_hire(text)["local_hire"]

    def test_nationals_only(self):
        for text in (
            "This role is open to UAE Nationals only.",
            "Saudi nationals only.",
            "This is an Emiratisation role.",
            "Must be a Qatari national.",
            "الوظيفة للسعوديين فقط",
        ):
            self.assertEqual(self.kind(text), "nationals_only", text)

    def test_in_country_only(self):
        for text in (
            "Only candidates currently residing in the UAE will be considered.",
            "Candidates must currently be based in Riyadh.",
            "Candidates with a transferable iqama.",
            "Applicants must have their own valid UAE residence visa.",
            "Only local candidates.",
            "In-country candidates only.",
        ):
            self.assertEqual(self.kind(text), "in_country_only", text)

    def test_preferred(self):
        for text in (
            "Candidates residing in the UAE are preferred.",
            "Saudi nationals are preferred.",
            "Immediate joiners preferred.",
            "You should be based in Dubai.",
        ):
            self.assertEqual(self.kind(text), "preferred", text)

    def test_not_local_only(self):
        for text in (
            "The role is based in Dubai.",
            "Must be based in Dubai or willing to relocate.",
            "We support Saudization and invest in local talent through our academy.",
            "Equal opportunity employer regardless of nationality.",
        ):
            self.assertIsNone(self.kind(text), text)


class TestGulfVisa(unittest.TestCase):

    def status(self, text):
        return analyze_visa(text)["visa_status"]

    def test_employer_provides_the_visa(self):
        for text in (
            "Employment visa will be provided.",
            "Company sponsored residence visa.",
            "Visa will be arranged by the company.",
            "Benefits: Visa, medical insurance and annual air ticket.",
            "We provide your work visa and health insurance.",
        ):
            self.assertEqual(self.status(text), "yes", text)

    def test_refusals_still_win(self):
        self.assertEqual(self.status("We do not provide visa sponsorship."), "no")
        self.assertEqual(self.status("No visa sponsorship, medical insurance included."), "no")


class TestGulfDecisions(unittest.TestCase):

    def test_silent_gulf_ad_is_possible_with_the_visa_norm_noted(self):
        job = evaluate(FILLER * 4, country="uae")

        self.assertEqual(job.eligibility_status, "possible")
        self.assertIn("EMPLOYER_VISA_IS_THE_NORM_THERE", job.eligibility_positives)
        self.assertEqual(job.application_bucket, "apply_with_research")

    def test_silent_german_ad_gets_no_such_note(self):
        job = evaluate(FILLER * 4, country="germany", location="Berlin")

        self.assertNotIn("EMPLOYER_VISA_IS_THE_NORM_THERE", job.eligibility_positives)

    def test_nationals_only_is_blocked(self):
        job = evaluate(FILLER * 3 + "This position is for UAE nationals only.", country="uae")

        self.assertEqual(job.eligibility_status, "blocked")
        self.assertIn("NATIONALS_ONLY", job.eligibility_blockers)
        self.assertEqual(job.application_bucket, "skip")

    def test_in_country_only_is_blocked_unless_a_visa_is_offered(self):
        local = FILLER * 3 + "Only candidates currently residing in the UAE will be considered."
        self.assertIn("LOCAL_CANDIDATES_ONLY", evaluate(local, country="uae").eligibility_blockers)

        sponsored = local + " Employment visa will be provided by the company."
        job = evaluate(sponsored, country="uae")
        self.assertNotIn("LOCAL_CANDIDATES_ONLY", job.eligibility_blockers)
        self.assertIn("LOCAL_CANDIDATES_MENTIONED", job.eligibility_warnings)

    def test_visa_provided_is_likely(self):
        job = evaluate(FILLER * 3 + "Benefits: visa, medical insurance, annual air ticket.", country="qatar")

        self.assertEqual(job.eligibility_status, "likely")
        self.assertEqual(job.application_bucket, "apply_now")

    def test_arabic_required_is_your_advantage(self):
        job = evaluate(FILLER * 3 + "Fluent Arabic and English are required.", country="saudi_arabia")

        self.assertIn("ARABIC_REQUIRED_YOU_HAVE_IT", job.eligibility_positives)
        self.assertNotEqual(job.eligibility_status, "blocked")

    def test_a_language_you_lack_blocks(self):
        job = evaluate(FILLER * 3 + "Fluent Dutch is required.", country=None, location="Amsterdam")

        self.assertIn("DUTCH_REQUIRED", job.eligibility_blockers)

    def test_language_not_required_is_noted(self):
        job = evaluate(FILLER * 3 + "Dutch is not required.", location="Amsterdam")

        self.assertIn("DUTCH_NOT_REQUIRED", job.eligibility_positives)

    def test_french_required_does_not_count_as_german(self):
        # A French requirement once made a job "unlikely" (as if German).
        job = evaluate(FILLER * 3 + "Professional fluency in French and English.", location="Paris")

        self.assertEqual(job.eligibility_status, "possible")
        self.assertIn("FRENCH_REQUIRED_YOU_HAVE_IT", job.eligibility_positives)

    def test_jaabz_jobs_count_as_maybe_visa(self):
        job = evaluate(FILLER * 4, source_hint="visa", location="Amsterdam")

        self.assertIn("BOARD_LISTS_IT_AS_VISA_SPONSORED", job.eligibility_positives)
        self.assertEqual(job.eligibility_status, "possible")

        # The listing's own words beat the board's label.
        refused = evaluate(FILLER * 3 + "We cannot sponsor visas.", source_hint="visa", location="Amsterdam")
        self.assertEqual(refused.eligibility_status, "blocked")
        self.assertNotIn("BOARD_LISTS_IT_AS_VISA_SPONSORED", refused.eligibility_positives)


if __name__ == "__main__":
    unittest.main()


class TestNotSoftwareTitles(unittest.TestCase):
    """Indeed UAE returns jobs like these for "Software Engineer"."""

    def test_non_software_titles_are_skipped(self):
        for title in ("Interior Designer", "Draftsman", "civil site engineer",
                      "Planning Engineer", "IT Support Engineer", "Digital Marketing Executive"):
            job = Job(title=title, description=FILLER * 4, country="uae", role_match_score=20,
                      target_category="needs_review", match_score=45, match_coverage=30)
            EligibilityAnalyzer.analyze(job)
            EligibilityEvaluator.evaluate(job, you())
            ApplicationBucketer.assign(job)

            self.assertEqual(job.application_bucket, "skip", title)
            self.assertIn("Not a software role", job.bucket_reason)

    def test_software_titles_are_kept(self):
        for title in ("Web Developer / Web Designer (m/w/d)", "UX/UI Front-End Developer",
                      "Software Development Officer"):
            job = evaluate(FILLER * 4, country="uae")
            job.title = title
            ApplicationBucketer.assign(job)

            self.assertNotIn("Not a software role", job.bucket_reason, title)


class TestPreferredCountriesRankHigher(unittest.TestCase):

    def test_same_bucket_and_score_preferred_country_first(self):
        from pipeline import sort_jobs

        def make(country, score):
            return Job(country=country, application_bucket="apply_with_research",
                       visa_sponsorship_status="unknown", ranking_score=score)

        jobs = [make("uae", 70), make("qatar", 67), make("germany", 80)]
        sort_jobs(jobs, {"qatar": 2})

        # Qatar 67 + 5 = 72 passes the UAE (70), not Germany (80).
        self.assertEqual([job.country for job in jobs], ["germany", "qatar", "uae"])


class TestNationalsInTitle(unittest.TestCase):

    def test_title_naming_saudi_nationals_blocks(self):
        for title in ("Full Stack Development & UX Design – Onsite-KSA_Saudi Nation",
                      "Software Engineer (Saudi Nationals)",
                      "Web Developer - Emiratisation"):
            job = evaluate(FILLER * 4, country="saudi_arabia")
            job.title = title
            EligibilityAnalyzer.analyze(job)
            EligibilityEvaluator.evaluate(job, you())

            self.assertIn("NATIONALS_ONLY", job.eligibility_blockers, title)

    def test_other_titles_are_not_affected(self):
        job = evaluate(FILLER * 4, country="saudi_arabia")
        job.title = "Full Stack Developer - National Bank Project"
        EligibilityAnalyzer.analyze(job)

        self.assertIsNone(job.local_hire)


class TestBoardPromotionIsNotTheEmployer(unittest.TestCase):
    """Jaabz pages say "Searching for ... roles that provide visa sponsorship?"."""

    AD = (
        "Senior PHP Engineer\n"
        "We build a debt collection platform with PHP and Laravel.\n"
        "You have 3+ years of experience with PHP.\n"
        "We offer a hybrid setup in Berlin.\n"
        "Searching for Development & Programming roles that provide visa sponsorship?\n"
        "Looking to advance your Development & Programming career with relocation support?\n"
        "Jaabz lists thousands of jobs with visa sponsorship and relocation.\n"
        "Explore our comprehensive directory of visa sponsorship jobs from employers worldwide "
        "who are ready to sponsor talented international professionals.\n"
        "Discover our full range of relocation jobs with comprehensive support packages "
        "to help you relocate and settle in your new location.\n"
    )

    def test_promotion_lines_do_not_count_as_visa_or_relocation(self):
        from services.normalizer import JobNormalizer

        import pandas as pd

        row = pd.Series({column: None for column in JobNormalizer.JOB_COLUMNS})
        row["site"] = "jaabz"
        row["title"] = "Senior PHP Engineer"
        row["description"] = self.AD
        job = JobNormalizer().normalize_row(row)
        EligibilityAnalyzer.analyze(job)

        self.assertNotIn("Searching for", job.description)
        self.assertIn("debt collection", job.description)
        self.assertEqual(job.visa_sponsorship_status, "unknown")
        self.assertEqual(job.relocation_support, "unknown")

    def test_promotion_before_the_job_drops_only_its_line(self):
        from sources.jsonld import remove_site_promotion

        text = ("Looking to advance your Development career with relocation support?\n"
                + "We build React apps.\n" * 10)

        cleaned = remove_site_promotion(text)

        self.assertNotIn("Looking to advance", cleaned)
        self.assertEqual(cleaned.count("We build React apps."), 10)

    def test_employer_statements_stay(self):
        from sources.jsonld import remove_site_promotion

        for line in ("Work permit assistance",
                     "Visa sponsorship may be considered for exceptional candidates.",
                     "Full immigration and relocation support for UAE move",
                     "We offer relocation support and visa sponsorship.",
                     "We are hiring for multiple remote roles across Europe"):
            self.assertEqual(remove_site_promotion(line), line)

    def test_other_sites_are_left_alone(self):
        from services.normalizer import JobNormalizer

        self.assertIn("Looking to advance",
                      JobNormalizer.clean_description(self.AD, "linkedin"))