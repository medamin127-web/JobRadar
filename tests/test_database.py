import os
import tempfile
import unittest
from datetime import date

import pandas as pd

from database import JobStore, time_from_raw_filename


def row(id_, description="text", **kwargs):
    values = dict(id=id_, site="linkedin", title=f"Job {id_}", company="Co",
                  location="Berlin", job_url=f"https://x/{id_}",
                  date_posted="2026-10-10", description=description,
                  min_amount=float("nan"), is_remote=False)
    values.update(kwargs)
    return values


class TestJobStore(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = JobStore(os.path.join(self.directory.name, "db", "jobs.db"))

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def save(self, *rows, seen_at="2026-10-14T10:00:00"):
        return self.store.save_scraped(pd.DataFrame(list(rows)), seen_at=seen_at)

    def test_new_and_known_jobs(self):
        self.assertEqual(self.save(row("li-1"), row("li-2")), {"li-1", "li-2"})
        self.assertEqual(self.save(row("li-2"), row("li-3")), {"li-3"})
        self.assertEqual(self.store.count(), 3)

    def test_an_empty_description_never_replaces_a_good_one(self):
        self.save(row("li-1", "a long and useful description"))
        self.save(row("li-1", float("nan")))
        self.save(row("li-1", "short"))

        self.assertEqual(self.store.descriptions()["li-1"], "a long and useful description")

    def test_a_longer_description_replaces_a_shorter_one(self):
        self.save(row("li-1", "short"))
        self.save(row("li-1", "a much longer description"))

        self.assertEqual(self.store.descriptions()["li-1"], "a much longer description")

    def test_first_seen_is_kept_and_last_seen_moves(self):
        self.save(row("li-1"), seen_at="2026-10-13T10:00:00")
        self.save(row("li-1"), seen_at="2026-10-15T10:00:00")

        job = self.store.find("li-1")[0]
        self.assertEqual(job["first_seen"], "2026-10-13T10:00:00")
        self.assertEqual(job["last_seen"], "2026-10-15T10:00:00")

    def test_load_returns_raw_columns_and_tracking_columns(self):
        self.save(row("li-1"))

        frame = self.store.load(today=date(2026, 10, 15))

        self.assertEqual(frame.loc[0, "title"], "Job li-1")
        self.assertEqual(frame.loc[0, "status"], "open")
        self.assertEqual(frame.loc[0, "age_days"], 5)
        self.assertTrue(pd.isna(frame.loc[0, "min_amount"]))

    def test_old_postings_are_left_out(self):
        self.save(row("li-old", date_posted="2026-08-01"), row("li-new", date_posted="2026-10-14"))

        frame = self.store.load(max_age_days=30, today=date(2026, 10, 15))

        self.assertEqual(list(frame["id"]), ["li-new"])

    def test_find_by_full_id_number_or_last_digits(self):
        self.save(row("li-4460378155"), row("li-4477572741"))

        self.assertEqual(len(self.store.find("li-4460378155")), 1)
        self.assertEqual(len(self.store.find("4460378155")), 1)
        self.assertEqual(len(self.store.find("378155")), 1)
        self.assertEqual(len(self.store.find("12")), 0)       # too short

    def test_status(self):
        self.save(row("li-1"))
        self.store.set_status("li-1", "applied", "sent CV")

        self.assertEqual(self.store.by_status("applied")[0]["status_note"], "sent CV")

        with self.assertRaises(ValueError):
            self.store.set_status("li-1", "maybe")

    def test_rows_without_an_id_use_the_url(self):
        self.save(row(float("nan")))
        self.assertEqual(self.store.count(), 1)

    def test_import_raw_files_uses_the_file_time(self):
        path = os.path.join(self.directory.name, "jobs_raw_20261013_131151.csv")
        pd.DataFrame([row("li-1")]).to_csv(path, index=False)

        self.assertEqual(self.store.import_raw_files([path]), 1)
        self.assertEqual(self.store.find("li-1")[0]["first_seen"], "2026-10-13T13:11:51")

    def test_time_from_raw_filename(self):
        self.assertEqual(time_from_raw_filename("data/raw/jobs_raw_20261013_131151.csv"),
                         "2026-10-13T13:11:51")
        self.assertIsNone(time_from_raw_filename("other.csv"))


if __name__ == "__main__":
    unittest.main()