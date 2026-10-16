"""
Arbeitnow (arbeitnow.com): a Germany-focused job board with a free public
API. It returns all its jobs page by page (not a search), so JobRadar
keeps the tech titles.

    https://www.arbeitnow.com/api/job-board-api?page=2
"""

from datetime import datetime, timezone

import pandas as pd

from .http import FetchError, get_json
from .relevance import is_tech_title
from .text import html_to_text

API = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource:

    name = "arbeitnow"

    def __init__(self, max_pages=5, get=None, sleep=None):
        self.max_pages = max_pages
        self.get = get
        self.sleep = sleep

    def fetch(self) -> pd.DataFrame:
        rows = []
        seen = set()

        for page in range(1, self.max_pages + 1):
            kwargs = {"get": self.get}

            if self.sleep:
                kwargs["sleep"] = self.sleep

            try:
                payload = get_json(API, params={"page": page}, **kwargs)
            except FetchError as error:
                if page == 1:
                    raise
                print(f"  arbeitnow: stopped at page {page}: {error}")
                break

            jobs = payload.get("data") or []
            fresh = [job for job in jobs if job.get("slug") not in seen]

            if not fresh:
                break

            for job in fresh:
                seen.add(job.get("slug"))

                if is_tech_title(job.get("title")):
                    rows.append(self._row(job))

        return pd.DataFrame(rows)

    @staticmethod
    def _row(job) -> dict:
        created = job.get("created_at")
        date_posted = (
            datetime.fromtimestamp(created, tz=timezone.utc).date().isoformat()
            if isinstance(created, (int, float)) else None
        )
        tags = ", ".join(job.get("tags") or [])

        return {
            "id": f"an-{job.get('slug')}",
            "site": "arbeitnow",
            "job_url": job.get("url"),
            "title": job.get("title"),
            "company": job.get("company_name"),
            "location": job.get("location"),
            "date_posted": date_posted,
            "is_remote": bool(job.get("remote")),
            "job_type": ", ".join(job.get("job_types") or []) or None,
            "description": html_to_text(job.get("description")) + (f"\n\nTags: {tags}" if tags else ""),
            "search_term": "arbeitnow",
        }