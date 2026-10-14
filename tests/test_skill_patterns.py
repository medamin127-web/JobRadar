import unittest

from services import JobAnalyzer


class TestSkillPatterns(unittest.TestCase):

    def skills(self, text):
        return JobAnalyzer().extract_skills(text)

    def test_spring_the_season_is_not_a_skill(self):
        self.assertNotIn("Spring", self.skills("Our spring launch is coming."))

    def test_spring_boot_is_spring(self):
        self.assertIn("Spring", self.skills("Experience with Spring Boot"))

    def test_java_and_spring(self):
        self.assertIn("Spring", self.skills("Java, Spring and Hibernate"))

    def test_express_the_word_is_not_a_skill(self):
        self.assertNotIn("Express.js", self.skills("Please express your interest."))

    def test_node_express(self):
        self.assertIn("Express.js", self.skills("Node.js with Express"))

    def test_nest_the_word_is_not_a_skill(self):
        self.assertNotIn("NestJS", self.skills("A great place to build your nest egg."))

    def test_nestjs(self):
        self.assertIn("NestJS", self.skills("TypeScript and NestJS"))

    def test_swift_the_adjective_is_not_a_skill(self):
        self.assertNotIn("Swift", self.skills("We value swift decisions."))

    def test_swift_for_ios(self):
        self.assertIn("Swift", self.skills("iOS apps written in Swift"))

    def test_go_in_a_stack_list(self):
        self.assertIn("Go", self.skills("Python, Go and Kubernetes"))
        self.assertIn("Go", self.skills("Cloud & Go"))

    def test_go_the_verb_is_not_a_skill(self):
        self.assertNotIn("Go", self.skills("We go the extra mile."))


class TestTextCleaning(unittest.TestCase):

    def test_soft_hyphen_is_removed(self):
        from services import JobNormalizer
        self.assertEqual(
            JobNormalizer.clean_text("Senior Software En\u00adgineer"),
            "Senior Software Engineer",
        )


if __name__ == "__main__":
    unittest.main()
