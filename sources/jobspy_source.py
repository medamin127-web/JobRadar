import logging

import pandas as pd
from jobspy import scrape_jobs

from .base import JobSource


class _RateLimitWatcher(logging.Handler):
    """
    Listens to JobSpy's own loggers while one search runs.

    JobSpy does not raise an error when LinkedIn refuses a request: it logs
    it and returns fewer (or zero) jobs. This handler turns those log lines
    into numbers the pipeline can act on.
    """

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.search_blocked = False
        self.description_failures = 0

    def emit(self, record):
        message = record.getMessage()

        if "status code 429" in message and "for job" in message:
            # The search worked but one job page was refused.
            self.description_failures += 1
        elif "status code 429" in message or "(blocked?)" in message:
            # The search page itself was refused.
            self.search_blocked = True


def _jobspy_loggers():
    # JobSpy creates one logger per site ("JobSpy:LinkedIn", ...) and
    # disables propagation, so the handler must be attached to each.
    return [
        logging.getLogger(name)
        for name in list(logging.root.manager.loggerDict)
        if name.startswith("JobSpy")
    ]


class JobSpySource(JobSource):

    def __init__(self, sites=None):
        self.sites = sites or ["linkedin"]

        # Filled after every search().
        self.last_search_rate_limited = False
        self.last_description_failures = 0

    def search(
        self,
        search_term: str,
        location: str,
        results_wanted: int,
        hours_old: int,
    ) -> pd.DataFrame:

        watcher = _RateLimitWatcher()
        loggers = _jobspy_loggers()

        for logger in loggers:
            logger.addHandler(watcher)

        try:
            jobs = scrape_jobs(
                site_name=self.sites,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                linkedin_fetch_description=True,
            )
        finally:
            for logger in loggers:
                logger.removeHandler(watcher)

        self.last_search_rate_limited = watcher.search_blocked and jobs.empty
        self.last_description_failures = watcher.description_failures

        # Keep track of what search produced this job
        jobs["search_term"] = search_term

        return jobs