"""
Adzuna (adzuna.com): a job search engine with a free official API. One
key covers the UK, Germany, Austria, Switzerland, the Netherlands, Poland
and Canada (the "adzuna" code in countries.py).

    https://api.adzuna.com/v1/api/jobs/gb/search/1?app_id=...&app_key=...&what=react developer

Get a free key at https://developer.adzuna.com (sign up, "Create a new
application"), then set it once in PowerShell:

    setx ADZUNA_APP_ID "aa6ff08e"
    setx ADZUNA_APP_KEY "92066ddd1ca22fa823bab06c61702070"

and open a new terminal. Without a key JobRadar simply skips Adzuna.

Free keys allow 250 calls a day: JobRadar makes one call per search term
in each country searched this run (about 10 a run).

Adzuna gives only the first ~500 characters of each description, so its
jobs often end in "review" (too little text to judge): open the link.
"""

import os

import pandas as pd

from .http import FetchError, get_json
from .text import html_to_text

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def adzuna_keys():
    """(app_id, app_key) from the environment, or (None, None)."""

    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()

    return (app_id, app_key) if app_id and app_key else (None, None)


class AdzunaSource:
    """One country (a profile with an "adzuna" code), one call per term."""

    def __init__(self, config, app_id, app_key, terms=None, max_days_old=7, results=50, get=None, sleep=None):
        self.config = config
        self.country = config["adzuna"]
        self.name = f"adzuna:{self.country}"
        self.app_id = app_id
        self.app_key = app_key
        self.terms = terms or config.get("adzuna_terms") or config["search_terms"][:3]
        self.max_days_old = max_days_old
        self.results = results
        self.get = get
        self.sleep = sleep
        self.stats = {}

    def fetch(self) -> pd.DataFrame:
        rows = {}
        calls = 0

        for term in self.terms:
            params = {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "what": term,
                "results_per_page": self.results,
                "max_days_old": self.max_days_old,
                "sort_by": "date",
                "content-type": "application/json",
            }
            kwargs = {"get": self.get}

            if self.sleep:
                kwargs["sleep"] = self.sleep

            try:
                payload = get_json(API.format(country=self.country, page=1), params=params, **kwargs)
            except FetchError as error:
                # A wrong key answers 401: say it once and stop.
                print(f"  {self.name}: {error}")
                if "401" in str(error) or "403" in str(error):
                    print("  Adzuna refused the key: check ADZUNA_APP_ID / ADZUNA_APP_KEY.")
                    break
                continue

            calls += 1

            for job in payload.get("results") or []:
                row = self._row(job, term)

                if row["job_url"]:
                    rows.setdefault(row["id"], row)

        self.stats = {"calls": calls, "listed": len(rows)}

        return pd.DataFrame(list(rows.values()))

    def _row(self, job, term) -> dict:
        location = (job.get("location") or {}).get("display_name") or self.config["name"]
        name = self.config["name"]

        if name.lower() not in location.lower():
            location = f"{location}, {name}"

        created = str(job.get("created") or "")[:10] or None

        return {
            "id": f"az-{job.get('id')}",
            "site": "adzuna",
            "job_url": job.get("redirect_url"),
            "title": html_to_text(job.get("title")) or None,
            "company": (job.get("company") or {}).get("display_name"),
            "location": location,
            "date_posted": created,
            "is_remote": False,
            "job_type": job.get("contract_time"),
            "description": html_to_text(job.get("description")),
            "search_term": term,
            # A country search: the job belongs to that country.
            "search_country": self.config["key"],
        }


def adzuna_sources(configs, terms_per_country=3):
    """One source per country searched this run that Adzuna covers (needs a key)."""

    app_id, app_key = adzuna_keys()
    covered = [config for config in configs if config.get("adzuna")]

    if not covered:
        return []

    if not app_id:
        print("  Adzuna: no key set (ADZUNA_APP_ID / ADZUNA_APP_KEY), skipped. See sources/adzuna.py.")
        return []

    return [
        AdzunaSource(config, app_id, app_key, terms=config["search_terms"][:terms_per_country])
        for config in covered
    ]