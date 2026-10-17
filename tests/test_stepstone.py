"""StepStone: search pages -> job links -> job pages (schema.org JobPosting)."""

import json
import unittest

from sources.http import FetchError
from sources.stepstone import StepStoneSource, job_links, slugify

from .test_jaabz import Response, fake_get


def search_page(*links, embedded=False):
    if embedded:
        # The same links inside the page's JSON, with escaped slashes.
        items = ",".join('{"url":"\\/' + link.lstrip("/") + '"}' for link in links)
        return f'<html><script>window.__DATA__={{"items":[{items}]}}</script></html>'

    return "<html>" + "".join(f'<a href="{link}">job</a>' for link in links) + "</html>"


def job_page(title="Full Stack Developer (m/w/d)", company="Acme GmbH"):
    posting = {
        "@context": "https://schema.org", "@type": "JobPosting",
        "title": title,
        "hiringOrganization": {"@type": "Organization", "name": company},
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "Berlin",
                                                     "addressCountry": "DE"}},
        "datePosted": "2026-10-15",
        "description": "<p>" + "We build web apps with React, Node.js and PostgreSQL. " * 30 + "</p>",
    }
    return f'<script type="application/ld+json">{json.dumps(posting)}</script><h1>{title}</h1>'


LINK_1 = "/stellenangebote--Full-Stack-Developer-m-w-d-Berlin-Acme-GmbH--14030765-inline.html"
LINK_2 = "/stellenangebote--Steuerberater-m-w-d-Hamburg-Kanzlei--14030766-inline.html"
LINK_3 = "/stellenangebote--Software-Engineer-Muenchen-ADAC--14030767-inline.html"


class TestLinks(unittest.TestCase):

    def test_links_in_html_and_in_embedded_json(self):
        for page in (search_page(LINK_1, LINK_3, LINK_1), search_page(LINK_1, LINK_3, embedded=True)):
            self.assertEqual(
                job_links(page),
                [("14030765", "Full-Stack-Developer-m-w-d-Berlin-Acme-GmbH"),
                 ("14030767", "Software-Engineer-Muenchen-ADAC")],
            )

    def test_search_address(self):
        self.assertEqual(slugify("Full Stack Developer"), "full-stack-developer")
        source = StepStoneSource(terms=["Web Developer"])
        self.assertEqual(source.search_url("Web Developer"), "https://www.stepstone.de/jobs/web-developer")


class TestSource(unittest.TestCase):

    def source(self, pages, **kwargs):
        return StepStoneSource(terms=["Full Stack Developer"], get=fake_get(pages),
                               sleep=lambda _: None, **kwargs)

    def test_reads_tech_jobs_as_a_germany_search(self):
        pages = {
            "jobs/full-stack-developer": search_page(LINK_1, LINK_2),
            LINK_1: job_page(),
        }
        source = self.source(pages)
        jobs = source.fetch()

        self.assertEqual(list(jobs["id"]), ["ss-14030765"])   # the tax adviser is not opened
        job = jobs.iloc[0]
        self.assertEqual(job["site"], "stepstone")
        self.assertEqual(job["company"], "Acme GmbH")
        self.assertEqual(job["location"], "Berlin, DE")
        self.assertEqual(job["search_country"], "germany")
        self.assertGreater(len(job["description"]), 1000)
        self.assertEqual(source.stats["structured"], 1)

    def test_known_jobs_are_not_opened(self):
        pages = {"jobs/full-stack-developer": search_page(LINK_1)}
        jobs = self.source(pages, known_ids={"ss-14030765"}).fetch()

        self.assertTrue(jobs.empty)

    def test_a_page_without_job_data_is_not_a_job(self):
        # Bot protection may answer 200 with a challenge page.
        pages = {
            "jobs/full-stack-developer": search_page(LINK_1),
            LINK_1: "<html><body>Please verify you are a human</body></html>",
        }
        source = self.source(pages)

        self.assertTrue(source.fetch().empty)
        self.assertEqual(source.stats["opened"], 1)
        self.assertEqual(source.stats["structured"], 0)

    def test_refused_search_raises_with_the_reason(self):
        pages = {"jobs/full-stack-developer": Response("", status=403)}

        with self.assertRaisesRegex(FetchError, "403"):
            self.source(pages).fetch()


class TestScraperBuildsStepStone(unittest.TestCase):

    def test_only_for_searched_countries_with_a_stepstone_site(self):
        import scraper
        from countries import search_configs

        sources = scraper.stepstone_sources(search_configs(["germany", "uae"]))

        self.assertEqual([s.country_key for s in sources], ["germany"])
        self.assertEqual(scraper.stepstone_sources(search_configs(["uae", "qatar"])), [])


if __name__ == "__main__":
    unittest.main()