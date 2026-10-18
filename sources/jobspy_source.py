import logging
import re

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

    # 429 = too many requests; 403 = blocked (Bayt's Cloudflare says 403).
    REFUSED = re.compile(r"status code (?:429|403)\b")

    def emit(self, record):
        message = record.getMessage()
        refused = bool(self.REFUSED.search(message))

        if refused and "for job" in message:
            # The search worked but one job page was refused.
            self.description_failures += 1
        elif refused or "(blocked?)" in message:
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
    """
    LinkedIn, Indeed, Bayt, Glassdoor... through JobSpy. Use one source per site,
    so a site that refuses requests can be paused without stopping the others.
    """

    def __init__(self, sites=None):
        self.sites = sites or ["linkedin"]
        self.name = "+".join(self.sites)

        # Filled after every search().
        self.last_search_rate_limited = False
        self.last_description_failures = 0

    def search(
        self,
        search_term: str,
        location: str,
        results_wanted: int,
        hours_old: int,
        country: str = None,
        remote: bool = False,
    ) -> pd.DataFrame:

        watcher = _RateLimitWatcher()
        loggers = _jobspy_loggers()

        for logger in loggers:
            logger.addHandler(watcher)

        extra = {}

        if country:
            # Indeed and Glassdoor need the country name ("germany").
            extra["country_indeed"] = country

        if remote:
            # LinkedIn's "remote" filter (the "remote" country profile).
            extra["is_remote"] = True

        try:
            jobs = scrape_jobs(
                site_name=self.sites,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                # Open every job page for the full description (LinkedIn
                # and Bayt; Indeed always sends it).
                fetch_description=True,
                **extra,
            )
        finally:
            for logger in loggers:
                logger.removeHandler(watcher)

        self.last_search_rate_limited = watcher.search_blocked and jobs.empty
        self.last_description_failures = watcher.description_failures

        # Keep track of what search produced this job
        jobs["search_term"] = search_term

        return jobs