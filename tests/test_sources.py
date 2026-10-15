"""The feed sources, tested with sample API responses (no internet)."""

import contextlib
import io
import unittest

import pandas as pd

from pipeline import collect_feeds, deduplicate, merge_across_sites
from sources import ArbeitnowSource, GreenhouseSource, LeverSource
from sources.http import FetchError, get_json
from sources.relevance import in_country, is_tech_title
from sources.text import html_to_text


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


def fake_get(pages):
    """pages: list of payloads returned one after another."""
    calls = []

    def get(url, params=None, **kwargs):
        calls.append((url, params))
        payload = pages[min(len(calls) - 1, len(pages) - 1)]
        return payload if isinstance(payload, FakeResponse) else FakeResponse(payload)

    get.calls = calls
    return get


ARBEITNOW_JOB = {
    "slug": "full-stack-developer-berlin-123",
    "company_name": "Beispiel GmbH",
    "title": "Full Stack Developer (m/w/d)",
    "description": "<h2>Your tasks</h2>\n<ul><li>React &amp; TypeScript</li><li>Node.js</li></ul>",
    "remote": False,
    "url": "https://www.arbeitnow.com/jobs/companies/beispiel/full-stack-developer-berlin-123",
    "tags": ["IT"],
    "job_types": ["full time"],
    "location": "Berlin",
    "created_at": 1792049481,
}

ARBEITNOW_HR = dict(ARBEITNOW_JOB, slug="recruiter-1", title="Junior Recruiter (m/w/d)")


class TestHtmlToText(unittest.TestCase):

    def test_lists_and_entities(self):
        self.assertEqual(
            html_to_text("<h2>Tasks</h2><ul><li>React &amp; TS</li><li>Node</li></ul>"),
            "Tasks\n* React & TS\n* Node",
        )

    def test_escaped_html_from_greenhouse(self):
        self.assertEqual(html_to_text("&lt;p&gt;Hello&lt;/p&gt;&lt;p&gt;World&lt;/p&gt;"), "Hello\nWorld")

    def test_empty_values(self):
        self.assertEqual(html_to_text(None), "")
        self.assertEqual(html_to_text("   "), "")


class TestRelevance(unittest.TestCase):

    def test_tech_titles(self):
        for title in ["Full Stack Developer (m/w/d)", "Softwareentwickler", "Backend Engineer",
                      "Frontend-Entwickler", "Web Developer"]:
            with self.subTest(title=title):
                self.assertTrue(is_tech_title(title))

    def test_not_tech_titles(self):
        for title in ["Junior Recruiter", "Sales Engineer", "Werkstudent Softwareentwicklung",
                      "Elektroingenieur", "Steuerberater"]:
            with self.subTest(title=title):
                self.assertFalse(is_tech_title(title))

    def test_country(self):
        self.assertTrue(in_country("Berlin, Germany", ["germany"]))
        self.assertTrue(in_country("München", ["münchen"]))
        self.assertFalse(in_country("New York, NY", ["germany", "berlin"]))


class TestArbeitnow(unittest.TestCase):

    def test_pages_until_empty_and_only_tech_jobs(self):
        get = fake_get([{"data": [ARBEITNOW_JOB, ARBEITNOW_HR]}, {"data": []}])

        jobs = ArbeitnowSource(max_pages=5, get=get).fetch()

        self.assertEqual(len(get.calls), 2)
        self.assertEqual(len(jobs), 1)

        row = jobs.iloc[0]
        self.assertEqual(row["id"], "an-full-stack-developer-berlin-123")
        self.assertEqual(row["site"], "arbeitnow")
        self.assertEqual(row["company"], "Beispiel GmbH")
        self.assertEqual(row["date_posted"], "2026-10-15")
        self.assertIn("* React & TypeScript", row["description"])

    def test_stops_when_a_page_repeats(self):
        get = fake_get([{"data": [ARBEITNOW_JOB]}])

        ArbeitnowSource(max_pages=5, get=get).fetch()

        self.assertEqual(len(get.calls), 2)


class TestGreenhouse(unittest.TestCase):

    def test_jobs(self):
        get = fake_get([{"jobs": [{
            "id": 98765, "title": "Senior Backend Engineer",
            "location": {"name": "Berlin, Germany"},
            "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/98765",
            "updated_at": "2026-10-12T10:00:00-04:00",
            "content": "&lt;p&gt;We offer visa support.&lt;/p&gt;",
            "company_name": "Acme",
        }]}])

        jobs = GreenhouseSource("acme", get=get).fetch()
        row = jobs.iloc[0]

        self.assertEqual(get.calls[0][1], {"content": "true"})
        self.assertEqual(row["id"], "gh-acme-98765")
        self.assertEqual(row["company"], "Acme")
        self.assertEqual(row["date_posted"], "2026-10-12")
        self.assertEqual(row["description"], "We offer visa support.")

    def test_unknown_board(self):
        get = fake_get([FakeResponse({}, status=404)])

        with self.assertRaisesRegex(FetchError, "not found"):
            GreenhouseSource("nope", get=get).fetch()


class TestLever(unittest.TestCase):

    def test_postings(self):
        get = fake_get([[{
            "id": "abc-123", "text": " Full Stack Engineer ",
            "categories": {"location": "Munich, Germany", "commitment": "Full-time"},
            "descriptionPlain": "Build our product.",
            "lists": [{"text": "Requirements", "content": "<li>React</li><li>Python</li>"}],
            "additionalPlain": "Relocation support available.",
            "hostedUrl": "https://jobs.lever.co/acme/abc-123",
            "createdAt": 1792049481000,
            "workplaceType": "hybrid",
        }]])

        row = LeverSource("acme", get=get).fetch().iloc[0]

        self.assertEqual(row["id"], "lv-acme-abc-123")
        self.assertEqual(row["title"], "Full Stack Engineer")
        self.assertEqual(row["location"], "Munich, Germany")
        self.assertIn("Requirements\n* React\n* Python", row["description"])
        self.assertIn("Relocation support available.", row["description"])


class TestHttp(unittest.TestCase):

    def test_retries_on_429_then_succeeds(self):
        get = fake_get([FakeResponse({}, status=429), {"ok": True}])
        waits = []

        self.assertEqual(get_json("https://x", get=get, sleep=waits.append), {"ok": True})
        self.assertEqual(len(waits), 1)

    def test_network_error_gives_a_readable_message(self):
        def broken(*args, **kwargs):
            raise ConnectionError("no internet")

        with self.assertRaisesRegex(FetchError, "network error"):
            get_json("https://x", get=broken, sleep=lambda s: None)


class TestCollectFeeds(unittest.TestCase):

    def test_tech_jobs_from_all_countries_are_kept_for_later(self):
        class Feed:
            name = "greenhouse:acme"

            def fetch(self):
                return pd.DataFrame([
                    {"site": "greenhouse", "title": "Backend Engineer", "location": "Berlin, Germany"},
                    {"site": "greenhouse", "title": "Backend Engineer", "location": "New York, NY"},
                    {"site": "greenhouse", "title": "Office Manager", "location": "Berlin, Germany"},
                ])

        class Broken:
            name = "lever:broken"

            def fetch(self):
                raise RuntimeError("404")

        configs = [{"location": "Germany", "location_keywords": ["germany", "berlin"]}]

        with contextlib.redirect_stdout(io.StringIO()) as printed:
            jobs = collect_feeds([Feed(), Broken()], configs)

        # Both engineer jobs are stored (Berlin now, New York for later);
        # the office manager is not a tech role.
        self.assertEqual(sorted(jobs["location"]), ["Berlin, Germany", "New York, NY"])
        self.assertIn("1 of them in your countries", printed.getvalue())
        self.assertIn("Skipped", printed.getvalue())


class TestTargetCountries(unittest.TestCase):

    def test_feed_jobs_need_a_matching_location_or_remote(self):
        from sources.relevance import in_target_countries

        frame = pd.DataFrame([
            {"site": "linkedin", "location": "Somewhere", "is_remote": False},   # search site: kept
            {"site": "arbeitnow", "location": "Berlin", "is_remote": False},     # German city
            {"site": "arbeitnow", "location": "Paris, France", "is_remote": False},
            {"site": "arbeitnow", "location": "Remote", "is_remote": True},
            {"site": "greenhouse", "location": "London", "is_remote": "False"},
            {"site": "arbeitnow", "location": "Werken op afstand", "is_remote": True},
            {"site": "arbeitnow", "location": "Remote, Netherlands", "is_remote": True},
            {"site": "arbeitnow", "location": "Remote - Europe", "is_remote": True},
        ])
        configs = [{"location_keywords": ["germany", "berlin"]}]

        self.assertEqual(list(in_target_countries(frame, configs)),
                         [True, True, False, True, False, False, False, True])


class TestTitlesFromYourRun(unittest.TestCase):
    """Arbeitnow titles from the run of 2026-10-15."""

    def test_business_and_sales_titles_are_not_tech(self):
        for title in [
            "Director, Business Development", "Sales Development Representative (London - hybrid)",
            "Business Development Manager (AI Data Solutions)", "Engineering Manager - Data Platform (m/f/d)",
            "Staff Product Manager – E-Commerce Web Upper Funnel [CDI] (f/m/d)",
        ]:
            with self.subTest(title=title):
                self.assertFalse(is_tech_title(title))

    def test_developer_titles_are_tech(self):
        for title in ["Backend Entwickler", "Senior Full-Stack Developer – Laravel, Vue & Mobile (m/w/d)",
                      "Senior developer Novulo", "Software Development Engineer"]:
            with self.subTest(title=title):
                self.assertTrue(is_tech_title(title))

    def test_html_escaped_inside_html(self):
        text = html_to_text("<div>&lt;ul&gt;&lt;li&gt;Fluent German;&lt;/li&gt;&lt;/ul&gt;</div>")
        self.assertEqual(text, "* Fluent German;")

    def test_german_entity_is_not_a_language_requirement(self):
        from services.eligibility_analyzer import analyze_german_requirement

        text = "Some of the benefits listed here apply only to the German entity and to Junior-level roles or above."
        self.assertEqual(analyze_german_requirement(text, "en")["requirement"], "none_mentioned")


class TestSecondPhase3Run(unittest.TestCase):

    def test_umlaut_lost_on_one_site_still_merges(self):
        frame = pd.DataFrame([
            {"id": "in-1", "site": "indeed", "job_url": "u1", "location": "Frankfurt",
             "title": "Full-Stack Software Developer (m/f/d): TETTRIX project",
             "company": "Senckenberg Gesellschaft für Naturforschung", "description": "a"},
            {"id": "li-2", "site": "linkedin", "job_url": "u2", "location": "Frankfurt, Germany",
             "title": "Full-Stack Software Developer (m/f/d): TETTRIX project",
             "company": "Senckenberg Gesellschaft fur Naturforschung", "description": "bb"},
        ])

        self.assertEqual(len(merge_across_sites(frame)), 1)

    def test_company_suffix_in_brackets_and_city_variants_still_merge(self):
        frame = pd.DataFrame([
            {"id": "in-1", "site": "indeed", "job_url": "u1", "location": "Frankfurt am Main, HE, Germany",
             "title": "Full-Stack Software Developer (m/f/d): TETTRIX project",
             "company": "Senckenberg Gesellschaft für Naturforschung", "description": "a"},
            {"id": "in-2", "site": "indeed", "job_url": "u2", "location": "Frankfurt",
             "title": "Full-Stack Software Developer (m/f/d): TETTRIX project",
             "company": "Senckenberg Gesellschaft fur Naturforschung (SGN)", "description": "bb"},
        ])

        self.assertEqual(len(merge_across_sites(frame)), 1)

    def test_working_student_is_not_for_you(self):
        from models import Job
        from services.experience_analyzer import ExperienceAnalyzer
        from services.experience_matcher import ExperienceMatcher
        from services.seniority_matcher import SeniorityMatcher
        from services.target_classifier import TargetClassifier

        from .helpers import make_profile

        for title in ["Working Student Node.js/React Software Developer (m/f/d) InsurTech",
                      "Werkstudent Softwareentwicklung (m/w/d)", "Praktikum Frontend"]:
            with self.subTest(title=title):
                job = Job(title=title, role_match_score=90, skills_match_score=100)
                job.seniority = ExperienceAnalyzer().extract_seniority(title)
                profile = make_profile()

                result = TargetClassifier.classify(
                    job, profile,
                    ExperienceMatcher.match(job, profile),
                    SeniorityMatcher.match(job, profile),
                )

                self.assertEqual(job.seniority, "Intern")
                self.assertEqual(result["target_category"], "low_priority")


class TestMergeAcrossSites(unittest.TestCase):

    def frame(self):
        return pd.DataFrame([
            {"id": "li-1", "site": "linkedin", "job_url": "https://linkedin/1",
             "title": "Full Stack Developer (m/w/d)", "company": "Beispiel GmbH",
             "location": "Berlin, Germany", "description": "short"},
            {"id": "in-9", "site": "indeed", "job_url": "https://indeed/9",
             "title": "Full Stack Developer (w/m/d)", "company": "Beispiel",
             "location": "Berlin", "description": "a much longer description from indeed"},
            {"id": "li-2", "site": "linkedin", "job_url": "https://linkedin/2",
             "title": "Full Stack Developer (m/w/d)", "company": "Beispiel GmbH",
             "location": "Hamburg, Germany", "description": "other city"},
        ])

    def test_same_job_on_two_sites_becomes_one(self):
        merged = merge_across_sites(self.frame())

        self.assertEqual(len(merged), 2)

        berlin = merged[merged["id"] == "in-9"].iloc[0]
        self.assertEqual(berlin["found_on"], "indeed, linkedin")

    def test_same_title_in_another_city_stays_separate(self):
        merged = merge_across_sites(self.frame())
        self.assertIn("li-2", list(merged["id"]))

    def test_deduplicate_runs_the_merge(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(len(deduplicate(self.frame())), 2)


class TestJobSpyCountry(unittest.TestCase):

    def test_indeed_gets_the_country(self):
        import sys
        import types

        captured = {}

        fake = types.ModuleType("jobspy")

        def scrape_jobs(**kwargs):
            captured.update(kwargs)
            return pd.DataFrame([{"id": "in-1", "title": "Dev"}])

        fake.scrape_jobs = scrape_jobs
        real = sys.modules.get("jobspy")
        sys.modules["jobspy"] = fake
        sys.modules.pop("sources.jobspy_source", None)

        try:
            from sources.jobspy_source import JobSpySource

            JobSpySource(sites=["indeed"]).search(
                search_term="Developer", location="Germany",
                results_wanted=10, hours_old=72, country="germany",
            )
        finally:
            sys.modules.pop("sources.jobspy_source", None)
            if real is not None:
                sys.modules["jobspy"] = real
            else:
                sys.modules.pop("jobspy", None)

        self.assertEqual(captured["site_name"], ["indeed"])
        self.assertEqual(captured["country_indeed"], "germany")


class TestSourcesCheck(unittest.TestCase):

    def test_reports_working_and_missing_boards(self):
        import sources_check

        original = sources_check.GreenhouseSource

        class FakeBoard:
            def __init__(self, name):
                self.name = f"greenhouse:{name}"
                self.ok = name == "acme"

            def fetch(self):
                if not self.ok:
                    raise FetchError("not found (404)")
                return pd.DataFrame([{"title": "Backend Engineer", "location": "Berlin, Germany"}])

        sources_check.GreenhouseSource = FakeBoard
        printed = []

        try:
            sources_check.main(["greenhouse", "acme", "nope"], output=printed.append)
        finally:
            sources_check.GreenhouseSource = original

        text = "\n".join(printed)
        self.assertIn("1 kept", text)
        self.assertIn("not found", text)
        self.assertIn("GREENHOUSE_BOARDS = ['acme']", text)


if __name__ == "__main__":
    unittest.main()