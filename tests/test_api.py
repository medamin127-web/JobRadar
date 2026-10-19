"""Phase 5a: the dashboard API, on a small hand-made snapshot."""

import unittest
from datetime import datetime

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError) as error:   # httpx2 / httpx missing
    raise unittest.SkipTest(f"API tests need: pip install -r requirements.txt ({error})")

import api.server as server
from api.explain import code_text, reason_text
from api.snapshot import Snapshot, SnapshotHolder, mark_new
from models import Job


def job(id, bucket, country, score, **extra):
    defaults = dict(
        title=f"Developer {id}", company="Acme", location="Berlin, Germany",
        application_bucket=bucket, country=country, match_score=score,
        bucket_reason="Good technical fit and eligibility signals are positive.",
        eligibility_status="likely", status="open", first_seen="2026-10-18T10:00:00",
        age_days=1, work_mode="unclear", eligibility_blockers=[], eligibility_warnings=[],
        eligibility_positives=[],
    )
    defaults.update(extra)
    return Job(id=id, **defaults)


def snapshot():
    jobs = [
        job("a", "apply_now", "germany", 80),
        job("b", "apply_with_research", "germany", 70, title="React Engineer"),
        job("c", "apply_with_research", "remote", 65, work_mode="remote", remote_open="yes",
            first_seen="2026-10-19T09:00:00"),
        job("d", "skip", "uae", 60, bucket_reason="Blocked: NATIONALS_ONLY",
            eligibility_blockers=["NATIONALS_ONLY"], eligibility_status="blocked"),
        job("e", "apply_now", "germany", 75, status="applied"),
        job("f", "review", "uk", 50, status="not_interested"),
    ]
    mark_new(jobs)
    return Snapshot(jobs, datetime(2026, 10, 19, 12, 0), datetime(2026, 10, 19, 9, 0))


class TestApi(unittest.TestCase):

    def setUp(self):
        server.holder = SnapshotHolder(builder=snapshot)
        self.client = TestClient(server.app)

    def get(self, **params):
        response = self.client.get("/api/jobs", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_overview(self):
        data = self.client.get("/api/overview").json()

        self.assertEqual(data["total"], 4)            # open jobs only
        self.assertEqual(data["recommended"], 3)
        self.assertEqual(data["applied"], 1)
        self.assertEqual(data["new"], 1)              # only "c" came in the latest run

    def test_tabs_and_countries_count_with_the_other_filters(self):
        data = self.get(bucket="apply_with_research")

        self.assertEqual([item["id"] for item in data["items"]], ["b", "c"])
        self.assertEqual(data["buckets"], {"apply_now": 1, "apply_with_research": 2, "long_shot": 0,
                                           "review": 0, "skip": 1})
        self.assertEqual({c["key"]: c["count"] for c in data["countries"]}, {"germany": 1, "remote": 1})

    def test_filters(self):
        self.assertEqual([i["id"] for i in self.get(country="germany")["items"]], ["a", "b"])
        self.assertEqual([i["id"] for i in self.get(q="react")["items"]], ["b"])
        self.assertEqual([i["id"] for i in self.get(new="true")["items"]], ["c"])
        self.assertEqual([i["id"] for i in self.get(remote="true")["items"]], ["c"])
        self.assertEqual([i["id"] for i in self.get(view="applied")["items"]], ["e"])
        self.assertEqual([i["id"] for i in self.get(view="hidden")["items"]], ["f"])

    def test_sorting_and_paging(self):
        self.assertEqual([i["id"] for i in self.get(sort="score")["items"]], ["a", "b", "c", "d"])

        data = self.get(limit=2)
        self.assertEqual(data["total"], 4)
        self.assertEqual(len(data["items"]), 2)

    def test_reasons_are_plain_words(self):
        item = next(i for i in self.get(bucket="skip")["items"] if i["id"] == "d")
        self.assertEqual(item["reason"], "Blocked: Only for citizens of that country.")

    def test_one_job(self):
        data = self.client.get("/api/jobs/d").json()

        self.assertEqual(data["title"], "Developer d")
        self.assertEqual(data["blockers_text"], ["Only for citizens of that country"])
        self.assertEqual(self.client.get("/api/jobs/zzz").status_code, 404)

    def test_bad_parameters(self):
        self.assertEqual(self.client.get("/api/jobs", params={"view": "nope"}).status_code, 400)
        self.assertEqual(self.client.get("/api/jobs", params={"sort": "nope"}).status_code, 400)


class TestExplain(unittest.TestCase):

    def test_codes(self):
        self.assertEqual(code_text("REMOTE_OPEN_TO_TUNISIA"), "Hires people living in Tunisia")
        self.assertEqual(code_text("POLISH_REQUIRED"), "Needs Polish, which you do not speak well enough")
        self.assertEqual(code_text("ARABIC_REQUIRED_YOU_HAVE_IT"), "Asks for Arabic, which you have")

    def test_reasons(self):
        self.assertEqual(
            reason_text("Blocked: LOCAL_CANDIDATES_ONLY, JAPANESE_REQUIRED"),
            "Blocked: Only for people already living there; Needs Japanese, which you do not speak well enough.",
        )
        self.assertEqual(reason_text("Technical gap: 5 years"), "Technical gap: 5 years")


if __name__ == "__main__":
    unittest.main()