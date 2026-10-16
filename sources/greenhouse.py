"""
Company career pages hosted on Greenhouse.

A company's board token is the name in its Greenhouse URL, e.g.
job-boards.greenhouse.io/<token>. Check tokens with: python sources_check.py

    https://boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true
"""

import pandas as pd

from .http import get_json
from .text import html_to_text

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


class GreenhouseSource:

    def __init__(self, board, get=None):
        self.board = board
        self.name = f"greenhouse:{board}"
        self.get = get

    def fetch(self) -> pd.DataFrame:
        payload = get_json(API.format(board=self.board), params={"content": "true"}, get=self.get)

        return pd.DataFrame([self._row(job) for job in payload.get("jobs") or []])

    def _row(self, job) -> dict:
        location = (job.get("location") or {}).get("name")
        posted = job.get("first_published") or job.get("updated_at") or ""

        return {
            "id": f"gh-{self.board}-{job.get('id')}",
            "site": "greenhouse",
            "job_url": job.get("absolute_url"),
            "title": job.get("title"),
            "company": job.get("company_name") or self.board,
            "location": location,
            "date_posted": posted[:10] or None,
            "is_remote": "remote" in str(location or "").lower(),
            "description": html_to_text(job.get("content")),
            "search_term": self.name,
        }