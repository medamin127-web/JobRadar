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


class TestInteractiveLabelling(unittest.TestCase):

    def run_label(self, frame, replies):
        replies = iter(replies)
        printed = []

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "labels.csv")
            frame.to_csv(path, index=False, encoding="utf-8-sig")

            labels.label(path, input_fn=lambda prompt: next(replies),
                         output=printed.append, refresh=False)

            return labels.read_labels(path), "\n".join(printed)

    def test_answers_are_saved_and_enter_accepts_the_guess(self):
        frame = labels.build_rows([job("1", german_requirement="required")])

        # would_apply=y, in_my_field=Enter (guess yes), visa=n, german=Enter (guess required)
        back, _ = self.run_label(frame, ["y", "", "n", ""])

        row = back.iloc[0]
        self.assertEqual(row["true_would_apply"], "yes")
        self.assertEqual(row["true_in_my_field"], "yes")
        self.assertEqual(row["true_visa"], "no")
        self.assertEqual(row["true_german"], "required")

    def test_quit_keeps_earlier_answers(self):
        frame = labels.build_rows([job("1"), job("2")])

        back, _ = self.run_label(frame, ["y", "y", "y", "n", "q"])

        self.assertEqual(back.loc[0, "true_would_apply"], "yes")
        self.assertEqual(back.loc[1, "true_would_apply"], "")

    def test_skip_and_wrong_keys(self):
        frame = labels.build_rows([job("1"), job("2")])

        # job 1: a wrong key first, then skip; job 2: answered
        back, printed = self.run_label(frame, ["z", "s", "n", "n", "u", "n"])

        self.assertIn("Please type one of", printed)
        self.assertEqual(back.loc[0, "true_would_apply"], "")
        self.assertEqual(back.loc[1, "true_would_apply"], "no")
        self.assertEqual(back.loc[1, "true_visa"], "unknown")

    def test_already_answered_jobs_are_not_asked_again(self):
        frame = labels.build_rows([job("1"), job("2")])
        for field in ["would_apply", "in_my_field", "visa", "german"]:
            frame.loc[0, f"true_{field}"] = "yes" if field != "german" else "required"

        back, printed = self.run_label(frame, ["n", "n", "n", "n"])

        self.assertIn("1 jobs answered, 1 to go", printed)
        self.assertEqual(back.loc[1, "true_would_apply"], "no")

    def test_d_shows_the_full_description(self):
        long_text = "word " * 400 + "THE_END"
        frame = labels.build_rows([job("1", description=long_text)])

        _, printed = self.run_label(frame, ["d", "y", "y", "y", "n"])

        self.assertIn("THE_END", printed)


class TestEquivalentAnswers(unittest.TestCase):

    def test_implied_german_matches_required(self):
        frame = labels.build_rows([job("1", german_requirement="implied"),
                                   job("2", german_requirement="required")])
        frame["true_german"] = ["required", "implied"]

        self.assertEqual(labels.evaluate(frame)["german"]["correct"], 2)


class TestReview(unittest.TestCase):

    def run_review(self, frame, replies):
        replies = iter(replies)
        printed = []

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "labels.csv")
            frame.to_csv(path, index=False, encoding="utf-8-sig")

            labels.review(path, input_fn=lambda prompt: next(replies),
                          output=printed.append, refresh=False)

            return labels.read_labels(path), "\n".join(printed)

    def test_only_disagreements_are_shown_and_answers_change(self):
        frame = labels.build_rows([job("1"), job("2"), job("3")])
        frame["true_visa"] = ["yes", "no", "maybe"]       # job 1 agrees (pred yes)
        frame["true_german"] = ["none_mentioned", "none_mentioned", "required"]

        # job 2 visa: j (JobRadar right) ; job 3 visa: k (keep) ; job 3 german: n (new answer)
        back, printed = self.run_review(frame, ["j", "k", "n"])

        self.assertIn("3 disagreements", printed)
        self.assertEqual(list(back["true_visa"]), ["yes", "yes", "maybe"])
        self.assertEqual(back.loc[2, "true_german"], "none_mentioned")

    def test_nothing_to_review(self):
        frame = labels.build_rows([job("1")])
        frame["true_visa"] = ["yes"]

        _, printed = self.run_review(frame, [])

        self.assertIn("No disagreements left", printed)