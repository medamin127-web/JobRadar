from jobspy import scrape_jobs
import pandas as pd

from .base import JobSource


class JobSpySource(JobSource):

    def __init__(self, sites=None):
        self.sites = sites or ["linkedin"]

    def search(
        self,
        search_term: str,
        location: str,
        results_wanted: int,
        hours_old: int,
    ) -> pd.DataFrame:

        jobs = scrape_jobs(
            site_name=self.sites,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            linkedin_fetch_description=True,
        )

        # Keep track of what search produced this job
        jobs["search_term"] = search_term

        return jobs