import pandas as pd

from models import Job


class JobNormalizer:
    """
    Converts raw jobs from external sources into
    JobRadar's internal Job model.
    """

    JOB_COLUMNS = [
        "id",
        "site",
        "title",
        "company",
        "location",
        "job_url",
        "job_url_direct",
        "date_posted",
        "job_type",
        "is_remote",
        "work_from_home_type",
        "job_level",
        "job_function",
        "salary_source",
        "interval",
        "min_amount",
        "max_amount",
        "currency",
        "description",
        "skills",
        "experience_range",
        "company_industry",
        "company_url",
        "company_description",
        "search_term",
    ]

    def normalize_dataframe(
        self,
        jobs: pd.DataFrame,
    ) -> list[Job]:
        """
        Convert a raw DataFrame into a list of
        normalized Job objects.
        """

        if jobs.empty:
            return []

        jobs = jobs.copy()

        # Make sure all expected fields exist.
        for column in self.JOB_COLUMNS:

            if column not in jobs.columns:
                jobs[column] = None

        # Keep only fields understood by JobRadar.
        jobs = jobs[self.JOB_COLUMNS]

        normalized_jobs = []

        for _, row in jobs.iterrows():

            job = self.normalize_row(row)

            normalized_jobs.append(job)

        return normalized_jobs

    def normalize_row(
        self,
        row: pd.Series,
    ) -> Job:
        """
        Convert one raw job row into a Job object.
        """

        return Job(
            id=self.clean_value(row["id"]),
            site=self.clean_value(row["site"]),

            title=self.clean_text(row["title"]),
            company=self.clean_text(row["company"]),
            location=self.clean_text(row["location"]),

            job_url=self.clean_text(row["job_url"]),
            job_url_direct=self.clean_text(
                row["job_url_direct"]
            ),

            date_posted=self.clean_value(
                row["date_posted"]
            ),

            job_type=self.clean_text(
                row["job_type"]
            ),

            is_remote=self.clean_boolean(
                row["is_remote"]
            ),

            work_from_home_type=self.clean_text(
                row["work_from_home_type"]
            ),

            job_level=self.clean_text(
                row["job_level"]
            ),

            job_function=self.clean_text(
                row["job_function"]
            ),

            salary_source=self.clean_text(
                row["salary_source"]
            ),

            interval=self.clean_text(
                row["interval"]
            ),

            min_amount=self.clean_number(
                row["min_amount"]
            ),

            max_amount=self.clean_number(
                row["max_amount"]
            ),

            currency=self.clean_text(
                row["currency"]
            ),

            description=self.clean_text(
                row["description"]
            ),

            skills=self.clean_skills(
              row["skills"]
            ),

            experience_range=self.clean_text(
                row["experience_range"]
            ),

            company_industry=self.clean_text(
                row["company_industry"]
            ),

            company_url=self.clean_text(
                row["company_url"]
            ),

            company_description=self.clean_text(
                row["company_description"]
            ),

            search_term=self.clean_text(
                row["search_term"]
            ),
        )
        
    @staticmethod
    def clean_skills(value):
        """
        Normalize a source-provided skills value into a list.

        JobSpy may provide:
        - NaN
        - a string
        - a list
        """

        if pd.isna(value):
            return None

        if isinstance(value, list):
            return [
                str(skill).strip()
                for skill in value
                if str(skill).strip()
            ]

        value = str(value).strip()

        if not value:
            return None

        return [
            skill.strip()
            for skill in value.split(",")
            if skill.strip()
        ]

    # ==================================================
    # CLEANING HELPERS
    # ==================================================

    @staticmethod
    def clean_value(value):

        if pd.isna(value):
            return None

        return value

    @staticmethod
    def clean_text(value):

        if pd.isna(value):
            return None

        value = str(value).strip()

        if not value:
            return None

        return value

    @staticmethod
    def clean_boolean(value):

        if pd.isna(value):
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, str):

            value = value.strip().lower()

            if value in {"true", "yes", "1"}:
                return True

            if value in {"false", "no", "0"}:
                return False

        return value

    @staticmethod
    def clean_number(value):

        if pd.isna(value):
            return None

        try:
            return float(value)

        except (TypeError, ValueError):
            return None