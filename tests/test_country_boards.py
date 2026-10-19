"""Japan and Poland job boards, Adzuna, and the remote fixes from the first remote run."""

import json
import os
import unittest
from unittest import mock

import pandas as pd

from countries import search_configs
from services.eligibility_analyzer import analyze_remote_open
from sources import AdzunaSource, adzuna_sources, country_board_sources
from sources.listed_boards import japandev, justjoinit, nofluffjobs, tokyodev
from tests.test_gulf_and_languages import FILLER, evaluate
from tests.test_remote import NO_SLEEP, fake_get


def posting(title, company, city="Tokyo", country="JP"):
    data = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": title,
        "hiringOrganization": {"@type": "Organization", "name": company},
        "jobLocation": {"@type": "Place", "address": {"addressLocality": city, "addressCountry": country}},
        "datePosted": "2026-10-16",
        "description": "<p>" + FILLER * 3 + "</p>",
    }
    return f'<html><script type="application/ld+json">{json.dumps(data)}</script><h1>{title}</h1></html>'


TOKYODEV_LIST = """
<ul>
 <li><h3><a href="/companies/autify">Autify</a></h3>
   <a href="/companies/autify/jobs/frontend-engineer">Frontend Engineer</a>
   <a href="/jobs/no-japanese-required">No Japanese required</a>
   <a href="/jobs/apply-from-abroad">Apply from abroad</a></li>
 <li><h3><a href="/companies/moneyforward">Money Forward</a></h3>
   <a href="https://www.tokyodev.com/companies/moneyforward/jobs/full-stack-engineer-tokyo">Full Stack Engineer</a>
   <a href="/jobs/business-japanese">Business Japanese</a>
   <a href="/jobs/apply-from-abroad">Apply from abroad</a></li>
 <li><a href="/companies/moneyforward/jobs/engineering-manager">Engineering Manager</a></li>
</ul>"""


class TestTokyoDev(unittest.TestCase):

    def source(self, known=()):
        get = fake_get({
            "/jobs/apply-from-abroad": TOKYODEV_LIST,
            "/jobs/frontend-engineer": posting("Frontend Engineer", "Autify"),
            "/jobs/full-stack-engineer-tokyo": posting("Full Stack Engineer", "Money Forward"),
        })
        return tokyodev(get=get, sleep=NO_SLEEP, known_ids=known), get

    def test_reads_the_list_and_opens_tech_jobs(self):
        source, _ = self.source()
        jobs = source.fetch()

        # "Engineering Manager" is not a tech title: not opened.
        self.assertEqual(sorted(jobs["title"]), ["Frontend Engineer", "Full Stack Engineer"])
        self.assertEqual(source.stats["listed"], 3)
        self.assertEqual(source.stats["structured"], 2)

        row = jobs.set_index("title").loc["Frontend Engineer"]
        self.assertEqual(row["site"], "tokyodev")
        self.assertEqual(row["source_hint"], "visa")
        self.assertIn("Japan", row["location"])
        self.assertTrue(row["id"].startswith("td-"))
        self.assertIn("Japanese is not required.", row["description"])

    def test_badges_become_language_requirements(self):
        source, _ = self.source()
        jobs = source.fetch().set_index("title")

        business = jobs.loc["Full Stack Engineer", "description"]
        self.assertIn("business level", business)
        self.assertNotIn("Japanese language skills are required.", business)

        job = evaluate(business, country="japan", location="Tokyo, Japan")
        self.assertIn("JAPANESE_REQUIRED", job.eligibility_blockers)

        job = evaluate(jobs.loc["Frontend Engineer", "description"], country="japan", location="Tokyo, Japan")
        self.assertNotIn("JAPANESE_REQUIRED", job.eligibility_blockers)

    def test_saved_jobs_are_not_opened_again(self):
        source, _ = self.source()
        first = source.fetch()

        source, get = self.source(known=set(first["id"]))
        self.assertTrue(source.fetch().empty)
        self.assertEqual(len(get.calls), 1)    # only the list page

    def test_no_job_links_is_an_error(self):
        source = tokyodev(get=fake_get({"tokyodev.com": "<html>new layout</html>"}), sleep=NO_SLEEP)

        with self.assertRaises(Exception):
            source.fetch()


class TestBoardLocations(unittest.TestCase):

    def test_where_a_board_job_belongs(self):
        board = justjoinit()

        self.assertEqual(board.place("Warszawa, PL"), ("Warszawa, PL, Poland", "poland", False))
        self.assertEqual(board.place(""), ("Poland", "poland", False))
        # Another country: left alone, never "London, GB, Poland".
        self.assertEqual(board.place("London, GB"), ("London, GB", None, False))

    def test_a_list_of_the_whole_world_is_a_remote_job(self):
        location, country, remote = nofluffjobs().place(
            "Poland | Hungary | Austria | Germany | United States | --- | Afghanistan | Tunisia | Zambia")

        self.assertEqual((country, remote), ("remote", True))
        self.assertEqual(analyze_remote_open(location, "")["remote_open"], "yes")

    def test_board_country_counts_for_the_ranking(self):
        from sources.relevance import in_target_countries

        frame = pd.DataFrame([
            {"site": "nofluffjobs", "location": "Remote: Poland, United States", "search_country": "remote",
             "is_remote": True},
            {"site": "nofluffjobs", "location": "Remote: Poland, United States", "search_country": "remote",
             "is_remote": True},
        ])

        self.assertEqual(list(in_target_countries(frame, search_configs(["poland", "remote"]))), [True, True])
        self.assertEqual(list(in_target_countries(frame, search_configs(["poland"]))), [False, False])

    def test_japan_jobs_are_not_remote_only_inside_japan(self):
        page = '<a href="/companies/a/jobs/software-engineer">x</a> No Japanese required Fully remote Apply from abroad'
        sentences = dict(tokyodev().job_links(page))["/companies/a/jobs/software-engineer"]

        self.assertFalse(any("remote" in s.lower() for s in sentences))


class TestOtherBoardLinks(unittest.TestCase):

    def test_japandev(self):
        page = '<a href="/jobs/henngee/full-stack-developer-1234">x</a> Apply from Abroad ' \
               '<a href="/jobs/solafune/software-engineer-99">y</a> Japanese Required'
        links = dict(japandev().job_links(page))

        self.assertEqual(set(links), {"/jobs/henngee/full-stack-developer-1234", "/jobs/solafune/software-engineer-99"})
        self.assertIn("Japanese language skills are required.", links["/jobs/solafune/software-engineer-99"])
        self.assertEqual(japandev().job_id("/jobs/henngee/full-stack-developer-1234"), "jd-1234")

    def test_justjoinit(self):
        page = '<a href="/job-offer/acme-senior-react-developer-warszawa-javascript">x</a>' \
               '<a href="https://justjoin.it/job-offer/beta-php-developer-krakow-php">y</a>'
        self.assertEqual(len(justjoinit().job_links(page)), 2)

    def test_nofluffjobs(self):
        page = '<a href="/pl/job/frontend-developer-acme-warszawa-1">x</a><a href="/job/backend-dev-beta">y</a>'
        self.assertEqual(len(nofluffjobs().job_links(page)), 2)

    def test_boards_follow_the_countries_searched(self):
        names = lambda keys: [s.name for s in country_board_sources(search_configs(keys))]

        self.assertEqual(names(["japan"]), ["tokyodev", "japandev"])
        self.assertEqual(names(["poland", "germany"]), ["justjoinit", "nofluffjobs"])
        self.assertEqual(names(["germany"]), [])


ADZUNA_ANSWER = {"results": [
    {"id": "4711", "title": "<strong>React</strong> Developer", "redirect_url": "https://www.adzuna.de/land/ad/4711",
     "created": "2026-10-17T08:00:00Z", "company": {"display_name": "Acme GmbH"},
     "location": {"display_name": "Berlin"}, "description": "We build web apps with React..."},
    {"id": "4712", "title": "Web Developer", "redirect_url": "https://www.adzuna.de/land/ad/4712",
     "created": "2026-10-16T08:00:00Z", "company": {"display_name": "Beta"},
     "location": {"display_name": "Hamburg, Deutschland"}, "description": "PHP"},
]}


class TestAdzuna(unittest.TestCase):

    def test_reads_one_country(self):
        config = search_configs(["germany"])[0]
        get = fake_get({"api.adzuna.com": ADZUNA_ANSWER})
        jobs = AdzunaSource(config, "id", "key", terms=["react developer"], get=get, sleep=NO_SLEEP).fetch()

        self.assertEqual(list(jobs["id"]), ["az-4711", "az-4712"])
        row = jobs.iloc[0]
        self.assertEqual(row["title"], "React Developer")       # <strong> removed
        self.assertEqual(row["location"], "Berlin, Germany")
        self.assertEqual(row["search_country"], "germany")
        self.assertEqual(row["date_posted"], "2026-10-17")

        url, params = get.calls[0]
        self.assertIn("/jobs/de/search/1", url)
        self.assertEqual(params["what"], "react developer")
        self.assertEqual(params["app_key"], "key")

    def test_without_a_key_it_is_skipped(self):
        with mock.patch.dict(os.environ, {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""}):
            self.assertEqual(adzuna_sources(search_configs(["germany", "uk"])), [])

    def test_with_a_key_only_covered_countries(self):
        with mock.patch.dict(os.environ, {"ADZUNA_APP_ID": "a", "ADZUNA_APP_KEY": "b"}):
            sources = adzuna_sources(search_configs(["germany", "qatar", "uk"]))

        self.assertEqual([s.country for s in sources], ["de", "gb"])
        self.assertEqual(len(sources[0].terms), 3)       # 3 calls per country

    def test_a_refused_key_stops(self):
        config = search_configs(["uk"])[0]
        get = fake_get({})                                 # every call: 404 here

        class Refuse:
            status_code = 401
            text = ""

        calls = []

        def refuse(url, params=None, timeout=None, headers=None):
            calls.append(url)
            return Refuse()

        jobs = AdzunaSource(config, "id", "bad", terms=["a", "b", "c"], get=refuse, sleep=NO_SLEEP).fetch()

        self.assertTrue(jobs.empty)
        self.assertEqual(len(calls), 1)

    def test_adzuna_jobs_count_for_their_country(self):
        from pipeline import assign_countries
        from sources.relevance import in_target_countries

        frame = pd.DataFrame([{"site": "adzuna", "location": "Somewhere", "search_country": "germany"}])
        configs = search_configs(["germany"])

        self.assertEqual(assign_countries(frame, configs)["country"].iloc[0], "germany")
        self.assertEqual(list(in_target_countries(frame, configs)), [True])


class TestRemoteFixes(unittest.TestCase):

    LEMON = ("Anywhere in the World, 🇦🇩 Andorra, 🇦🇱 Albania, 🇦🇷 Argentina, 🇦🇹 Austria, "
             "🇲🇦 Morocco, 🇺🇸 United States of America, 🇺🇾 Uruguay, 🇻🇳 Viet Nam, and 🇿🇦 South Africa")

    def test_a_country_list_without_tunisia(self):
        self.assertEqual(analyze_remote_open(self.LEMON, "")["remote_open"], "no")
        self.assertEqual(analyze_remote_open(self.LEMON + ", 🇹🇳 Tunisia", "")["remote_open"], "yes")
        self.assertEqual(analyze_remote_open("South Africa", "")["remote_open"], "no")
        self.assertEqual(analyze_remote_open("North Africa", "")["remote_open"], "yes")

    def test_remote_in_other_languages_is_not_a_place(self):
        for region in ("Remoto", "Remota", "Télétravail"):
            self.assertEqual(analyze_remote_open(region, "")["remote_open"], "unknown", region)

    def test_remote_reasons_do_not_talk_about_visas(self):
        job = evaluate(FILLER * 4, country="remote", location="Worldwide")
        job.target_category = "needs_review"

        from services.eligibility_evaluator import ApplicationBucketer
        ApplicationBucketer.assign(job)

        self.assertNotIn("visa", job.bucket_reason.lower())

    def test_long_locations_are_shortened_in_the_report(self):
        from reporting import _short

        self.assertLessEqual(len(_short(self.LEMON)), 65)
        self.assertEqual(_short("Berlin"), "Berlin")


if __name__ == "__main__":
    unittest.main()