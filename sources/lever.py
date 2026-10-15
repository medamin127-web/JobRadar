"""
Company career pages hosted on Lever.

A company's Lever name is in its URL: jobs.lever.co/<company>
(or jobs.eu.lever.co/<company> for EU-hosted companies).
Check names with: python sources_check.py

    https://api.lever.co/v0/postings/<company>?mode=json
"""

from datetime import datetime, timezone

import pandas as pd

from .http import get_json
from .text import html_to_text

API = {
    "global": "https://api.lever.co/v0/postings/{company}",
    "eu": "https://api.eu.lever.co/v0/postings/{company}",
}


class LeverSource:

    def __init__(self, company, region="global", get=None):
        self.company = company
        self.region = region
        self.name = f"lever:{company}"
        self.get = get

    def fetch(self) -> pd.DataFrame:
        payload = get_json(API[self.region].format(company=self.company),
                           params={"mode": "json"}, get=self.get)

        postings = payload if isinstance(payload, list) else []
        return pd.DataFrame([self._row(posting) for posting in postings])

    def _row(self, posting) -> dict:
        categories = posting.get("categories") or {}
        created = posting.get("createdAt")
        date_posted = (
            datetime.fromtimestamp(created / 1000, tz=timezone.utc).date().isoformat()
            if isinstance(created, (int, float)) else None
        )

        parts = [
            posting.get("descriptionPlain"),
            posting.get("openingPlain"),
            posting.get("descriptionBodyPlain"),
        ]

        for item in posting.get("lists") or []:
            parts.append(f"{item.get('text', '')}\n{html_to_text(item.get('content'))}")

        parts.append(posting.get("additionalPlain"))

        location = categories.get("location") or ", ".join(categories.get("allLocations") or [])

        return {
            "id": f"lv-{self.company}-{posting.get('id')}",
            "site": "lever",
            "job_url": posting.get("hostedUrl") or posting.get("applyUrl"),
            "title": (posting.get("text") or "").strip(),
            "company": self.company,
            "location": location,
            "date_posted": date_posted,
            "is_remote": str(posting.get("workplaceType", "")).lower() == "remote",
            "job_type": categories.get("commitment"),
            "description": "\n\n".join(p.strip() for p in parts if p and p.strip()),
            "search_term": self.name,
        }