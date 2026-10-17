"""Official sponsor registers (UK, NL) and how they change a job's verdict."""

import json
import os
import tempfile
import unittest
from unittest import mock

import sponsors
from models import Job, Language, Profile
from services.eligibility_analyzer import EligibilityAnalyzer
from services.eligibility_evaluator import ApplicationBucketer, EligibilityEvaluator


UK_CSV = (
    "﻿Organisation Name,Town/City,County,Type & Rating,Route\n"
    "Picnic Technologies Ltd,London,,Worker (A rating),Skilled Worker\n"
    "Booking.com Ltd,Manchester,,Worker (A rating),Skilled Worker\n"
    "Acme Seasonal Farms Ltd,Kent,,Temporary Worker (A rating),Seasonal Worker\n"
    '"The Hut Group Limited",Manchester,,Worker (A rating),Skilled Worker\n'
)

NL_HTML = """
<table><thead><tr><th>Organisation</th><th>KVK (Chamber of Commerce) number</th></tr></thead>
<tbody>
<tr><td>""Aa-Dee"" Machinefabriek B.V.</td><td>16051874</td></tr>
<tr><td>Picnic Technologies B.V.</td><td>61829420</td></tr>
<tr><td>Adyen N.V.</td><td>34259528</td></tr>
<tr><td>ING Bank N.V.</td><td>33031431</td></tr>
</tbody></table>
"""


class TestParsing(unittest.TestCase):

    def test_uk_csv_keeps_skilled_worker_sponsors(self):
        names = sponsors.parse_uk_csv(UK_CSV)

        self.assertEqual(names, ["Picnic Technologies Ltd", "Booking.com Ltd", "The Hut Group Limited"])

    def test_nl_table_rows(self):
        names = sponsors.parse_nl_html(NL_HTML)

        self.assertEqual(len(names), 4)
        self.assertIn("Adyen N.V.", names)
        self.assertTrue(names[0].startswith("Aa-Dee") or names[0].startswith('"'))


class TestMatching(unittest.TestCase):

    def setUp(self):
        self.uk = sponsors.SponsorRegister("uk", sponsors.parse_uk_csv(UK_CSV))
        self.nl = sponsors.SponsorRegister("nl", sponsors.parse_nl_html(NL_HTML))

    def test_names_as_ads_write_them(self):
        self.assertEqual(self.nl.find("Adyen"), "Adyen N.V.")
        self.assertEqual(self.nl.find("Picnic"), "Picnic Technologies B.V.")
        self.assertEqual(self.nl.find("PICNIC TECHNOLOGIES BV"), "Picnic Technologies B.V.")
        self.assertEqual(self.uk.find("Booking.com"), "Booking.com Ltd")
        self.assertEqual(self.uk.find("THG (The Hut Group)"), None)       # different name: no guess
        self.assertEqual(self.uk.find("The Hut Group"), "The Hut Group Limited")

    def test_short_names_need_an_exact_match(self):
        self.assertEqual(self.nl.find("ING"), None)          # "ing bank" is not "ing"
        self.assertEqual(self.nl.find("ING Bank"), "ING Bank N.V.")

    def test_unknown_company(self):
        self.assertIsNone(self.uk.find("Some Startup"))
        self.assertIsNone(self.uk.find(""))


class TestDownloadAndCache(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(sponsors, "REGISTERS_DIR", self.directory.name)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    def fake_get(self, url, params=None, **kwargs):
        class Response:
            status_code = 200

            def __init__(self, text=None, payload=None):
                self.text = text
                self.payload = payload

            def json(self):
                return self.payload

        if "api/content" in url:
            return Response(payload={"details": {"attachments": [
                {"url": "https://assets.publishing.service.gov.uk/media/x/register.csv"}]}})
        if url.endswith(".csv"):
            return Response(text=UK_CSV + "".join(
                f"Company {n} Ltd,London,,Worker,Skilled Worker\n" for n in range(200)))
        return Response(text="<table>" + "".join(
            f"<tr><td>Bedrijf {n} B.V.</td><td>{10000000 + n}</td></tr>" for n in range(200)) + "</table>")

    def test_update_saves_and_load_reads(self):
        printed = []
        sponsors.update("uk", get=self.fake_get, output=printed.append)
        register = sponsors.load("uk", auto_update=False)

        self.assertEqual(register.find("Picnic Technologies"), "Picnic Technologies Ltd")
        self.assertIn("employers saved", printed[0])

    def test_too_few_names_is_an_error_not_a_save(self):
        with self.assertRaisesRegex(RuntimeError, "layout"):
            sponsors.update("nl", get=lambda url, **k: type("R", (), {"status_code": 200, "text": NL_HTML})())

        self.assertFalse(os.path.exists(os.path.join(self.directory.name, "nl.json")))

    def test_old_copy_is_used_when_the_download_fails(self):
        path = os.path.join(self.directory.name, "nl.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"updated": "2020-01-01T00:00:00", "names": ["Adyen N.V."]}, handle)

        printed = []
        with mock.patch.object(sponsors, "update", side_effect=RuntimeError("offline")):
            register = sponsors.load("nl", output=printed.append)

        self.assertEqual(register.find("Adyen"), "Adyen N.V.")
        self.assertIn("using the saved copy", printed[0])

    def test_only_registers_of_your_countries_are_loaded(self):
        from countries import search_configs

        with mock.patch.object(sponsors, "load", side_effect=lambda key, **k: key):
            self.assertEqual(sponsors.load_for(search_configs(["germany", "uae"])), {})
            self.assertEqual(sorted(sponsors.load_for(search_configs(["uk", "netherlands", "ireland"]))),
                             ["nl", "uk"])


class TestVerdicts(unittest.TestCase):

    FILLER = ("We build web apps with React, Node.js and PostgreSQL for our customers. "
              "You have 1+ years of experience. ") * 4

    def evaluate(self, description, register, country="uk", company="Picnic"):
        from pipeline import attach_sponsor_registers

        job = Job(title="Full Stack Developer", company=company, location="London",
                  description=description, country=country, target_category="good_target",
                  match_score=70, match_coverage=80, role_match_score=90,
                  experience_match_score=100, seniority_match_score=100)
        EligibilityAnalyzer.analyze(job)
        attach_sponsor_registers([job], {"uk": register} if register else {})
        EligibilityEvaluator.evaluate(job, Profile(languages=[Language(name="English", level="C1")]))
        ApplicationBucketer.assign(job)
        return job

    def register(self, *names):
        return sponsors.SponsorRegister("uk", list(names))

    def test_on_the_register_is_a_good_sign(self):
        job = self.evaluate(self.FILLER, self.register("Picnic Technologies Ltd"))

        self.assertEqual(job.sponsor_register, "listed")
        self.assertIn("ON_OFFICIAL_SPONSOR_REGISTER", job.eligibility_positives)
        self.assertEqual(job.eligibility_status, "possible")
        self.assertEqual(job.application_bucket, "apply_with_research")

    def test_not_on_the_register_and_silent_is_unlikely(self):
        job = self.evaluate(self.FILLER, self.register("Other Company Ltd"))

        self.assertEqual(job.eligibility_status, "unlikely")
        self.assertIn("NOT_ON_OFFICIAL_SPONSOR_REGISTER", job.eligibility_warnings)
        self.assertIn("not on the official sponsor register", job.bucket_reason)

    def test_ad_promising_a_visa_wins_with_a_warning(self):
        job = self.evaluate(self.FILLER + "We can sponsor Skilled Worker visas.",
                            self.register("Other Company Ltd"))

        self.assertIn("SAYS_SPONSOR_BUT_NOT_ON_REGISTER", job.eligibility_warnings)
        self.assertNotEqual(job.eligibility_status, "unlikely")

    def test_countries_without_a_register_are_unchanged(self):
        job = self.evaluate(self.FILLER, self.register("Other Company Ltd"), country="ireland")

        self.assertIsNone(job.sponsor_register)
        self.assertEqual(job.eligibility_status, "possible")


class TestEuropeanWording(unittest.TestCase):

    def visa(self, text):
        from services.eligibility_analyzer import analyze_visa

        result = analyze_visa(text)
        return result["visa_status"], result["work_authorization_required"]

    def test_permit_names(self):
        self.assertEqual(self.visa("We can sponsor Skilled Worker visas for this role."), ("yes", False))
        self.assertEqual(self.visa("We support Critical Skills Employment Permit applications."), ("yes", False))
        self.assertEqual(self.visa("We help with your highly skilled migrant permit."), ("yes", False))
        self.assertEqual(self.visa("Skilled Worker sponsorship is not available for this role."), ("no", False))

    def test_already_allowed_to_work(self):
        self.assertEqual(self.visa("Applicants must have the right to work in the UK."), ("unknown", True))
        self.assertEqual(self.visa("Candidates must hold Stamp 4 or an EU passport."), ("unknown", True))
        self.assertEqual(self.visa("You must be eligible to work in the Netherlands."), ("unknown", True))

    def test_remote_inside_one_country_only(self):
        from services.eligibility_analyzer import analyze_remote

        for text, scope in (
            ("This is a fully remote role, open to candidates based in the UK.", "country_only"),
            ("Fully remote (Netherlands).", "country_only"),
            ("Fully remote, work from anywhere in the world.", "worldwide"),
        ):
            job = Job(title="Developer", location="Remote")
            self.assertEqual(analyze_remote(job, text)["remote_scope"], scope, text)

    def test_30_percent_ruling_means_hiring_from_abroad(self):
        from services.eligibility_analyzer import INTERNATIONAL_FRIENDLY

        self.assertIsNotNone(INTERNATIONAL_FRIENDLY.search("You may be eligible for the 30% ruling."))


class TestEuropeanPlaces(unittest.TestCase):

    def test_cities_and_lookalikes(self):
        from countries import country_of_location, search_configs

        configs = search_configs(["germany", "netherlands", "ireland", "uk"])

        for location, expected in (
            ("Amsterdam, North Holland, Netherlands", "netherlands"),
            ("Eindhoven", "netherlands"),
            ("Dublin, County Dublin, Ireland", "ireland"),
            ("London, England, United Kingdom", "uk"),
            ("Remote - UK", "uk"),
            ("Berlin, DE", "germany"),
            ("Cambridge, MA", None),
            ("London, ON, Canada", None),
            ("Dublin, CA", None),
            ("New York, NY", None),
            ("Kyiv, Ukraine", None),
        ):
            self.assertEqual(country_of_location(location, configs), expected, location)


if __name__ == "__main__":
    unittest.main()