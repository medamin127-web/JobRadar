"""Relocate.me: list pages -> job links (with the place) -> job page text."""

import unittest

from sources.jsonld import page_text
from sources.relocateme import RelocateMeSource, job_links, location_of

from .test_jaabz import Response, fake_get


def list_page(*paths):
    links = "".join(f'<a class="job" href="{path}">job</a>' for path in paths)
    return f"<html><nav><a href='/moving-to-germany'>Germany</a></nav>{links}</html>"


JOB_PAGE = """
<html><head><script>var tracking = "visa sponsorship";</script><style>p{}</style></head>
<body><nav>Jobs | Visa guides</nav>
<h1>Senior Backend Engineer</h1>
<p>We build payments with Node.js and PostgreSQL. 2+ years of experience.</p>
<h3>Advanced relocation package</h3><ul><li>Flight ticket</li><li>Visa services</li></ul>
<footer>All rights reserved</footer></body></html>
"""


class TestLinks(unittest.TestCase):

    def test_links_carry_country_city_and_company(self):
        page = list_page(
            "https://relocate.me/netherlands/amsterdam/catawiki/lead-security-engineer-10303",
            "/germany/berlin/acme-gmbh/full-stack-developer-10400",
            "/remote/remote/the-global-move/1700-curated-visa-sponsorship-jobs-paid-option-10080",
            "/germany/berlin/acme-gmbh/full-stack-developer-10400",
        )
        links = job_links(page)

        self.assertEqual([link["number"] for link in links], ["10303", "10400"])
        self.assertEqual(links[1]["path"], "/germany/berlin/acme-gmbh/full-stack-developer-10400")
        self.assertEqual(location_of(links[0]), "Amsterdam, Netherlands")
        self.assertEqual(location_of({"country": "remote", "city": "remote"}), "Remote")

    def test_menu_links_are_not_jobs(self):
        self.assertEqual(job_links("<a href='/moving-to-germany'>x</a><a href='/international-jobs?page=2'>2</a>"), [])


class TestPageText(unittest.TestCase):

    def test_scripts_menus_and_footer_are_left_out(self):
        text = page_text(JOB_PAGE)

        self.assertTrue(text.startswith("Senior Backend Engineer"))
        self.assertIn("* Visa services", text)
        self.assertNotIn("tracking", text)
        self.assertNotIn("Visa guides", text)
        self.assertNotIn("All rights reserved", text)

    def test_similar_jobs_at_the_end_are_cut(self):
        page = "<h1>Dev</h1><p>Our job.</p><h3>These jobs may fit you</h3><p>Other job</p>"
        self.assertEqual(page_text(page), "Dev\nOur job.")


class TestSource(unittest.TestCase):

    def test_relocation_offered_is_cut_from_titles(self):
        page = JOB_PAGE.replace("<h1>Senior Backend Engineer</h1>",
                                "<h1>Senior Backend Engineer | Relocation Offered</h1>")
        pages = {
            "international-jobs": list_page("/germany/berlin/acme/backend-engineer-9"),
            "international-jobs?page=2": list_page(),
            "/germany/berlin/acme/backend-engineer-9": page,
        }
        jobs = RelocateMeSource(get=fake_get(pages), sleep=lambda _: None).fetch()

        self.assertEqual(jobs.iloc[0]["title"], "Senior Backend Engineer")

    def test_visa_in_the_package_next_to_a_long_description(self):
        import json

        posting = {"@type": "JobPosting", "title": "Web Developer",
                   "description": "<p>" + "We build React apps. " * 80 + "</p>"}
        page = (
            '<script type="application/ld+json">' + json.dumps(posting) + "</script>"
            "<h1>Web Developer</h1><h3>Advanced relocation package</h3>"
            "<ul><li>Flight ticket</li><li>Visa services</li></ul>"
        )
        pages = {
            "international-jobs": list_page("/germany/berlin/acme/web-developer-7"),
            "international-jobs?page=2": list_page(),
            "/germany/berlin/acme/web-developer-7": page,
        }
        jobs = RelocateMeSource(get=fake_get(pages), sleep=lambda _: None).fetch()

        self.assertEqual(jobs.iloc[0]["source_hint"], "visa")
        self.assertNotIn("Flight ticket", jobs.iloc[0]["description"])

    def test_reads_tech_jobs_with_place_and_visa_hint(self):
        pages = {
            "international-jobs": list_page(
                "/germany/berlin/acme-gmbh/senior-backend-engineer-1",
                "/spain/madrid/acme/head-of-marketing-2",          # not tech: not opened
            ),
            "international-jobs?page=2": list_page(),
            "/germany/berlin/acme-gmbh/senior-backend-engineer-1": JOB_PAGE,
        }
        source = RelocateMeSource(max_pages=3, get=fake_get(pages), sleep=lambda _: None)
        jobs = source.fetch()

        self.assertEqual(list(jobs["id"]), ["rm-1"])
        job = jobs.iloc[0]
        self.assertEqual(job["site"], "relocateme")
        self.assertEqual(job["location"], "Berlin, Germany")
        self.assertEqual(job["company"], "Acme Gmbh")
        self.assertEqual(job["title"], "Senior Backend Engineer")
        self.assertEqual(job["source_hint"], "visa")
        self.assertIn("Node.js", job["description"])

    def test_package_without_visa_counts_as_relocation_only(self):
        page = JOB_PAGE.replace("<li>Visa services</li>", "")
        pages = {
            "international-jobs": list_page("/germany/berlin/acme/web-developer-5"),
            "international-jobs?page=2": list_page(),
            "/germany/berlin/acme/web-developer-5": page,
        }
        jobs = RelocateMeSource(get=fake_get(pages), sleep=lambda _: None).fetch()

        self.assertEqual(jobs.iloc[0]["source_hint"], "relocation")

    def test_known_jobs_are_skipped(self):
        pages = {
            "international-jobs": list_page("/germany/berlin/acme/web-developer-5"),
            "international-jobs?page=2": list_page(),
        }
        jobs = RelocateMeSource(known_ids={"rm-5"}, get=fake_get(pages), sleep=lambda _: None).fetch()

        self.assertTrue(jobs.empty)


if __name__ == "__main__":
    unittest.main()


class TestSourcesCheckVerdicts(unittest.TestCase):

    def test_each_job_gets_jobradars_verdict(self):
        import pandas as pd

        import sources_check

        from .helpers import make_profile

        jobs = pd.DataFrame([
            {"id": "rm-1", "site": "relocateme", "title": "Full Stack Developer",
             "company": "Acme", "location": "Berlin, Germany", "source_hint": "visa",
             "description": "We build web apps with React, Node.js and PostgreSQL. "
                            "1+ years of experience. Relocation package and visa support. " * 3},
            {"id": "rm-2", "site": "relocateme", "title": "Senior CAD Design Engineer",
             "company": "Acme", "location": "Tokyo, Japan", "source_hint": "visa",
             "description": "CAD design of rocket parts, 8+ years of experience with CATIA. " * 3},
        ])
        printed = []
        sources_check.print_verdicts(jobs, printed.append, profile=make_profile())

        text = "\n".join(printed)
        self.assertIn("Full Stack Developer", text)
        self.assertIn("skip", text)
        self.assertIn("recommended", text)
        # Your countries first.
        self.assertLess(text.index("Full Stack Developer"), text.index("CAD Design"))