"""Canada, Austria, Switzerland, Kuwait, Oman, Malta, Poland, Estonia,
Lithuania, Sweden, Japan."""

import unittest

import pandas as pd

from countries import COUNTRY_PROFILES, country_of_location, search_configs, skipped_location
from sources.relevance import in_country, in_target_countries
from tests.test_gulf_and_languages import FILLER, evaluate

ALL = search_configs([
    "uk", "netherlands", "germany", "austria", "switzerland", "canada", "kuwait", "oman",
    "malta", "poland", "estonia", "lithuania", "sweden", "japan",
])


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


class TestSecondBatch(unittest.TestCase):

    def test_cities(self):
        for location, key in (
            ("St. Julian's, Malta", "malta"), ("Sliema", "malta"),
            ("Kraków, Lesser Poland, Poland", "poland"), ("Warszawa", "poland"),
            ("Tallinn, Harjumaa, Estonia", "estonia"), ("Vilnius", "lithuania"),
            ("Göteborg, Sweden", "sweden"), ("Malmö", "sweden"),
            ("Shibuya, Tokyo, Japan", "japan"), ("Osaka", "japan"),
        ):
            self.assertEqual(country_of_location(location, ALL), key, location)

    def test_japanese_level_required(self):
        job = evaluate(FILLER + "Japanese language skills at JLPT N2 level or above are required. " + FILLER,
                       country="japan", location="Tokyo")

        self.assertEqual(job.other_languages["Japanese"]["requirement"], "required")
        self.assertEqual(job.other_languages["Japanese"]["level_value"], 4)
        self.assertIn("JAPANESE_REQUIRED", job.eligibility_blockers)

    def test_japanese_not_required(self):
        job = evaluate(FILLER + "Japanese is not required; our team works in English. " + FILLER,
                       country="japan", location="Tokyo")

        self.assertEqual(job.other_languages["Japanese"]["requirement"], "not_required")

    def test_listing_written_in_japanese(self):
        text = "当社はウェブアプリケーションを開発するソフトウェア会社です。フロントエンドエンジニアを募集しています。" * 3
        job = evaluate(text + " React TypeScript", country="japan", location="Tokyo")

        self.assertEqual(job.other_languages["Japanese"]["requirement"], "required")

    def test_listing_written_in_polish_or_swedish(self):
        polish = ("Oferujemy pracę w zespole, który rozwija aplikacje. Wymagania: doświadczenie jako "
                  "programista, znajomość React oraz Node. Zakres obowiązków jest szeroki i nie "
                  "będzie nudno, praca dla ciebie jest tutaj, która daje rozwój zespołu. ") * 2
        swedish = ("Vi söker en utvecklare som vill arbeta hos oss och är nyfiken. Du kommer att "
                   "arbeta inom vårt team för att bygga tjänsten, och erfarenhet av React eller "
                   "Node är också bra. Vår kunskap och ditt engagemang. ") * 2

        self.assertEqual(evaluate(polish, country="poland", location="Warszawa")
                         .other_languages["Polish"]["requirement"], "required")
        self.assertEqual(evaluate(swedish, country="sweden", location="Stockholm")
                         .other_languages["Swedish"]["requirement"], "required")

    def test_polish_the_verb_is_not_the_language(self):
        job = evaluate(FILLER + "You will polish UI skills and must have strong React skills. " + FILLER,
                       country="poland", location="Warsaw")

        self.assertNotIn("Polish", job.other_languages or {})

    def test_english_listing_is_not_marked_foreign(self):
        job = evaluate(FILLER * 6, country="sweden", location="Stockholm")
        self.assertNotIn("Swedish", job.other_languages or {})

    def test_must_already_live_in_japan(self):
        job = evaluate(FILLER + "Applicants must already reside in Japan. " + FILLER,
                       country="japan", location="Tokyo")

        self.assertEqual(job.local_hire, "in_country_only")
        self.assertIn("LOCAL_CANDIDATES_ONLY", job.eligibility_blockers)

    def test_malta_single_permit_support(self):
        job = evaluate(FILLER + "We will support your Single Permit application. " + FILLER,
                       country="malta", location="Sliema")

        self.assertEqual(job.visa_sponsorship_status, "yes")


class TestCzechiaAndPriorities(unittest.TestCase):

    def test_czech_cities(self):
        configs = search_configs(["czechia", "romania"])
        for location, key in (("Praha, Czechia", "czechia"), ("Brno, South Moravia, Czech Republic", "czechia"),
                              ("Cluj-Napoca, Romania", "romania")):
            self.assertEqual(country_of_location(location, configs), key, location)

    def test_czech_required(self):
        job = evaluate(FILLER + "Fluent Czech is required for this role. " + FILLER,
                       country="czechia", location="Praha")
        self.assertIn("CZECH_REQUIRED", job.eligibility_blockers)

    def test_czech_republic_is_not_the_language(self):
        job = evaluate(FILLER + "Our office is in the Czech Republic and we need strong skills. " + FILLER,
                       country="czechia", location="Praha")
        self.assertNotIn("Czech", job.other_languages or {})

    def test_gulf_preference_is_only_within_the_gulf(self):
        import config

        # Saudi Arabia and Qatar are normal (like Europe); only the UAE is lower.
        self.assertEqual(config.COUNTRY_PRIORITY.get("saudi_arabia", 1), 1)
        self.assertEqual(config.COUNTRY_PRIORITY.get("qatar", 1), 1)
        self.assertLess(config.COUNTRY_PRIORITY["uae"], 1)
        self.assertNotIn("romania", config.COUNTRIES)


class TestConfig(unittest.TestCase):

    def test_new_countries_are_searched(self):
        import config

        for key in ("canada", "austria", "switzerland", "kuwait", "oman",
                    "malta", "poland", "estonia", "lithuania", "sweden", "japan", "czechia"):
            self.assertIn(key, config.COUNTRIES)
            self.assertTrue(COUNTRY_PROFILES[key]["indeed_country"])


if __name__ == "__main__":
    unittest.main()