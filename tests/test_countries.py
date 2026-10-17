"""Country profiles, taking turns between countries, and which jobs count."""

import os
import tempfile
import unittest

import pandas as pd

from countries import COUNTRY_PROFILES, country_of_location, search_configs
from database import JobStore
from pipeline import assign_countries, collect_jobs
from sources.relevance import in_country, in_target_countries


class TestProfiles(unittest.TestCase):

    def test_every_profile_has_what_the_pipeline_needs(self):
        for key, profile in COUNTRY_PROFILES.items():
            for field in ("name", "location", "sites", "local_language",
                          "visa_norm", "location_keywords", "search_terms"):
                self.assertIn(field, profile, f"{key} has no {field}")

            self.assertIn(profile["visa_norm"], ("explicit", "employer_sponsored"))
            self.assertTrue(profile["search_terms"])

    def test_bayt_only_in_the_gulf(self):
        for key, profile in COUNTRY_PROFILES.items():
            if "bayt" in profile["sites"]:
                self.assertEqual(profile["visa_norm"], "employer_sponsored", key)

    def test_priorities_are_attached(self):
        configs = search_configs(["qatar", "germany"], {"qatar": 2})

        self.assertEqual([c["priority"] for c in configs], [2, 1])

    def test_search_configs_keep_order_and_add_the_key(self):
        configs = search_configs(["qatar", "germany"])

        self.assertEqual([c["key"] for c in configs], ["qatar", "germany"])
        self.assertEqual(configs[0]["name"], "Qatar")

    def test_unknown_country_stops_with_a_clear_message(self):
        with self.assertRaisesRegex(SystemExit, "Unknown country.*atlantis"):
            search_configs(["germany", "atlantis"])

    def test_country_of_location(self):
        configs = search_configs(["germany", "uae", "saudi_arabia", "qatar", "oman"])

        self.assertEqual(country_of_location("Dubai, United Arab Emirates", configs), "uae")
        self.assertEqual(country_of_location("Riyadh", configs), "saudi_arabia")
        self.assertEqual(country_of_location("Doha, Qatar", configs), "qatar")
        self.assertEqual(country_of_location("München", configs), "germany")
        self.assertIsNone(country_of_location("Bucharest, Romania", configs))
        self.assertIsNone(country_of_location(None, configs))

    def test_keywords_match_whole_words_only(self):
        self.assertTrue(in_country("Muscat, Oman", ["oman"]))
        self.assertFalse(in_country("Cluj, Romania", ["oman"]))
        self.assertFalse(in_country("Leipzig", ["essen"]) )
        self.assertTrue(in_country("Essen, NRW", ["essen"]))
        self.assertTrue(in_country("Düsseldorf", ["düsseldorf"]))


class TestTargetCountries(unittest.TestCase):

    def frame(self, rows):
        return pd.DataFrame(rows, columns=["site", "location", "is_remote", "search_country"])

    def test_search_jobs_count_while_their_country_is_in_your_list(self):
        configs = search_configs(["germany"])
        frame = self.frame([
            ["linkedin", "Dubai", False, "uae"],        # UAE removed from your list
            ["linkedin", "Berlin", False, "germany"],
            ["linkedin", "Berlin", False, None],        # saved before country keys
        ])

        self.assertEqual(list(in_target_countries(frame, configs)), [False, True, True])

    def test_feed_jobs_count_by_location_or_generic_remote(self):
        configs = search_configs(["germany", "uae"])
        frame = self.frame([
            ["jaabz", "Dubai, UAE", False, None],
            ["jaabz", "Netherlands", False, None],
            ["jaabz", "Remote", True, None],
            ["jaabz", "Remote, Netherlands", True, None],
        ])

        self.assertEqual(list(in_target_countries(frame, configs)), [True, False, True, False])

    def test_assign_countries_prefers_the_search_then_the_location(self):
        configs = search_configs(["germany", "uae"])
        frame = pd.DataFrame({
            "location": ["Remote", "Abu Dhabi", "Hamburg", "Paris"],
            "search_country": ["uae", None, float("nan"), None],
        })

        countries = assign_countries(frame, configs)["country"]

        self.assertEqual(list(countries[:3]), ["uae", "uae", "germany"])
        self.assertTrue(pd.isna(countries[3]))


class TestTakingTurns(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = JobStore(os.path.join(self.directory.name, "test.db"))

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_never_searched_first_then_oldest(self):
        keys = ["germany", "uae", "saudi_arabia", "qatar"]

        self.assertEqual(self.store.countries_to_search(keys, 2), ["germany", "uae"])

        self.store.mark_searched(["germany", "uae"], "2026-10-15T10:00:00")
        self.assertEqual(self.store.countries_to_search(keys, 2), ["saudi_arabia", "qatar"])

        self.store.mark_searched(["saudi_arabia", "qatar"], "2026-10-16T10:00:00")
        self.assertEqual(self.store.countries_to_search(keys, 2), ["germany", "uae"])

        self.store.mark_searched(["germany"], "2026-10-17T10:00:00")
        self.assertEqual(self.store.countries_to_search(keys, 2), ["uae", "saudi_arabia"])

    def test_priority_two_comes_back_twice_as_often(self):
        from datetime import datetime, timedelta

        keys = ["saudi_arabia", "qatar", "germany", "uae"]
        priorities = {"saudi_arabia": 2, "qatar": 2}
        now = datetime(2026, 10, 16, 8, 0)
        counts = dict.fromkeys(keys, 0)

        # 12 runs, 12 hours apart, 2 countries per run.
        for run in range(12):
            chosen = self.store.countries_to_search(keys, 2, priorities, now=now)
            self.store.mark_searched(chosen, now.isoformat(timespec="seconds"))

            for key in chosen:
                counts[key] += 1

            now += timedelta(hours=12)

        self.assertGreater(counts["saudi_arabia"], counts["germany"])
        self.assertGreater(counts["qatar"], counts["uae"])
        self.assertGreater(counts["germany"], 0)   # the others still get their turn
        self.assertGreater(counts["uae"], 0)

    def test_zero_means_all(self):
        keys = ["germany", "uae"]
        self.assertEqual(self.store.countries_to_search(keys, 0), keys)
        self.assertEqual(self.store.countries_to_search(keys, 5), keys)

    def test_a_new_country_in_config_goes_first(self):
        self.store.mark_searched(["germany", "uae"], "2026-10-15T10:00:00")

        self.assertEqual(
            self.store.countries_to_search(["germany", "uae", "qatar"], 1),
            ["qatar"],
        )


class TestCollectTagsTheCountry(unittest.TestCase):

    def test_jobs_remember_which_country_search_found_them(self):
        class Source:
            def search(self, search_term, location, **kwargs):
                return pd.DataFrame([{"id": f"{location}-{search_term}", "title": search_term}])

        configs = search_configs(["uae", "qatar"])
        for config in configs:
            config["search_terms"] = ["Dev"]

        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            jobs = collect_jobs(Source(), configs, 5, 72, sleep=lambda _: None)

        self.assertEqual(list(jobs["search_country"]), ["uae", "qatar"])


class TestScraperRunsSitesPerCountry(unittest.TestCase):
    """Bayt is searched only in Gulf countries; countries take turns."""

    def setUp(self):
        import scraper

        from .helpers import make_profile

        self.scraper = scraper
        self.names = ("load_profile", "build_source", "SEARCH_CONFIGS",
                      "DELAY_BETWEEN_SEARCHES", "build_feeds", "SITES", "COUNTRIES_PER_RUN")
        self.original = {name: getattr(scraper, name) for name in self.names}

        configs = search_configs(["germany", "uae"])
        for config in configs:
            config["search_terms"] = ["Dev"]

        scraper.load_profile = make_profile
        scraper.SEARCH_CONFIGS = configs
        scraper.DELAY_BETWEEN_SEARCHES = (0, 0)
        scraper.build_feeds = lambda known_ids=(), searched=None: []
        scraper.SITES = ["linkedin", "bayt"]
        scraper.COUNTRIES_PER_RUN = 1

        self.calls = []
        calls = self.calls

        class Source:
            def __init__(self, site):
                self.site = site

            def search(self, search_term, location, **kwargs):
                calls.append((self.site, location))
                return pd.DataFrame()

        scraper.build_source = Source

        self.cwd = os.getcwd()
        self.directory = tempfile.TemporaryDirectory()
        os.chdir(self.directory.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.directory.cleanup()

        for name, value in self.original.items():
            setattr(self.scraper, name, value)

    def run_main(self, argv):
        import contextlib
        import io

        self.calls.clear()

        with contextlib.redirect_stdout(io.StringIO()) as printed:
            try:
                self.scraper.main(argv)
            except SystemExit:
                pass  # no jobs at all: fine here

        return printed.getvalue()

    def test_countries_take_turns_and_bayt_skips_germany(self):
        first = self.run_main([])
        self.assertEqual(self.calls, [("linkedin", "Germany")])
        self.assertIn("Countries searched this run: Germany", first)
        self.assertIn("Next runs: United Arab Emirates", first)

        self.run_main([])
        self.assertEqual(
            self.calls,
            [("linkedin", "United Arab Emirates"), ("bayt", "United Arab Emirates")],
        )

    def test_countries_flag_and_all_countries(self):
        # Qatar is not in this config: it is searched with its full profile.
        self.run_main(["--countries", "qatar"])
        self.assertEqual(sorted(set(self.calls)), [("bayt", "Qatar"), ("linkedin", "Qatar")])

        self.run_main(["--all-countries"])
        self.assertEqual(
            self.calls,
            [("linkedin", "Germany"), ("linkedin", "United Arab Emirates"),
             ("bayt", "United Arab Emirates")],
        )

    def test_unknown_country_flag_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "Unknown country"):
            self.scraper.main(["--countries", "atlantis"])


if __name__ == "__main__":
    unittest.main()