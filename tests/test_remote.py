"""Phase 4c: remote jobs you can do from Tunisia."""

import json
import unittest

import pandas as pd

from countries import search_configs
from pipeline import assign_countries
from services.eligibility_analyzer import analyze_remote_open
from sources import (
    HimalayasSource,
    RemoteOKSource,
    RemotiveSource,
    WeWorkRemotelySource,
    WorkingNomadsSource,
    remote_board_sources,
)
from sources.relevance import in_target_countries
from tests.test_gulf_and_languages import FILLER, evaluate


class Response:

    def __init__(self, payload=None, text=None, status=200):
        self.payload = payload
        self.text = text if text is not None else json.dumps(payload)
        self.status_code = status

    def json(self):
        return self.payload


def fake_get(answers):
    """answers: {url fragment: payload or text}; records the calls."""

    calls = []

    def get(url, params=None, timeout=None, headers=None):
        calls.append((url, params))

        for fragment, answer in answers.items():
            if fragment in url:
                return Response(text=answer) if isinstance(answer, str) else Response(answer)

        return Response(status=404, text="")

    get.calls = calls
    return get


NO_SLEEP = lambda seconds: None

DESCRIPTION = "<p>We build web apps with React, TypeScript and Node.js.</p>"


class TestBoards(unittest.TestCase):

    def test_remotive(self):
        get = fake_get({"remotive.com": {"jobs": [{
            "id": 1, "url": "https://remotive.com/remote-jobs/software-dev/fs-1", "title": "Full Stack Developer",
            "company_name": "Acme", "candidate_required_location": "Worldwide",
            "publication_date": "2026-10-17T10:00:00", "description": DESCRIPTION, "tags": ["react"],
        }]}})
        jobs = RemotiveSource(get=get, sleep=NO_SLEEP, cache_dir=None).fetch()

        row = jobs.iloc[0]
        self.assertEqual(row["id"], "rv-1")
        self.assertEqual(row["location"], "Worldwide")
        self.assertEqual(row["date_posted"], "2026-10-17")
        self.assertTrue(row["is_remote"])
        self.assertIn("React", row["description"])
        self.assertEqual(get.calls[0][1]["category"], "software-dev")

    def test_remotive_is_cached(self):
        import tempfile

        payload = {"jobs": [{"id": 2, "url": "https://remotive.com/x-2", "title": "Web Developer",
                             "company_name": "B", "candidate_required_location": "Europe"}]}
        get = fake_get({"remotive.com": payload})

        with tempfile.TemporaryDirectory() as folder:
            RemotiveSource(get=get, sleep=NO_SLEEP, cache_dir=folder).fetch()
            RemotiveSource(get=get, sleep=NO_SLEEP, cache_dir=folder).fetch()

        self.assertEqual(len(get.calls), 1)    # they ask for few calls a day

    def test_remoteok_skips_the_legal_notice(self):
        get = fake_get({"remoteok.com": [
            {"last_updated": 1, "legal": "Please link back"},
            {"id": "77", "position": "Frontend Engineer", "company": "C", "location": "",
             "epoch": 1792224050, "url": "https://remoteOK.com/remote-jobs/77", "description": DESCRIPTION},
        ]})
        jobs = RemoteOKSource(get=get, sleep=NO_SLEEP).fetch()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs.iloc[0]["id"], "rok-77")
        self.assertEqual(jobs.iloc[0]["location"], "Worldwide")

    def test_weworkremotely_rss(self):
        rss = """<?xml version="1.0"?><rss><channel>
            <item><title>Mixpanel: Senior Full-Stack Engineer</title><region>Anywhere in the World</region>
            <country></country><description>&lt;p&gt;React&lt;/p&gt;</description>
            <pubDate>Sat, 17 Oct 2026 07:30:54 +0000</pubDate>
            <link>https://weworkremotely.com/remote-jobs/mixpanel-senior-full-stack-engineer</link></item>
            </channel></rss>"""
        get = fake_get({"weworkremotely.com": rss})
        jobs = WeWorkRemotelySource(get=get, sleep=NO_SLEEP).fetch()

        self.assertEqual(len(jobs), 1)          # the same job in 3 feeds is kept once
        row = jobs.iloc[0]
        self.assertEqual(row["company"], "Mixpanel")
        self.assertEqual(row["title"], "Senior Full-Stack Engineer")
        self.assertEqual(row["location"], "Anywhere in the World")
        self.assertEqual(row["date_posted"], "2026-10-17")

    def test_workingnomads_keeps_development_jobs(self):
        get = fake_get({"workingnomads.com": [
            {"url": "https://www.workingnomads.com/job/go/1944774/", "title": "Video Creator",
             "category_name": "Marketing", "location": "USA only"},
            {"url": "https://www.workingnomads.com/job/go/1944775/", "title": "Senior Vue Developer",
             "category_name": "Development", "location": "Europe", "pub_date": "2026-10-15T14:12:21-04:00",
             "company_name": "D", "tags": "vue,javascript"},
        ]})
        jobs = WorkingNomadsSource(get=get, sleep=NO_SLEEP).fetch()

        self.assertEqual(list(jobs["id"]), ["wn-1944775"])

    def test_himalayas_searches_for_your_country(self):
        job = {"title": "React Developer", "companyName": "E", "locationRestrictions": [],
               "description": DESCRIPTION, "pubDate": 1792265691,
               "applicationLink": "https://himalayas.app/companies/e/jobs/react-developer",
               "guid": "https://himalayas.app/companies/e/jobs/react-developer"}
        get = fake_get({"himalayas.app": {"jobs": [job]}})
        jobs = HimalayasSource(["react", "frontend"], country="Tunisia", get=get, sleep=NO_SLEEP).fetch()

        self.assertEqual(len(jobs), 1)            # same job for both terms, kept once
        self.assertEqual(jobs.iloc[0]["location"], "Worldwide")
        self.assertEqual(jobs.iloc[0]["source_hint"], "open_to_you")
        self.assertEqual(get.calls[0][1]["country"], "Tunisia")

    def test_unknown_board_name(self):
        with self.assertRaises(SystemExit):
            remote_board_sources(["remotive", "nope"], [])


class TestRemoteCountry(unittest.TestCase):

    configs = search_configs(["germany", "remote"])

    def frame(self, rows):
        return pd.DataFrame(rows)

    def test_board_jobs_are_remote_and_kept(self):
        jobs = self.frame([
            {"site": "remotive", "location": "USA Only", "is_remote": True, "title": "Web Developer"},
            {"site": "himalayas", "location": "Worldwide", "is_remote": True, "title": "Web Developer"},
        ])

        self.assertEqual(list(assign_countries(jobs, self.configs)["country"]), ["remote", "remote"])
        # Kept for the ranking; whether it is open to Tunisia is decided later.
        self.assertEqual(list(in_target_countries(jobs, self.configs)), [True, True])

    def test_generic_remote_feed_jobs_become_remote(self):
        jobs = self.frame([
            {"site": "arbeitnow", "location": "Remote", "is_remote": True},
            {"site": "arbeitnow", "location": "Berlin", "is_remote": True},
        ])

        self.assertEqual(list(assign_countries(jobs, self.configs)["country"]), ["remote", "germany"])

    def test_without_remote_in_your_countries(self):
        configs = search_configs(["germany"])
        jobs = self.frame([{"site": "remotive", "location": "USA Only", "is_remote": True}])

        self.assertIsNone(assign_countries(jobs, configs)["country"].iloc[0])
        self.assertEqual(list(in_target_countries(jobs, configs)), [False])


class TestOpenToTunisia(unittest.TestCase):

    def test_regions(self):
        cases = {
            "Anywhere in the World": "yes", "Worldwide": "yes", "EMEA": "yes",
            "Europe, Middle East and Africa": "yes", "USA, Europe, Africa": "yes",
            "CET +/- 2 hours": "yes", "UTC+1": "yes",
            "USA Only": "no", "Canada, UK": "no", "North America": "no", "UTC-5": "no",
            "Germany": "no",
            "Europe": "europe", "EU only": "europe",
            "Remote": "unknown", "": "unknown",
        }

        for region, expected in cases.items():
            self.assertEqual(analyze_remote_open(region, "")["remote_open"], expected, region)

    def test_the_ad_decides_when_the_board_gives_no_region(self):
        self.assertEqual(analyze_remote_open("Remote", "You must be based in the US.")["remote_open"], "no")
        self.assertEqual(analyze_remote_open("Remote", "We pay contractors worldwide via Deel.")["remote_open"], "yes")
        self.assertEqual(analyze_remote_open("Remote", "Work during CET business hours.")["remote_open"], "yes")

    def test_describing_the_team_is_not_a_rule(self):
        for text in ("Our team is based across the UK, EU and US, and this is our main focus.",
                     "We are a US-based company.",
                     "Health benefits are limited to team members in the US."):
            self.assertEqual(analyze_remote_open("Remote", text)["remote_open"], "unknown", text)

        for text in ("Candidates must currently live in Canada.", "You must have the right to work in the UK.",
                     "UK residents only."):
            self.assertEqual(analyze_remote_open("Remote", text)["remote_open"], "no", text)

    def test_the_board_says_so(self):
        verdict = analyze_remote_open("Germany, Tunisia", "", source_hint="open_to_you")
        self.assertEqual(verdict["remote_open"], "yes")


class TestRemoteDecisions(unittest.TestCase):

    def remote(self, location, text=FILLER * 4, hint=None):
        return evaluate(text, country="remote", location=location, source_hint=hint)

    def test_open_worldwide_is_recommended(self):
        job = self.remote("Anywhere in the World")

        self.assertIn("REMOTE_OPEN_TO_TUNISIA", job.eligibility_positives)
        self.assertEqual(job.eligibility_status, "likely")
        self.assertIn(job.application_bucket, ("apply_now", "apply_with_research"))

    def test_usa_only_is_skipped(self):
        job = self.remote("USA Only")

        self.assertIn("REMOTE_NOT_OPEN_TO_TUNISIA", job.eligibility_blockers)
        self.assertEqual(job.application_bucket, "skip")

    def test_europe_only_is_a_warning(self):
        job = self.remote("Europe")

        self.assertIn("REMOTE_EUROPE_ONLY", job.eligibility_warnings)
        self.assertNotEqual(job.application_bucket, "skip")

    def test_no_visa_sponsorship_does_not_block_a_remote_job(self):
        job = self.remote("Worldwide", FILLER * 2 + "We do not offer visa sponsorship. " + FILLER * 2)

        self.assertNotIn("NO_VISA_SPONSORSHIP", job.eligibility_blockers)
        self.assertIn("SAYS_NO_VISA_SPONSORSHIP", job.eligibility_warnings)

    def test_country_jobs_are_unchanged(self):
        job = evaluate(FILLER * 2 + "We do not offer visa sponsorship. " + FILLER * 2,
                       country="germany", location="Berlin")

        self.assertIn("NO_VISA_SPONSORSHIP", job.eligibility_blockers)
        self.assertIsNone(job.remote_open)


class TestLinkedInRemoteSearch(unittest.TestCase):

    def test_remote_profile_asks_for_the_remote_filter(self):
        from pipeline import collect_jobs

        class Source:
            name = "linkedin"
            last_search_rate_limited = False

            def __init__(self):
                self.calls = []

            def search(self, **kwargs):
                self.calls.append(kwargs)
                return pd.DataFrame()

        source = Source()
        collect_jobs(source, search_configs(["remote"]), 10, 72, sleep=NO_SLEEP)

        self.assertTrue(source.calls)
        self.assertTrue(all(call.get("remote") for call in source.calls))
        self.assertEqual(source.calls[0]["location"], "EMEA")

        source = Source()
        collect_jobs(source, search_configs(["germany"]), 10, 72, sleep=NO_SLEEP)
        self.assertFalse(any(call.get("remote") for call in source.calls))


class TestNotSoftware(unittest.TestCase):

    def test_construction_engineers_are_not_software(self):
        from sources.relevance import is_tech_title

        for title in ("Architectural Engineer", "Structural Engineer - Steel Fabrication"):
            self.assertFalse(is_tech_title(title), title)

        self.assertTrue(is_tech_title("Full Stack Developer, Construction Software"))


if __name__ == "__main__":
    unittest.main()