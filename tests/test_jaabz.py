"""Jaabz: list pages -> job links -> job pages (schema.org JobPosting)."""

import json
import unittest

from sources.http import FetchError
from sources.jaabz import JaabzSource, job_links
from sources.jsonld import parse_job_page


def list_page(*links):
    cards = "".join(
        f'<div class="card"><a href="{link}">title</a><span>Visa Sponsorship</span></div>'
        for link in links
    )
    return f"<html><body>{cards}<a href='/jobs/programming'>Programming</a></body></html>"


def job_page(title="Backend Engineer", company="Torentify", country="NL", city="Amsterdam"):
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": title,
        "hiringOrganization": {"@type": "Organization", "name": company},
        "jobLocation": [{"@type": "Place", "address": {
            "@type": "PostalAddress", "addressLocality": city, "addressCountry": country}}],
        "datePosted": "2026-10-14T09:00:00+00:00",
        "employmentType": ["FULL_TIME"],
        "description": "<p>We build <strong>React</strong> apps.</p><ul><li>Visa sponsorship provided</li></ul>",
    }
    return (
        "<html><head><script type=\"application/ld+json\">"
        + json.dumps(posting)
        + "</script></head><body><h1>ignored</h1></body></html>"
    )


def real_layout_page(visa="active", relocation="inactive"):
    """A trimmed copy of a real Jaabz job page (October 2026)."""

    def badge(state, icon, name):
        check = '<i class="fas fa-check-circle benefit-check-icon"></i>' if state == "active" else ""
        return (f'<span class="benefit-tag {state}" itemprop="jobBenefits">'
                f'<i class="fas {icon}"></i><span>{name}</span>{check}</span>')

    return (
        "<html><body><h1>Backend Engineer</h1>"
        '<div class="category-box-description"><p>Looking to advance your Development career with '
        "relocation support? Explore our Development Jobs with Relocation Packages.</p></div>"
        '<div class="category-box-description"><p>Explore our comprehensive directory of visa '
        "sponsorship jobs from employers worldwide who are ready to sponsor.</p></div>"
        '<h3 class="content-card-title">Job Description</h3>'
        '<div class="content-single description-excerpt">'
        "Acme builds payment software in Doha with Node.js and React.</div>"
        '<div class="source-readmore"><a class="source-readmore-btn"\n'
        '   href="https://sa.linkedin.com/jobs/view/backend-engineer-at-acme-4476406369" target="_blank">'
        "Continue on LinkedIn</a></div>"
        '<div class="benefits-section">'
        + badge(visa, "fa-passport", "Visa Sponsorship")
        + badge(relocation, "fa-plane-departure", "Relocation")
        + badge("inactive", "fa-house-laptop", "Remote")
        + "</div>"
        '<div class="job-details-full ">'
        '<div class="detail-full-item"><span class="detail-label"><i></i>Job Type</span>'
        '<span class="detail-value">Full-time</span></div>'
        '<div class="detail-full-item"><span class="detail-label"><i></i>Experience Level</span>'
        '<span class="detail-value">Mid-Senior</span></div></div>'
        # another job, further down
        '<div class="job-details-full premium-hidden">'
        '<span class="benefit-tag active" itemprop="jobBenefits"><i></i><span>Relocation</span></span>'
        '<div class="detail-full-item"><span class="detail-label">Job Type</span>'
        '<span class="detail-value">Part-time</span></div></div>'
        "</body></html>"
    )


def linkedin_page():
    return (
        '<html><body><div class="show-more-less-html__markup">'
        "<p>Full LinkedIn description: we build payments with Node.js, React and PostgreSQL.</p>"
        "<ul><li>2+ years of experience</li><li>Visa and relocation provided</li></ul>"
        "</div></body></html>"
    )


class Response:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


def fake_get(pages):
    """pages: {url-part: html or Response}; unknown URLs give 404."""
    calls = []

    def get(url, params=None, **kwargs):
        calls.append((url, params))
        if params is None:
            key = url
        elif "countries" in params:
            key = f"{url}?{params['countries']}&page={params['page']}"
        else:
            key = f"{url}?page={params.get('page')}"

        for part, page in pages.items():
            if key.endswith(part):
                return page if isinstance(page, Response) else Response(page)

        return Response("", status=404)

    get.calls = calls
    return get


class TestJobLinks(unittest.TestCase):

    def test_relative_and_absolute_links_once_each_in_order(self):
        page = list_page(
            "/jobs/284930-backend-engineer-ii-remote",
            "https://jaabz.com/jobs/274705-senior-software-engineer",
            "/jobs/284930-backend-engineer-ii-remote",
        )

        self.assertEqual(
            job_links(page),
            [("284930", "backend-engineer-ii-remote"), ("274705", "senior-software-engineer")],
        )

    def test_category_links_are_not_jobs(self):
        self.assertEqual(job_links("<a href='/jobs/programming/visasponsorship'>x</a>"), [])


class TestParseJobPage(unittest.TestCase):

    def test_job_posting(self):
        job = parse_job_page(job_page())

        self.assertTrue(job["structured"])
        self.assertEqual(job["title"], "Backend Engineer")
        self.assertEqual(job["company"], "Torentify")
        self.assertEqual(job["location"], "Amsterdam, NL")
        self.assertEqual(job["date_posted"], "2026-10-14")
        self.assertEqual(job["job_type"], "FULL_TIME")
        self.assertIn("React", job["description"])
        self.assertIn("* Visa sponsorship provided", job["description"])

    def test_posting_inside_a_graph_and_remote(self):
        page = (
            '<script type="application/ld+json">{"@graph": [{"@type": "WebPage"},'
            '{"@type": "JobPosting", "title": "Dev", "jobLocationType": "TELECOMMUTE",'
            '"applicantLocationRequirements": {"@type": "Country", "name": "Germany"}}]}</script>'
        )
        job = parse_job_page(page)

        self.assertEqual(job["title"], "Dev")
        self.assertTrue(job["is_remote"])
        self.assertEqual(job["location"], "Germany")

    def test_no_posting_falls_back_to_title_and_meta_description(self):
        page = (
            '<html><head><meta property="og:description" content="Short &amp; sweet"></head>'
            "<body><h1>Senior <b>Dev</b></h1></body></html>"
        )
        job = parse_job_page(page)

        self.assertFalse(job["structured"])
        self.assertEqual(job["title"], "Senior Dev")
        self.assertEqual(job["description"], "Short & sweet")

    def test_broken_json_is_skipped(self):
        page = '<script type="application/ld+json">{not json</script><h1>Dev</h1>'
        self.assertEqual(parse_job_page(page)["title"], "Dev")


class TestJaabzSource(unittest.TestCase):

    def source(self, pages, countries=(("qatar", "Qatar"),), **kwargs):
        return JaabzSource(list(countries), get=fake_get(pages), sleep=lambda _: None, **kwargs)

    def test_excerpt_badges_and_full_text_from_linkedin(self):
        pages = {
            "jobs?qatar&page=1": list_page("/jobs/1-backend-engineer"),
            "/jobs/1-backend-engineer": real_layout_page(),
            "linkedin.com/jobs/view/4476406369": linkedin_page(),
        }
        source = self.source(pages, max_pages=1)
        jobs = source.fetch()
        job = jobs.iloc[0]

        self.assertIn("Full LinkedIn description", job["description"])
        self.assertIn("Experience Level: Mid-Senior", job["description"])
        self.assertNotIn("Explore our", job["description"])
        self.assertNotIn("Looking to advance", job["description"])
        self.assertEqual(job["job_url_direct"],
                         "https://sa.linkedin.com/jobs/view/backend-engineer-at-acme-4476406369")
        self.assertEqual(job["source_hint"], "visa")
        self.assertEqual(source.stats["full_text"], 1)

    def test_linkedin_refuses_the_excerpt_is_kept(self):
        pages = {
            "jobs?qatar&page=1": list_page("/jobs/1-backend-engineer"),
            "/jobs/1-backend-engineer": real_layout_page(),
            "linkedin.com/jobs/view/4476406369": Response("", status=429),
        }
        source = self.source(pages, max_pages=1)
        job = source.fetch().iloc[0]

        self.assertTrue(job["description"].startswith("Acme builds payment software"))
        self.assertNotIn("Explore our", job["description"])
        self.assertEqual(source.stats["originals_refused"], 1)

    def test_only_active_badges_count(self):
        from sources.jaabz import read_job_page, source_hint_from

        page = real_layout_page(visa="inactive", relocation="active")
        badges = read_job_page(page)["badges"]

        self.assertEqual(badges, {"Visa Sponsorship": False, "Relocation": True, "Remote": False})
        self.assertEqual(source_hint_from(badges), "relocation")
        self.assertIsNone(source_hint_from({"Visa Sponsorship": False, "Relocation": False}))

    def test_other_jobs_on_the_page_are_ignored(self):
        from sources.jaabz import read_job_page

        details = read_job_page(real_layout_page())

        self.assertEqual(details["details"], {"Job Type": "Full-time", "Experience Level": "Mid-Senior"})

    def test_reads_tech_jobs_and_marks_them_visa(self):
        pages = {
            "jobs?qatar&page=1": list_page(
                "/jobs/1-backend-engineer-remote",
                "/jobs/2-enterprise-deployment-manager",   # not a tech title: not opened
            ),
            "jobs?qatar&page=2": list_page(),          # empty: stop
            "/jobs/1-backend-engineer-remote": job_page(),
        }
        source = self.source(pages, max_pages=3)
        jobs = source.fetch()

        self.assertEqual(list(jobs["id"]), ["jz-1"])
        row = jobs.iloc[0]
        self.assertEqual(row["site"], "jaabz")
        self.assertEqual(row["source_hint"], "visa")
        self.assertEqual(row["job_url"], "https://jaabz.com/jobs/1-backend-engineer-remote")
        self.assertEqual(source.stats, {"listed": 2, "tech": 1, "already_saved": 0,
                                        "opened": 1, "structured": 1, "fallbacks": []})

    def test_known_jobs_are_not_downloaded_again(self):
        pages = {
            "jobs?qatar&page=1": list_page("/jobs/1-backend-engineer", "/jobs/2-web-developer"),
            "/jobs/2-web-developer": job_page("Web Developer"),
        }
        get = fake_get(pages)
        source = JaabzSource([("qatar", "Qatar")], max_pages=1, known_ids={"jz-1"},
                             get=get, sleep=lambda _: None)
        jobs = source.fetch()

        self.assertEqual(list(jobs["id"]), ["jz-2"])
        self.assertFalse(any(url.endswith("/jobs/1-backend-engineer") for url, _ in get.calls))

    def test_title_from_the_link_when_the_page_has_none(self):
        pages = {
            "jobs?qatar&page=1": list_page("/jobs/7-full-stack-developer"),
            "/jobs/7-full-stack-developer": "<html><body>no details</body></html>",
        }
        jobs = self.source(pages, max_pages=1).fetch()

        self.assertEqual(jobs.iloc[0]["title"], "Full Stack Developer")
        # The page names no place: the country of the list is used.
        self.assertEqual(jobs.iloc[0]["location"], "Qatar")

    def test_stops_after_several_failed_job_pages(self):
        links = [f"/jobs/{n}-software-engineer" for n in range(1, 8)]
        pages = {"jobs?qatar&page=1": list_page(*links)}   # every job page: 404
        get = fake_get(pages)
        source = JaabzSource([("qatar", "Qatar")], max_pages=1, get=get, sleep=lambda _: None)

        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            jobs = source.fetch()

        self.assertTrue(jobs.empty)
        job_requests = [url for url, params in get.calls if params is None]
        self.assertEqual(len(job_requests), 3)

    def test_unreachable_lists_raise(self):
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(FetchError):
            self.source({}, max_pages=1).fetch()

    def test_reads_each_country_and_remembers_where_jobs_came_from(self):
        pages = {
            "jobs?saudi-arabia&page=1": list_page("/jobs/1-backend-developer"),
            "jobs?saudi-arabia&page=2": list_page("/jobs/1-backend-developer"),   # same again: stop
            "jobs?qatar&page=1": list_page("/jobs/2-web-developer", "/jobs/1-backend-developer"),
            "/jobs/1-backend-developer": "<h1>Backend Developer</h1>",
            "/jobs/2-web-developer": "<h1>Web Developer</h1>",
        }
        get = fake_get(pages)
        jobs = self.source(pages, countries=[("saudi-arabia", "Saudi Arabia"), ("qatar", "Qatar")],
                           max_pages=3).fetch()

        self.assertEqual(dict(zip(jobs["id"], jobs["location"])),
                         {"jz-1": "Saudi Arabia", "jz-2": "Qatar"})

    def test_country_search_down_falls_back_to_the_landing_page(self):
        import contextlib
        import io

        pages = {
            "jobs?qatar&page=1": Response("", status=500),
            "/jobs/in/qatar/visasponsorship": list_page("/jobs/3-web-developer"),
            "/jobs/3-web-developer": "<h1>Web Developer</h1>",
        }
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            source = self.source(pages, max_pages=2)
            jobs = source.fetch()

        self.assertEqual(dict(zip(jobs["id"], jobs["location"])), {"jz-3": "Qatar"})
        self.assertIn("Qatar: landing page only", printed.getvalue())

    def test_all_country_pages_down_falls_back_to_the_programming_list(self):
        import contextlib
        import io

        pages = {
            "jobs?qatar&page=1": Response("", status=500),
            # landing page: not found
            "programming/visasponsorship?page=1": list_page("/jobs/4-backend-developer"),
            "programming/visasponsorship?page=2": list_page(),
            "/jobs/4-backend-developer": job_page("Backend Developer"),
        }
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            jobs = self.source(pages, max_pages=2).fetch()

        self.assertEqual(list(jobs["id"]), ["jz-4"])
        self.assertEqual(jobs.iloc[0]["location"], "Amsterdam, NL")   # from the job page
        self.assertIn("general programming list", printed.getvalue())

    def test_404_after_page_one_is_just_the_end(self):
        import contextlib
        import io

        pages = {
            "jobs?qatar&page=1": list_page("/jobs/5-web-developer"),
            "/jobs/5-web-developer": "<h1>Web Developer</h1>",
        }   # page 2: 404
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            jobs = self.source(pages, max_pages=3).fetch()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(printed.getvalue(), "")

    def test_list_address_uses_the_country_filter(self):
        from sources.jaabz import list_params

        self.assertEqual(
            list_params("saudi-arabia", 2),
            {"countries": "saudi-arabia", "visa_sponsorship": 1, "search_submitted": 1, "page": 2},
        )


class TestSourcesCheckJaabz(unittest.TestCase):

    def test_reports_when_no_links_are_found(self):
        import sources_check

        printed = []
        source = JaabzSource(
            [("qatar", "Qatar")],
            max_pages=1,
            get=fake_get({"jobs?qatar&page=1": "<html>new layout</html>"}),
            sleep=lambda _: None,
        )
        sources_check.check_jaabz(printed.append, source=source)

        self.assertTrue(any("0 jobs listed" in line for line in printed))
        self.assertTrue(any("jaabz dump" in line for line in printed))


if __name__ == "__main__":
    unittest.main()