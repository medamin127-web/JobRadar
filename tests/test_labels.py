import os
import tempfile
import unittest

import pandas as pd

import labels
from models import Job


def job(id_, **kwargs):
    values = dict(
        id=id_, title=f"Job {id_}", company="Co", job_url=f"https://x/{id_}",
        description="text", visa_sponsorship_status="yes",
        relocation_support="unknown", work_authorization_required=False,
        german_requirement="none_mentioned", german_level_required=None,
        seniority="Junior", experience_min_years=2.0,
        role_match_score=90, application_bucket="apply_now", match_score=70,
    )
    values.update(kwargs)
    return Job(**values)


class TestBuildRows(unittest.TestCase):

    def test_predictions_are_plain_words(self):
        row = labels.build_rows([job("1")]).iloc[0]

        self.assertEqual(row["pred_visa"], "yes")
        self.assertEqual(row["pred_work_permit_required"], "no")
        self.assertEqual(row["pred_german_level"], "none")
        self.assertEqual(row["pred_seniority"], "junior")
        self.assertEqual(row["pred_min_years"], "2")
        self.assertEqual(row["pred_would_apply"], "yes")
        self.assertEqual(row["true_visa"], "")

    def test_re_export_keeps_your_answers(self):
        first = labels.build_rows([job("1"), job("2")])
        first.loc[first["id"] == "1", "true_visa"] = "no"

        again = labels.build_rows([job("1"), job("2"), job("3")], previous=first)

        self.assertEqual(len(again), 3)
        self.assertEqual(again.set_index("id").loc["1", "true_visa"], "no")

    def test_labelled_jobs_that_disappeared_are_kept(self):
        first = labels.build_rows([job("1")])
        first.loc[0, "true_visa"] = "yes"

        again = labels.build_rows([job("2")], previous=first)

        self.assertEqual(sorted(again["id"]), ["1", "2"])


class TestEvaluate(unittest.TestCase):

    def test_accuracy_and_mistakes(self):
        frame = labels.build_rows([job("1"), job("2"), job("3")])
        frame["true_visa"] = ["yes", "no", ""]       # 1 right, 1 wrong, 1 skipped
        frame["true_min_years"] = ["2.0", "2,0", "none"]

        results = labels.evaluate(frame)

        self.assertEqual(results["visa"]["labelled"], 2)
        self.assertEqual(results["visa"]["correct"], 1)
        self.assertEqual(results["visa"]["mistakes"][0][2:], ("yes", "no"))
        self.assertEqual(results["min_years"]["correct"], 2)  # "2,0" counts as 2

    def test_recommendation_counts(self):
        frame = labels.build_rows([
            job("1", application_bucket="apply_now"),
            job("2", application_bucket="skip"),
            job("3", application_bucket="skip"),
        ])
        frame["true_would_apply"] = ["yes", "yes", "no"]

        rec = labels.evaluate(frame)["recommendations"]

        self.assertEqual(rec, {"recommended": 1,
                               "recommended_and_you_would_apply": 1,
                               "you_would_apply": 2})


class TestReadLabels(unittest.TestCase):

    def test_reads_excel_semicolon_ansi_files(self):
        frame = labels.build_rows([job("1", title="Entwickler für Köln")])
        frame.loc[0, "true_visa"] = "no"

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "labels.csv")
            frame.to_csv(path, sep=";", index=False, encoding="cp1252")

            back = labels.read_labels(path)

        self.assertEqual(back.loc[0, "title"], "Entwickler für Köln")
        self.assertEqual(back.loc[0, "true_visa"], "no")


if __name__ == "__main__":
    unittest.main()