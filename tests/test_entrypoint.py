import importlib
import os
import tempfile
import unittest


class TestImportHasNoSideEffects(unittest.TestCase):

    def test_importing_scraper_creates_nothing_and_keeps_stdout(self):
        import sys

        original_stdout = sys.stdout
        original_cwd = os.getcwd()

        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)

            try:
                import scraper

                importlib.reload(scraper)

                self.assertEqual(os.listdir(directory), [])
            finally:
                os.chdir(original_cwd)

        self.assertIs(sys.stdout, original_stdout)
        self.assertTrue(callable(scraper.main))


if __name__ == "__main__":
    unittest.main()


class TestMain(unittest.TestCase):
    """Run the whole program with a fake job source, in a temp folder."""

    def test_main_writes_csv_report_and_raw_copy(self):
        import contextlib
        import io
        import sys

        import scraper

        from .helpers import make_profile
        from .test_pipeline import raw_frame

        class FakeSource:
            def search(self, **kwargs):
                return raw_frame()

        original_stdout = sys.stdout
        original_cwd = os.getcwd()
        original = (scraper.load_profile, scraper.build_source,
                    scraper.SEARCH_CONFIGS, scraper.DELAY_BETWEEN_SEARCHES)

        scraper.load_profile = make_profile
        scraper.build_source = FakeSource
        scraper.SEARCH_CONFIGS = [
            {"location": "Testland", "search_terms": ["Software Engineer"]}
        ]
        scraper.DELAY_BETWEEN_SEARCHES = (0, 0)

        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)

            try:
                with contextlib.redirect_stdout(io.StringIO()) as printed:
                    scraper.main([])

                self.assertTrue(os.path.exists("data/output/jobs.csv"))
                self.assertEqual(len(os.listdir("data/raw")), 1)

                reports = os.listdir("reports")
                self.assertEqual(len(reports), 1)

                with open(os.path.join("reports", reports[0]), encoding="utf-8") as f:
                    report = f.read()

                self.assertIn("JOBRADAR MATCH RANKING", report)
                self.assertIn("JOBRADAR MATCH RANKING", printed.getvalue())
            finally:
                os.chdir(original_cwd)
                (scraper.load_profile, scraper.build_source,
                 scraper.SEARCH_CONFIGS, scraper.DELAY_BETWEEN_SEARCHES) = original

        self.assertIs(sys.stdout, original_stdout)


class TestOfflineMode(unittest.TestCase):
    """--offline re-analyzes saved raw files and never scrapes."""

    def test_offline_uses_saved_files_and_never_scrapes(self):
        import contextlib
        import io

        import scraper

        from .helpers import make_profile
        from .test_pipeline import raw_frame

        def no_scraping():
            raise AssertionError("offline mode must not build a source")

        original = (scraper.load_profile, scraper.build_source)
        scraper.load_profile = make_profile
        scraper.build_source = no_scraping

        original_cwd = os.getcwd()

        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)

            try:
                os.makedirs("data/raw")
                raw_frame().to_csv("data/raw/jobs_raw_20260101_000000.csv", index=False)
                raw_frame().to_csv("data/raw/jobs_raw_20260102_000000.csv", index=False)

                with contextlib.redirect_stdout(io.StringIO()) as printed:
                    scraper.main(["--offline"])

                output = printed.getvalue()

                self.assertIn("analyzing 2 saved raw file(s)", output)
                self.assertIn("Unique jobs after deduplication: 3", output)
                self.assertTrue(os.path.exists("data/output/jobs.csv"))

                # No new raw file is written in offline mode.
                self.assertEqual(len(os.listdir("data/raw")), 2)
            finally:
                os.chdir(original_cwd)
                scraper.load_profile, scraper.build_source = original

    def test_no_saved_files_gives_a_clear_message(self):
        import scraper

        original_cwd = os.getcwd()
        original = scraper.load_profile
        scraper.load_profile = lambda: None

        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)

            try:
                with self.assertRaisesRegex(SystemExit, "No saved raw files"):
                    scraper.main(["--offline"])
            finally:
                os.chdir(original_cwd)
                scraper.load_profile = original