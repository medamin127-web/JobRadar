"""End-to-end run of the pipeline on a few small, fake job postings."""

import unittest

import pandas as pd

from pipeline import jobs_to_frame, process_jobs

from .helpers import make_profile


ENGLISH_VISA_JOB = (
    "We are looking for a Junior Full Stack Developer to join our team. "
    "You will work with React, TypeScript and Python on our web platform. "
    "You will build features, write tests and work with the product team. "
    "We offer visa support and a relocation package for international "
    "candidates. The working language is English and you will be part of "
    "an international team. Our company is growing and we are happy to "
    "welcome new colleagues from all over the world."
)

GERMAN_JOB = (
    "Wir suchen einen Full-Stack Entwickler für unser Team in München. "
    "Du arbeitest mit React und TypeScript und entwickelst neue Funktionen "
    "für unsere Plattform. Wir bieten dir ein tolles Team und flexible "
    "Arbeitszeiten. Du bringst Verhandlungssichere Deutschkenntnisse "
    "(mindestens C1) sowie gute Englischkenntnisse mit und hast Freude "
    "an der Arbeit im Team. Wir freuen uns auf deine Bewerbung."
)

BARE_JOB = "Software Engineer wanted."


def raw_frame():
    rows = [
        # id, url, title, company, description
        ("1", "https://x/1", "Junior Full Stack Developer", "Acme", ENGLISH_VISA_JOB),
        ("1", "https://x/1", "Junior Full Stack Developer", "Acme", ENGLISH_VISA_JOB),  # same URL
        ("2", "https://x/2", "Full-Stack Entwickler (m/w/d)", "Beispiel GmbH", GERMAN_JOB),
        ("3", "https://x/3", "Software Engineer", "Bare Inc", BARE_JOB),
        ("4", "https://x/4", "Junior Full Stack Developer", "Acme", ENGLISH_VISA_JOB),  # other URL, same job
    ]

    return pd.DataFrame(
        rows, columns=["id", "job_url", "title", "company", "description"]
    )


class TestPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.jobs = process_jobs(raw_frame(), make_profile())
        cls.by_company = {job.company: job for job in cls.jobs}

    def test_duplicates_are_removed(self):
        self.assertEqual(len(self.jobs), 3)

    def test_english_job_with_visa_support(self):
        job = self.by_company["Acme"]

        self.assertEqual(job.visa_sponsorship_status, "yes")
        self.assertEqual(job.relocation_support, "yes")
        self.assertEqual(job.eligibility_status, "likely")
        self.assertEqual(job.application_bucket, "apply_now")
        self.assertEqual(job.seniority, "Junior")

    def test_german_ad_needing_c1_is_blocked_for_an_a2_candidate(self):
        job = self.by_company["Beispiel GmbH"]

        self.assertEqual(job.job_language, "de")
        self.assertEqual(job.german_level_required, "C1")
        self.assertEqual(job.eligibility_status, "blocked")
        self.assertEqual(job.application_bucket, "skip")

    def test_job_with_no_description_signals_is_sent_to_review(self):
        job = self.by_company["Bare Inc"]

        self.assertEqual(job.application_bucket, "review")

    def test_best_bucket_comes_first(self):
        self.assertEqual(self.jobs[0].company, "Acme")
        self.assertEqual(self.jobs[-1].application_bucket, "skip")

    def test_frame_has_the_important_columns_first(self):
        frame = jobs_to_frame(self.jobs)

        self.assertEqual(frame.columns[0], "application_bucket")
        self.assertEqual(len(frame), 3)

    def test_empty_input(self):
        self.assertEqual(process_jobs(pd.DataFrame(), make_profile()), [])
        self.assertTrue(jobs_to_frame([]).empty)


if __name__ == "__main__":
    unittest.main()
