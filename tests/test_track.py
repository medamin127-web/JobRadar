import os
import tempfile
import unittest

import pandas as pd

import track
from database import JobStore

from .test_database import row


class TestTrack(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = JobStore(os.path.join(self.directory.name, "jobs.db"))
        self.store.save_scraped(pd.DataFrame([row("li-4460378155"), row("li-4477572741")]))
        self.printed = []

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def out(self):
        return "\n".join(self.printed)

    def test_applied_with_a_note(self):
        self.assertTrue(track.set_status(self.store, "applied", "378155", "sent CV 15/10",
                                         self.printed.append))

        job = self.store.find("4460378155")[0]
        self.assertEqual(job["status"], "applied")
        self.assertEqual(job["status_note"], "sent CV 15/10")
        self.assertIn("APPLIED", self.out())

    def test_no_and_open(self):
        track.set_status(self.store, "no", "4477572741", output=self.printed.append)
        self.assertEqual(self.store.find("4477572741")[0]["status"], "not_interested")

        track.set_status(self.store, "open", "4477572741", output=self.printed.append)
        self.assertEqual(self.store.find("4477572741")[0]["status"], "open")

    def test_unknown_id(self):
        self.assertFalse(track.set_status(self.store, "closed", "999999", output=self.printed.append))
        self.assertIn("No job with id", self.out())

    def test_ambiguous_suffix_asks_for_more_digits(self):
        self.store.save_scraped(pd.DataFrame([row("li-1110378155")]))

        self.assertFalse(track.set_status(self.store, "applied", "378155", output=self.printed.append))
        self.assertIn("type more digits", self.out())

    def test_overview_lists_recommended_open_jobs_and_applications(self):
        results = os.path.join(self.directory.name, "jobs.csv")
        pd.DataFrame([
            dict(id="li-4460378155", application_bucket="apply_now", match_score=70,
                 title="Backend", company="N26", job_url="u1", is_new=True),
            dict(id="li-4477572741", application_bucket="skip", match_score=50,
                 title="Other", company="X", job_url="u2", is_new=False),
        ]).to_csv(results, index=False, encoding="utf-8-sig")

        self.store.set_status("li-4477572741", "applied", "via LinkedIn")
        track.overview(self.store, results, self.printed.append)

        text = self.out()
        self.assertIn("NEW   4460378155", text)
        self.assertIn("YOUR APPLICATIONS (1)", text)
        self.assertIn("via LinkedIn", text)


if __name__ == "__main__":
    unittest.main()