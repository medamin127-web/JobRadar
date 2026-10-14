import unittest

from models import Job
from services.eligibility_analyzer import (
    EligibilityAnalyzer,
    analyze_german_requirement,
    analyze_relocation,
    analyze_visa,
    detect_language,
)


def german(text, language=None):
    return analyze_german_requirement(text, language)


class TestGermanRequirement(unittest.TestCase):
    """Sentences below come from real LinkedIn listings."""

    def test_explicit_cefr_level(self):
        r = german("Verhandlungssichere Deutschkenntnisse (mindestens C1) "
                   "und gute Englischkenntnisse (B2) runden Dein Profil ab")
        self.assertEqual(r["requirement"], "required")
        self.assertEqual(r["level_value"], 5)

    def test_cefr_level_belongs_to_german_not_english(self):
        r = german("Sehr gute Deutschkenntnisse und mindestens "
                   "Englisch Kenntnisse auf B2 Niveau")
        self.assertEqual(r["level_value"], 4)

    def test_german_c1_mandatory(self):
        r = german("German C1 (Mandatory)")
        self.assertEqual(r["requirement"], "required")
        self.assertEqual(r["level_value"], 5)

    def test_fluent_english_and_german_shares_level(self):
        r = german("Fluent English and German language skills")
        self.assertEqual(r["level_value"], 5)

    def test_basic_german_is_not_fluent(self):
        r = german("Fluent English, basic German is enough to start.")
        self.assertEqual(r["level_value"], 2)

    def test_plus_is_optional(self):
        r = german("German skills are a plus.")
        self.assertEqual(r["requirement"], "optional")

    def test_not_required(self):
        r = german("German helps for customer calls but isn't required.")
        self.assertEqual(r["requirement"], "not_required")

    def test_english_or_german_is_not_a_german_requirement(self):
        r = german("Professionelle Sprachkenntnisse in Englisch oder / und Deutsch.")
        self.assertEqual(r["requirement"], "optional")

    def test_company_description_is_not_a_requirement(self):
        r = german("Our client is a venture-backed German AI company helping "
                   "businesses build customer-facing voice agents.")
        self.assertEqual(r["requirement"], "none_mentioned")

    def test_language_course_perk_is_not_a_requirement(self):
        r = german("Personal learning budget as well as German and "
                   "English language courses")
        self.assertEqual(r["requirement"], "not_required")

    def test_very_high_level_wording(self):
        r = german("Deine Deutschkenntnisse sind in Wort und Schrift auf einem sehr hohen Niveau.")
        self.assertEqual(r["level_value"], 5)

    def test_c_niveau(self):
        r = german("Sie kommunizieren klar auf Deutsch und Englisch (C-Niveau).")
        self.assertEqual(r["level_value"], 5)

    def test_german_listing_without_statement_is_implied(self):
        r = german("Wir suchen einen Entwickler.", language="de")
        self.assertEqual(r["requirement"], "implied")

    def test_nothing_mentioned(self):
        r = german("We build software for logistics.", language="en")
        self.assertEqual(r["requirement"], "none_mentioned")


class TestVisa(unittest.TestCase):

    def test_visa_sponsorship_offered(self):
        r = analyze_visa("We offer visa sponsorship")
        self.assertEqual(r["visa_status"], "yes")

    def test_visa_and_relocation_support(self):
        r = analyze_visa("We offer full visa and relocation support "
                         "for international candidates")
        self.assertEqual(r["visa_status"], "yes")

    def test_no_sponsorship(self):
        r = analyze_visa("Unfortunately we cannot sponsor visas.")
        self.assertEqual(r["visa_status"], "no")

    def test_german_no_visa_support(self):
        r = analyze_visa("Wir bieten leider keine Unterstützung bei Visa an.")
        self.assertEqual(r["visa_status"], "no")

    def test_work_permit_required_for_non_eu(self):
        r = analyze_visa("Please be advised that a valid work permit for "
                         "Germany is required for non-EU citizens.")
        self.assertTrue(r["work_authorization_required"])
        self.assertEqual(r["visa_status"], "unknown")

    def test_arbeitserlaubnis_required(self):
        r = analyze_visa("Eine gültige Arbeitserlaubnis für Deutschland ist erforderlich.")
        self.assertTrue(r["work_authorization_required"])

    def test_event_sponsor_is_not_visa(self):
        r = analyze_visa("We are the main sponsor of the local football club.")
        self.assertEqual(r["visa_status"], "unknown")

    def test_silence_is_unknown(self):
        r = analyze_visa("You will build REST APIs with Python.")
        self.assertEqual(r["visa_status"], "unknown")


class TestWorkAuthorization(unittest.TestCase):

    def test_equal_opportunity_is_not_a_requirement(self):
        for s in [
            "Wir freuen uns über Bewerbungen unabhängig von Alter, Geschlecht, Herkunft oder Staatsangehörigkeit.",
            "We welcome everyone regardless of nationality or citizenship.",
            "Bewerber mit EU-Staatsangehörigkeit oder Aufenthaltstitel sind willkommen.",
        ]:
            self.assertFalse(analyze_visa(s)["work_authorization_required"], s)

    def test_real_requirements(self):
        for s in [
            "Please be advised that a valid work permit for Germany is required for non-EU citizens.",
            "Eine gültige Arbeitserlaubnis für Deutschland ist erforderlich.",
            "You must be authorized to work in the EU.",
            "EU citizens only.",
            "Nur für EU-Bürger.",
        ]:
            self.assertTrue(analyze_visa(s)["work_authorization_required"], s)

    def test_requirement_with_visa_support_is_not_a_blocker(self):
        r = analyze_visa("We support your work permit application and visa process.")
        self.assertFalse(r["work_authorization_required"])


class TestRelocation(unittest.TestCase):

    def test_relocation_support(self):
        r = analyze_relocation("Relocation support is available.")
        self.assertEqual(r["relocation_support"], "yes")

    def test_german_relocation(self):
        r = analyze_relocation("Attraktive Vergütung und bei Bedarf Unterstützung beim Umzug.")
        self.assertEqual(r["relocation_support"], "yes")

    def test_no_relocation(self):
        r = analyze_relocation("Unfortunately no relocation is offered.")
        self.assertEqual(r["relocation_support"], "no")

    def test_willing_to_relocate_is_not_support(self):
        r = analyze_relocation("You are willing to relocate to Berlin.")
        self.assertEqual(r["relocation_support"], "unknown")


class TestRemoteAndLanguage(unittest.TestCase):

    def make(self, text, title="Developer", location="Berlin"):
        return EligibilityAnalyzer.analyze(
            Job(title=title, location=location, description=text)
        )

    def test_option_to_work_remotely_on_fridays_is_not_remote(self):
        job = self.make("Together in the office Monday to Thursday, with "
                        "the option to work remotely on Fridays.")
        self.assertNotEqual(job.work_mode, "remote")

    def test_worldwide_remote(self):
        job = self.make("This is a fully remote role, work from anywhere in the world.")
        self.assertEqual(job.work_mode, "remote")
        self.assertEqual(job.remote_scope, "worldwide")

    def test_remote_in_the_eu_is_eu_only(self):
        job = self.make("This is a remote role.", title="Senior Engineer - remote in the EU")
        self.assertEqual(job.remote_scope, "eu_only")

    def test_remote_germany_only(self):
        job = self.make("Fully remote, but you must be based in Germany.")
        self.assertEqual(job.remote_scope, "germany_only")

    def test_no_description(self):
        job = EligibilityAnalyzer.analyze(Job(title="X"))
        self.assertFalse(job.has_description)

    def test_eligible_countries_remote(self):
        job = self.make("Or fully remote from eligible countries.")
        self.assertEqual(job.work_mode, "remote")
        self.assertEqual(job.remote_scope, "limited_countries")

    def test_detect_language(self):
        german_text = ("Wir suchen dich als Entwickler für unser Team und "
                       "du bist mit uns bei der Entwicklung von Software "
                       "dabei, wenn du auch Erfahrung mit der Cloud hast "
                       "und es nicht scheust neue Dinge zu lernen und "
                       "von uns zu lernen") * 2
        english_text = ("We are looking for a developer to join our team and "
                        "you will work with us on the platform that is used "
                        "by customers from all over the world and you have "
                        "experience with the cloud") * 2
        self.assertEqual(detect_language(german_text), "de")
        self.assertEqual(detect_language(english_text), "en")


class TestRealWorldRegressions(unittest.TestCase):
    """Cases found in a real run of the scraper."""

    def make(self, text, title="Developer", location="Berlin"):
        return EligibilityAnalyzer.analyze(
            Job(title=title, location=location, description=text)
        )

    def test_abbreviation_does_not_cut_the_level(self):
        r = german("Wir erwarten sehr gute Deutschkenntnisse (mind. C1) "
                   "für die Zusammenarbeit.")
        self.assertEqual(r["level_value"], 5)

    def test_c_niveau(self):
        r = german("Sie kommunizieren klar auf Deutsch und Englisch (C-Niveau).")
        self.assertEqual(r["level_value"], 5)

    def test_very_high_level_in_german(self):
        r = german("Deine Deutschkenntnisse sind in Wort und Schrift auf "
                   "einem sehr hohen Niveau.")
        self.assertEqual(r["level_value"], 5)

    def test_equal_opportunity_sentence_is_not_a_work_permit_rule(self):
        r = analyze_visa("Wir freuen uns über Bewerbungen unabhängig von "
                         "Alter, Geschlecht oder Staatsangehörigkeit.")
        self.assertFalse(r["work_authorization_required"])

    def test_english_equal_opportunity_sentence(self):
        r = analyze_visa("We welcome applicants regardless of nationality, "
                         "citizenship or background.")
        self.assertFalse(r["work_authorization_required"])

    def test_eu_citizens_only_is_a_requirement(self):
        r = analyze_visa("This position is open to EU citizens only.")
        self.assertTrue(r["work_authorization_required"])

    def test_remote_in_the_eu_is_eu_only(self):
        job = self.make("Join our team.",
                        title="Senior Software Engineer (Rust) - remote in the EU")
        self.assertEqual(job.work_mode, "remote")
        self.assertEqual(job.remote_scope, "eu_only")

    def test_company_spread_around_the_globe_is_not_worldwide_hiring(self):
        job = self.make("We are a remote-first company with teams located "
                        "around the Globe and our HQ in Berlin.")
        self.assertNotEqual(job.remote_scope, "worldwide")

    def test_salary_range_in_title(self):
        job = self.make("Join us.",
                        title="Full-stack Engineer | Berlin | Voice AI | €85–160k")
        self.assertEqual(job.salary_hint_max_eur, 160000)

    def test_german_style_salary_in_title(self):
        job = self.make("Join us.",
                        title="Senior Frontend Web Developer (m/w/d) 75.000€")
        self.assertEqual(job.salary_hint_max_eur, 75000)

    def test_no_salary_in_title(self):
        job = self.make("Join us.", title="Software Engineer")
        self.assertIsNone(job.salary_hint_max_eur)


if __name__ == "__main__":
    unittest.main()
