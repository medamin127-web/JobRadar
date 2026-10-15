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
                    scraper.SEARCH_CONFIGS, scraper.DELAY_BETWEEN_SEARCHES,
                    scraper.build_feeds, scraper.SITES)

        scraper.load_profile = make_profile
        scraper.build_source = lambda site: FakeSource()
        scraper.SEARCH_CONFIGS = [
            {"location": "Testland", "search_terms": ["Software Engineer"]}
        ]
        scraper.DELAY_BETWEEN_SEARCHES = (0, 0)
        scraper.build_feeds = lambda: []
        scraper.SITES = ["linkedin"]

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
                 scraper.SEARCH_CONFIGS, scraper.DELAY_BETWEEN_SEARCHES,
                 scraper.build_feeds, scraper.SITES) = original

        self.assertIs(sys.stdout, original_stdout)


class TestDatabaseRuns(unittest.TestCase):
    """main() with the database, in a temp folder, with fake sources."""

    def setUp(self):
        import scraper

        from .helpers import make_profile

        self.scraper = scraper
        self.original = (scraper.load_profile, scraper.build_source,
                         scraper.SEARCH_CONFIGS, scraper.DELAY_BETWEEN_SEARCHES,
                         scraper.build_feeds, scraper.SITES)
        scraper.load_profile = make_profile
        scraper.SEARCH_CONFIGS = [{"location": "Testland", "search_terms": ["Dev"]}]
        scraper.DELAY_BETWEEN_SEARCHES = (0, 0)
        scraper.build_feeds = lambda: []
        scraper.SITES = ["linkedin"]

        self.original_cwd = os.getcwd()
        self.directory = tempfile.TemporaryDirectory()
        os.chdir(self.directory.name)

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.directory.cleanup()
        (self.scraper.load_profile, self.scraper.build_source,
         self.scraper.SEARCH_CONFIGS, self.scraper.DELAY_BETWEEN_SEARCHES,
         self.scraper.build_feeds, self.scraper.SITES) = self.original

    def run_main(self, argv, frame=None):
        import contextlib
        import io

        class FakeSource:
            def search(self, **kwargs):
                return frame.copy()

        def no_scraping():
            raise AssertionError("must not scrape")

        self.scraper.build_source = (
            (lambda site: FakeSource()) if frame is not None else (lambda site: no_scraping())
        )

        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.scraper.main(argv)

        return printed.getvalue()

    def frame(self):
        from datetime import date

        from .test_pipeline import raw_frame

        frame = raw_frame()
        frame["date_posted"] = date.today().isoformat()
        return frame

    def test_first_scrape_marks_everything_new_second_marks_nothing(self):
        first = self.run_main([], self.frame())
        self.assertIn("New jobs (never seen before): 4", first)
        self.assertIn("New in this run: 3", first)      # 4 ids, 3 unique jobs

        second = self.run_main([], self.frame())
        self.assertIn("New jobs (never seen before): 0", second)
        self.assertTrue(os.path.exists("data/jobradar.db"))

    def test_offline_ranks_the_database_and_never_scrapes(self):
        self.run_main([], self.frame())

        output = self.run_main(["--offline"])

        self.assertIn("Offline mode", output)
        self.assertIn("Unique jobs after deduplication: 3", output)

    def test_old_raw_files_are_imported_on_the_first_run(self):
        from datetime import datetime

        os.makedirs("data/raw")
        name = f"jobs_raw_{datetime.now():%Y%m%d_%H%M%S}.csv"
        self.frame().to_csv(os.path.join("data/raw", name), index=False)

        output = self.run_main(["--offline"])

        self.assertIn("imported 4 jobs from data/raw", output)
        self.assertIn("Unique jobs after deduplication: 3", output)

    def test_jobs_you_marked_leave_the_ranking(self):
        from database import JobStore

        self.run_main([], self.frame())

        with JobStore("data/jobradar.db") as store:
            store.set_status("1", "applied", "sent CV")
            store.set_status("2", "not_interested")

        output = self.run_main(["--offline"])
        ranking = output.split("JOBRADAR MATCH RANKING")[1].split("JOBRADAR DATASET")[0]

        self.assertIn("YOUR APPLICATIONS (1)", output)
        self.assertIn("sent CV", output)
        self.assertIn("Hidden (not interested / closed): 1", output)
        self.assertNotIn("Beispiel GmbH", ranking)

    def test_offline_with_an_empty_database_explains_what_to_do(self):
        with self.assertRaisesRegex(SystemExit, "database is empty"):
            self.run_main(["--offline"])