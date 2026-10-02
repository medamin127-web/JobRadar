import re

from models import Job


class JobAnalyzer:
    """
    Extracts structured information from a normalized Job.

    First version:
    - Extract technical skills from title + description.
    - No AI.
    - Uses a controlled vocabulary with aliases.
    """

    SKILL_PATTERNS = {
        # Languages
        "Python": [
            r"\bpython\b",
        ],
        "Java": [
            r"\bjava\b",
        ],
        "JavaScript": [
            r"\bjavascript\b",
            r"\bjs\b",
        ],
        "TypeScript": [
            r"\btypescript\b",
            r"\bts\b",
        ],
        "C#": [
            r"(?<!\w)c#(?!\w)",
            r"\bc\s*sharp\b",
        ],
        "C++": [
            r"(?<!\w)c\+\+(?!\w)",
        ],
        "PHP": [
            r"\bphp\b",
        ],
        "Go": [
            r"\bgolang\b",
        ],
        "Rust": [
            r"\brust\b",
        ],
        "Kotlin": [
            r"\bkotlin\b",
        ],
        "Swift": [
            r"\bswift\b",
        ],

        # Frontend
        "React": [
            r"\breact(?:\.js|js)?\b",
        ],
        "Vue.js": [
            r"\bvue(?:\.js|js)?\b",
        ],
        "Angular": [
            r"\bangular\b",
        ],
        "Next.js": [
            r"\bnext(?:\.js|js)\b",
        ],
        "HTML": [
            r"\bhtml5?\b",
        ],
        "CSS": [
            r"\bcss3?\b",
        ],
        "Tailwind CSS": [
            r"\btailwind(?:\s+css)?\b",
        ],

        # Backend
        "Node.js": [
            r"\bnode(?:\.js|js)\b",
        ],
        "Express.js": [
            r"\bexpress(?:\.js|js)?\b",
        ],
        "NestJS": [
            r"\bnest(?:\.js|js)?\b",
        ],
        "Django": [
            r"\bdjango\b",
        ],
        "Flask": [
            r"\bflask\b",
        ],
        "FastAPI": [
            r"\bfastapi\b",
        ],
        "Laravel": [
            r"\blaravel\b",
        ],
        "Symfony": [
            r"\bsymfony\b",
        ],
        ".NET": [
            r"\.net\b",
            r"\basp\.net\b",
            r"\baspnet\b",
        ],
        "Spring": [
            r"\bspring\b",
            r"\bspring\s+boot\b",
        ],
        "Spring Boot": [
            r"\bspring\s+boot\b",
        ],

        # Databases
        "PostgreSQL": [
            r"\bpostgres(?:ql)?\b",
        ],
        "MySQL": [
            r"\bmysql\b",
        ],
        "MongoDB": [
            r"\bmongodb\b",
            r"\bmongo\s*db\b",
        ],
        "Redis": [
            r"\bredis\b",
        ],
        "SQL": [
            r"\bsql\b",
        ],
        "NoSQL": [
            r"\bnosql\b",
        ],
        "SQL Server": [
            r"\bsql\s+server\b",
            r"\bmicrosoft\s+sql\s+server\b",
        ],

        # DevOps / infrastructure
        "Docker": [
            r"\bdocker\b",
        ],
        "Kubernetes": [
            r"\bkubernetes\b",
            r"\bk8s\b",
        ],
        "AWS": [
            r"\baws\b",
            r"\bamazon\s+web\s+services\b",
        ],
        "Azure": [
            r"\bazure\b",
        ],
        "Google Cloud": [
            r"\bgoogle\s+cloud\b",
            r"\bgcp\b",
        ],
        "Jenkins": [
            r"\bjenkins\b",
        ],
        "Git": [
            r"\bgit\b",
        ],
        "GitHub": [
            r"\bgithub\b",
        ],
        "GitLab": [
            r"\bgitlab\b",
        ],
        "CI/CD": [
            r"\bci\s*/\s*cd\b",
            r"\bci-cd\b",
            r"\bcicd\b",
        ],

        # Testing
        "Selenium": [
            r"\bselenium\b",
        ],
        "Cypress": [
            r"\bcypress\b",
        ],
        "Playwright": [
            r"\bplaywright\b",
        ],
        "Jest": [
            r"\bjest\b",
        ],

        # Architecture / APIs
        "REST API": [
            r"\brest(?:ful)?\s+api(?:s)?\b",
            r"\brestful\b",
        ],
        "GraphQL": [
            r"\bgraphql\b",
        ],
        "Microservices": [
            r"\bmicroservices?\b",
        ],
    }

    def analyze(self, job: Job) -> Job:
        """
        Enrich a Job with extracted technical skills.
        """

        text = self._build_search_text(job)

        extracted_skills = self.extract_skills(text)

        job.skills = extracted_skills

        return job

    def extract_skills(self, text: str) -> list[str]:
        """
        Extract known technical skills from text.

        Returns canonical skill names in a stable order.
        """

        if not text:
            return []

        text = text.lower()

        found = []

        for skill, patterns in self.SKILL_PATTERNS.items():

            for pattern in patterns:

                if re.search(pattern, text, flags=re.IGNORECASE):
                    found.append(skill)
                    break

        return found

    @staticmethod
    def _build_search_text(job: Job) -> str:
        """
        Combine the most useful textual fields.

        We include the title because sometimes a technology
        appears only in the job title.
        """

        parts = [
            job.title,
            job.description,
        ]

        return "\n".join(
            part
            for part in parts
            if part
        )