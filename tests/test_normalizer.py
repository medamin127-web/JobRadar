import unittest

import pandas as pd

from services.normalizer import JobNormalizer


class TestCleanText(unittest.TestCase):

    def test_look_alike_spaces_and_hyphens_become_plain(self):
        raw = "Full‑Stack Entwickler (m/w/d) – Fokus"

        self.assertEqual(
            JobNormalizer.clean_text(raw),
            "Full-Stack Entwickler (m/w/d) – Fokus",
        )

    def test_invisible_characters_are_removed(self):
        self.assertEqual(JobNormalizer.clean_text("En­gineer​"), "Engineer")

    def test_empty_and_missing_values(self):
        self.assertIsNone(JobNormalizer.clean_text(None))
        self.assertIsNone(JobNormalizer.clean_text(float("nan")))
        self.assertIsNone(JobNormalizer.clean_text("   "))

    def test_normal_text_is_unchanged(self):
        self.assertEqual(JobNormalizer.clean_text("Köln – €85k"), "Köln – €85k")


if __name__ == "__main__":
    unittest.main()
