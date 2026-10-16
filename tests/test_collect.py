"""collect_jobs: pauses, retries and stopping when LinkedIn refuses (HTTP 429)."""

import contextlib
import io
import unittest

import pandas as pd

from pipeline import collect_jobs


def one_job(term):
    return pd.DataFrame([{"id": term, "job_url": f"https://x/{term}",
                          "title": term, "company": "C", "description": "d"}])


class FakeSource:
    """Refuses the searches listed in `refuse` (each refusal used once per call)."""

    def __init__(self, refuse=()):
        self.refuse = list(refuse)
        self.calls = []
        self.last_search_rate_limited = False
        self.last_description_failures = 0

    def search(self, search_term, **kwargs):
        self.calls.append(search_term)

        if search_term in self.refuse:
            self.refuse.remove(search_term)
            self.last_search_rate_limited = True
            return pd.DataFrame()

        self.last_search_rate_limited = False
        return one_job(search_term)


def configs(*terms):
    return [{"location": "Germany", "search_terms": list(terms)}]


def collect(source, *terms, stop_after=2):
    sleeps = []

    with contextlib.redirect_stdout(io.StringIO()) as printed:
        jobs = collect_jobs(
            source, configs(*terms), 10, 72,
            delay=(5, 5), rate_limit_wait=90,
            stop_after_rate_limited=stop_after,
            sleep=sleeps.append,
        )

    return jobs, sleeps, printed.getvalue()


class TestCollect(unittest.TestCase):

    def test_pauses_between_searches_but_not_before_the_first(self):
        jobs, sleeps, _ = collect(FakeSource(), "a", "b", "c")

        self.assertEqual(len(jobs), 3)
        self.assertEqual(sleeps, [5, 5])

    def test_refused_search_is_retried_once_after_waiting(self):
        source = FakeSource(refuse=["b"])

        jobs, sleeps, output = collect(source, "a", "b", "c")

        self.assertEqual(source.calls, ["a", "b", "b", "c"])
        self.assertIn(90, sleeps)
        self.assertEqual(len(jobs), 3)
        self.assertNotIn("Searches refused", output)

    def test_search_refused_twice_is_skipped_and_reported(self):
        source = FakeSource(refuse=["b", "b"])

        jobs, _, output = collect(source, "a", "b", "c")

        self.assertEqual(sorted(jobs["id"]), ["a", "c"])
        self.assertIn("Searches refused: 1", output)

    def test_stops_after_too_many_refusals_in_a_row(self):
        source = FakeSource(refuse=["b", "b", "c", "c"])

        jobs, _, output = collect(source, "a", "b", "c", "d", "e")

        self.assertNotIn("d", source.calls)
        self.assertEqual(list(jobs["id"]), ["a"])
        self.assertIn("Stopped early", output)

    def test_nothing_collected_gives_an_empty_frame(self):
        source = FakeSource(refuse=["a", "a", "b", "b"])

        jobs, _, _ = collect(source, "a", "b")

        self.assertTrue(jobs.empty)

    def test_source_without_rate_limit_info_still_works(self):
        class PlainSource:
            def search(self, search_term, **kwargs):
                return one_job(search_term)

        jobs, _, _ = collect(PlainSource(), "a", "b")

        self.assertEqual(len(jobs), 2)


class TestRateLimitWatcher(unittest.TestCase):
    """The watcher reads JobSpy's log lines (JobSpy itself is not needed)."""

    def test_log_lines_are_classified(self):
        import importlib
        import logging
        import sys
        import types

        # Load sources/jobspy_source.py with a stand-in for the jobspy package.
        fake = types.ModuleType("jobspy")
        fake.scrape_jobs = None
        sys.modules.setdefault("jobspy", fake)

        module = importlib.import_module("sources.jobspy_source")
        watcher = module._RateLimitWatcher()

        def log(level, message):
            watcher.handle(logging.LogRecord("JobSpy:LinkedIn", level, "", 0, message, None, None))

        log(logging.WARNING, "LinkedIn response status code 429 for job 4461778698")
        log(logging.WARNING, "LinkedIn response status code 429 for job 4478529221")
        self.assertEqual(watcher.description_failures, 2)
        self.assertFalse(watcher.search_blocked)

        log(logging.ERROR, "LinkedIn response status code 429")
        self.assertTrue(watcher.search_blocked)

    def test_bayt_403_counts_as_refused(self):
        import importlib
        import logging
        import sys
        import types

        fake = types.ModuleType("jobspy")
        fake.scrape_jobs = None
        sys.modules.setdefault("jobspy", fake)

        module = importlib.import_module("sources.jobspy_source")
        watcher = module._RateLimitWatcher()

        def log(message):
            watcher.handle(logging.LogRecord("JobSpy:Bayt", logging.WARNING, "", 0, message, None, None))

        log("Bayt response status code 403 for job 5123456")
        self.assertEqual(watcher.description_failures, 1)
        self.assertFalse(watcher.search_blocked)

        log("Bayt response status code 4030")   # not a status code
        self.assertFalse(watcher.search_blocked)

        log("Bayt response status code 403")
        self.assertTrue(watcher.search_blocked)


if __name__ == "__main__":
    unittest.main()