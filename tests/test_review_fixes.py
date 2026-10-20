"""Fewer jobs in "Decide yourself" (your notes on the first dashboard)."""

import json
import unittest

from models import Job
from services.eligibility_evaluator import ApplicationBucketer
from services.experience_analyzer import ExperienceAnalyzer
from services.matcher import JobMatcher
from sources.jaabz import read_job_page, summary_sections
from sources.jsonld import parse_job_page

LONG_AD = "We build web applications with React and Java Spring Boot for our customers. " * 10


def bucket(**fields):
    defaults = dict(
        id="x", title="Fullstack Java & React Developer", description=LONG_AD,
        target_category="needs_review", eligibility_status="possible",
        match_score=66, match_coverage=70, role_match_score=100, skills_match_score=70,
        eligibility_blockers=[], eligibility_warnings=[], eligibility_positives=[],
    )
    defaults.update(fields)
    job = Job(**defaults)
    ApplicationBucketer.assign(job)
    return job


class TestNoLevelStated(unittest.TestCase):
    """Most ads never say how many years ("strong experience with Java")."""

    def test_good_match_is_worth_a_closer_look(self):
        job = bucket()
        self.assertEqual(job.application_bucket, "apply_with_research")
        self.assertIn("does not say how much experience", job.bucket_reason)

    def test_partial_match_is_a_long_shot(self):
        self.assertEqual(bucket(match_score=55).application_bucket, "long_shot")

    def test_weak_match_is_skipped(self):
        self.assertEqual(bucket(match_score=45).application_bucket, "skip")

    def test_other_kind_of_role_is_skipped_unless_the_skills_fit(self):
        self.assertEqual(bucket(role_match_score=0, skills_match_score=30).application_bucket, "skip")
        self.assertEqual(bucket(role_match_score=0, skills_match_score=75).application_bucket, "long_shot")

    def test_unreadable_ad_still_goes_to_decide_yourself(self):
        job = bucket(description="", match_coverage=30)
        self.assertEqual(job.application_bucket, "review")
        self.assertIn("could not be read", job.bucket_reason)

    def test_long_ad_without_named_skills_is_judged_not_parked(self):
        # Deliveroo-style: 6,900 characters, no technology named.
        job = bucket(match_coverage=30, skills_match_score=None, match_score=62)
        self.assertNotEqual(job.application_bucket, "review")


class TestRoleNames(unittest.TestCase):

    def test_more_titles_are_your_roles(self):
        from candidate_profile import PROFILE

        for title in ("Website Developer", "Web Engineer", "Product Engineer"):
            score = JobMatcher.match_role(Job(id="x", title=title), PROFILE)["score"]
            self.assertGreaterEqual(score, 80, title)


class TestJaabzSummary(unittest.TestCase):

    PAGE = """
    <div class="ai-summary-card"><div class="ai-summary-head"><div class="ai-badge">AI Summary</div>
      <a href="https://chatgpt.com/?q=...">Open in ChatGPT</a></div>
    <div class="ai-summary-text"><p>Build AI infrastructure. Requires 2+ years of production software experience.</p></div>
    <div class="ai-responsibilities"><h6 class="section-title">Key Responsibilities</h6>
      <div class="responsibility-item"><span>Lead full-stack development</span></div></div>
    <div class="category-links-box content-card"><p>Explore our relocation jobs</p></div>
    <div class="ai-benefits"><h6>Benefits &amp; Perks</h6>
      <div class="benefit-item"><span>Visa sponsorship</span></div></div>
    </div>
    <div class="content-single description-excerpt"><p>Short excerpt.</p></div>
    """

    def test_summary_boxes_are_read_without_jaabz_promotion(self):
        text = summary_sections(self.PAGE)

        self.assertIn("Requires 2+ years", text)
        self.assertIn("Lead full-stack development", text)
        self.assertIn("Visa sponsorship", text)
        self.assertNotIn("Explore our relocation jobs", text)
        self.assertNotIn("ChatGPT", text)

    def test_the_years_are_found(self):
        years = ExperienceAnalyzer().extract_years(summary_sections(self.PAGE))
        self.assertEqual(years[0], 2)

    def test_read_job_page_returns_it(self):
        self.assertIn("Requires 2+ years", read_job_page(self.PAGE)["summary"])


class TestStructuredFields(unittest.TestCase):

    def test_level_skills_and_languages_join_the_description(self):
        posting = {
            "@type": "JobPosting", "title": "Full Stack Developer", "description": "<p>Platform work.</p>",
            "experienceRequirements": {"@type": "OccupationalExperienceRequirements", "monthsOfExperience": 60},
            "skills": ["Python", "Java"], "qualifications": "Polish C2, English B2",
        }
        page = f'<script type="application/ld+json">{json.dumps(posting)}</script>'
        text = parse_job_page(page)["description"]

        self.assertIn("5 years of experience", text)
        self.assertIn("Skills: Python, Java", text)
        self.assertIn("Polish C2", text)


if __name__ == "__main__":
    unittest.main()


class TestJustJoinItFacts(unittest.TestCase):
    """Just Join IT shows the level and languages beside the text."""

    PAGE = (
        r'<html>...\"slug\":\"acme-other-job\",\"experienceLevel\":{\"label\":\"junior\"}...'
        r'\"slug\":\"acme-senior-frontend-developer-angular--wroclaw-javascript\",'
        r'\"title\":\"Senior Frontend Developer (Angular)\",\"experienceLevel\":{\"label\":\"senior\",'
        r'\"value\":\"senior\"},'
        r'\"workplaceType\":{\"label\":\"hybrid\",\"value\":\"hybrid\"},\"requiredSkills\":[{\"id\":\"Angular\",'
        r'\"name\":\"Angular\",\"level\":4},{\"id\":\"TypeScript\",\"name\":\"TypeScript\",\"level\":3}],'
        r'\"languages\":[{\"code\":\"pl\",\"level\":\"C1\"},{\"code\":\"en\",\"level\":\"B2\"}]</html>'
    )

    def test_facts_of_the_ad_itself(self):
        from sources.listed_boards import justjoinit_facts

        facts = justjoinit_facts(self.PAGE, "/job-offer/acme-senior-frontend-developer-angular--wroclaw-javascript")

        self.assertEqual(facts["level"], "Senior")
        self.assertIn("Polish (C1)", facts["text"])
        self.assertIn("Required skills: Angular, TypeScript", facts["text"])

    def test_polish_c1_blocks_and_the_level_counts(self):
        from services.eligibility_analyzer import analyze_other_languages

        langs = analyze_other_languages("Language requirements: Polish (C1), English (B2).")
        self.assertEqual(langs["Polish"]["requirement"], "required")
        self.assertEqual(langs["Polish"]["level_value"], 5)

        job = Job(id="x", title="Frontend Developer", description=LONG_AD, job_level="Mid")
        ExperienceAnalyzer().analyze(job)
        self.assertEqual(job.seniority, "Mid")

    def test_title_level_wins_over_the_board(self):
        job = Job(id="x", title="Senior Frontend Developer", description=LONG_AD, job_level="mid")
        ExperienceAnalyzer().analyze(job)
        self.assertEqual(job.seniority, "Senior")


class TestImpossibleYears(unittest.TestCase):

    def test_company_history_is_not_experience(self):
        for text in ("With over 200 years of history in banking, we...",
                     "25 years of experience on the market make us a leader."):
            job = Job(id="x", title="Developer", description=text + " " + LONG_AD)
            ExperienceAnalyzer().analyze(job)
            self.assertIsNone(job.experience_min_years, text)

    def test_real_requirements_still_count(self):
        job = Job(id="x", title="Developer", description="You have 5+ years of experience. " + LONG_AD)
        ExperienceAnalyzer().analyze(job)
        self.assertEqual(job.experience_min_years, 5)



class TestApplyNowNeedsAVisaSignal(unittest.TestCase):
    """Your rule: no "Apply now" when the ad says nothing about a visa."""

    def test_signs_alone_do_not_make_apply_now(self):
        for sign in ("INTERNATIONAL_FRIENDLY", "RELOCATION_SUPPORT", "ON_OFFICIAL_SPONSOR_REGISTER",
                     "EMPLOYER_VISA_IS_THE_NORM_THERE"):
            job = bucket(target_category="good_target", match_score=85, experience_match_score=100,
                         eligibility_positives=[sign])
            self.assertEqual(job.application_bucket, "apply_with_research", sign)


class TestYourLabelsOct20(unittest.TestCase):
    """From your first 84 labels (labels.py)."""

    def test_not_your_field(self):
        from candidate_profile import PROFILE

        for title in ("Robotics Software Engineer", "Forward Deployed Engineer (Full-Stack)",
                      "Founding Full Stack AI Engineer", "Software Engineer - ML Systems & AI Infrastructure",
                      "Senior Full-Stack Engineer (AI Platform Development)",
                      "Senior Software Engineer, C++ Backend Development", "AI Product Engineer (Demo)",
                      "Senior Product Engineer (Voice AI) - Full Lifecycle Ownership"):
            score = JobMatcher.match_role(Job(id="x", title=title), PROFILE)["score"]
            self.assertLess(score, 50, title)

    def test_still_your_field(self):
        from candidate_profile import PROFILE

        for title in ("Full-Stack Software Engineer (AI Focus)", "Full-Stack Developer | Node.js | AI Builder",
                      "Software Engineer - AI & Productivity Solutions",
                      "Senior SAP Full-Stack Developer (SAPUI5/Fiori & CAP)",
                      "Graduate Programme 2027: Applied AI Engineer",
                      "Graduate Programme 2027: Technology Services Specialist (IT Systems Engineer)"):
            score = JobMatcher.match_role(Job(id="x", title=title), PROFILE)["score"]
            self.assertGreaterEqual(score, 50, title)

    def test_visa_wording(self):
        from services.eligibility_analyzer import analyze_visa

        cases = {
            "Visa sponsorship is available for exceptional candidates.": "maybe",
            "Critical Skills sponsorship can be supported.": "maybe",
            "Applicants must be legally authorized to work in Switzerland or be eligible to obtain the "
            "required Swiss work authorization without employer-sponsored visa support.": "no",
            "We offer visa sponsorship and relocation.": "yes",
            "We can sponsor your visa.": "yes",
        }
        for text, expected in cases.items():
            self.assertEqual(analyze_visa(text)["visa_status"], expected, text)

    def test_board_flag_is_a_maybe_and_jaabz_summary_is_not_used_for_visa(self):
        from services.eligibility_analyzer import EligibilityAnalyzer

        flagged = Job(id="jz-1", title="Developer", description=LONG_AD, source_hint="visa")
        EligibilityAnalyzer.analyze(flagged)
        self.assertEqual(flagged.visa_sponsorship_status, "maybe")

        summary = Job(id="jz-2", title="Developer",
                      description=LONG_AD + "\n\nSummary on Jaabz:\nBenefits & Perks\nVisa sponsorship provided")
        EligibilityAnalyzer.analyze(summary)
        self.assertEqual(summary.visa_sponsorship_status, "unknown")