"""Canada, Austria, Switzerland, Kuwait, Oman."""

import unittest

import pandas as pd

from countries import COUNTRY_PROFILES, country_of_location, search_configs, skipped_location
from sources.relevance import in_country, in_target_countries
from tests.test_gulf_and_languages import FILLER, evaluate

ALL = search_configs(["uk", "netherlands", "germany", "austria", "switzerland", "canada", "kuwait", "oman"])


class TestWhereAJobIs(unittest.TestCase):

    def test_canadian_cities(self):
        for location in ("Toronto, ON", "Vancouver, BC, Canada", "Remote, Canada", "Calgary, Alberta"):
            self.assertEqual(country_of_location(location, ALL), "canada", location)

    def test_london_ontario_is_not_london_uk(self):
        self.assertEqual(country_of_location("London, ON", ALL), "canada")
        self.assertEqual(country_of_location("London, England, UK", ALL), "uk")

    def test_amsterdam_nl_is_still_the_netherlands(self):
        self.assertEqual(country_of_location("Amsterdam, NL", ALL), "netherlands")

    def test_us_locations_never_count(self):
        for location in ("Cambridge, MA", "Austin, TX", "Remote, USA"):
            self.assertIsNone(country_of_location(location, ALL), location)

    def test_canada_without_canada_in_your_countries(self):
        uk_only = COUNTRY_PROFILES["uk"]["location_keywords"]
        self.assertFalse(in_country("London, ON", uk_only))

    def test_austria_switzerland_gulf(self):
        self.assertEqual(country_of_location("Wien, Österreich", ALL), "austria")
        self.assertEqual(country_of_location("Zürich, Switzerland", ALL), "switzerland")
        self.assertEqual(country_of_location("Kuwait City", ALL), "kuwait")
        self.assertEqual(country_of_location("Muscat, Oman", ALL), "oman")

    def test_feed_jobs_in_canada_are_kept(self):
        frame = pd.DataFrame([
            {"site": "jaabz", "location": "Toronto, ON", "is_remote": False},
            {"site": "jaabz", "location": "Austin, TX", "is_remote": False},
        ])
        self.assertEqual(list(in_target_countries(frame, ALL)), [True, False])


class TestRegionsYouDoNotWant(unittest.TestCase):

    def test_quebec_and_romandy(self):
        self.assertIsNotNone(skipped_location("Montréal, QC, Canada", "canada"))
        self.assertIsNotNone(skipped_location("Laval, QC", "canada"))
        self.assertIsNotNone(skipped_location("Geneva, Switzerland", "switzerland"))
        self.assertIsNotNone(skipped_location("Lugano", "switzerland"))

    def test_the_rest_is_kept(self):
        self.assertIsNone(skipped_location("Toronto, ON", "canada"))
        self.assertIsNone(skipped_location("Zürich", "switzerland"))
        self.assertIsNone(skipped_location("Montreal", "germany"))   # only that country's rule

    def test_quebec_jobs_are_skipped_with_the_reason(self):
        job = evaluate(FILLER * 4, country="canada", location="Montréal, QC, Canada")

        self.assertEqual(job.application_bucket, "skip")
        self.assertIn("Québec", job.bucket_reason)

        job = evaluate(FILLER * 4, country="canada", location="Toronto, ON")
        self.assertNotEqual(job.application_bucket, "skip")


class TestLocalVisaWording(unittest.TestCase):

    def test_canadian_citizen_or_pr_required(self):
        job = evaluate(FILLER + "You must be a Canadian citizen or permanent resident. " + FILLER,
                       country="canada", location="Toronto, ON")

        self.assertTrue(job.work_authorization_required)

    def test_legally_entitled_to_work_in_canada(self):
        job = evaluate(FILLER + "Candidates must be legally entitled to work in Canada. " + FILLER,
                       country="canada", location="Toronto, ON")

        self.assertTrue(job.work_authorization_required)

    def test_red_white_red_card_support(self):
        job = evaluate(FILLER + "We support you with the Red-White-Red Card application. " + FILLER,
                       country="austria", location="Wien")

        self.assertEqual(job.visa_sponsorship_status, "yes")

    def test_lmia_sponsorship(self):
        job = evaluate(FILLER + "We will sponsor an LMIA for the right candidate. " + FILLER,
                       country="canada", location="Calgary, AB")

        self.assertEqual(job.visa_sponsorship_status, "yes")

    def test_swiss_permit_required(self):
        job = evaluate(FILLER + "A valid Swiss work permit is required. " + FILLER,
                       country="switzerland", location="Zürich")

        self.assertTrue(job.work_authorization_required)

    def test_kuwait_and_oman_are_gulf(self):
        for key in ("kuwait", "oman"):
            job = evaluate(FILLER * 4, country=key, location=key.title())
            self.assertIn("EMPLOYER_VISA_IS_THE_NORM_THERE", job.eligibility_positives, key)


class TestConfig(unittest.TestCase):

    def test_new_countries_are_searched(self):
        import config

        for key in ("canada", "austria", "switzerland", "kuwait", "oman"):
            self.assertIn(key, config.COUNTRIES)
            self.assertTrue(COUNTRY_PROFILES[key]["indeed_country"])


if __name__ == "__main__":
    unittest.main()