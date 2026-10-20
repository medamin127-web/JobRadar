"""
JobRadar's web API. Start it with:

    uvicorn api.server:app --reload --port 8000

The dashboard (web/) calls these endpoints:

    GET  /api/overview              totals, last run, countries
    GET  /api/jobs                  the ranked list, filtered (see list_jobs)
    GET  /api/jobs/{id}             one job, every detail
    POST /api/jobs/{id}/status      mark it applied / not interested / closed / open
    POST /api/refresh               rank the database again (after a scrape)
"""

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.explain import codes_text, reason_text
from api.snapshot import BUCKETS, SnapshotHolder, country_label

app = FastAPI(title="JobRadar")

# The dev server of the dashboard (Vite) runs on another port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

holder = SnapshotHolder()


@app.on_event("startup")
def start_ranking():
    # Ranking takes ~20-40 s: start it now, so the page is ready sooner.
    import threading

    threading.Thread(target=holder.get, daemon=True).start()


@app.get("/api/ready")
def ready():
    """Has the ranking been built yet? (The page waits on this.)"""

    return {"ready": holder.snapshot is not None}

# Which jobs a view shows, by your status (database.py STATUSES).
VIEWS = {
    "ranking": {"open"},
    "applied": {"applied"},
    "hidden": {"not_interested", "closed"},
}

SORTS = {
    # The ranking's own order (bucket, then score with country preference).
    "rank": None,
    "score": lambda job: -(job.match_score or 0),
    "newest": lambda job: (job.age_days if job.age_days is not None else 9999),
}


def _short(text, limit=70):
    text = str(text or "")
    return text if len(text) <= limit else text[:limit].rsplit(",", 1)[0] + ", ..."


def summary(job) -> dict:
    """What one row of the list needs."""

    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": _short(job.location),
        "country": job.country,
        "country_name": country_label(job.country),
        "bucket": job.application_bucket,
        "reason": reason_text(job.bucket_reason),
        "score": round(job.match_score or 0),
        "eligibility": job.eligibility_status,
        "seniority": job.seniority,
        "work_mode": job.work_mode,
        "remote_open": job.remote_open,
        "is_new": bool(job.is_new),
        "age_days": job.age_days,
        "site": job.found_on or job.site,
        "job_url": job.job_url,
        "status": job.status or "open",
    }


def _matches(job, *, view, bucket, country, q, new, remote):
    if (job.status or "open") not in VIEWS[view]:
        return False
    if bucket and bucket != "all" and job.application_bucket != bucket:
        return False
    if country and job.country != country:
        return False
    if new and not job.is_new:
        return False
    if remote and not (job.country == "remote" or job.work_mode == "remote"):
        return False
    if q:
        text = f"{job.title or ''} {job.company or ''} {job.location or ''}".lower()
        if not all(word in text for word in q.lower().split()):
            return False
    return True


@app.get("/api/overview")
def overview():
    snapshot = holder.get()
    ranking = [job for job in snapshot.jobs if (job.status or "open") == "open"]

    return {
        "total": len(ranking),
        "new": sum(1 for job in ranking if job.is_new),
        "recommended": sum(1 for job in ranking if job.application_bucket in ("apply_now", "apply_with_research")),
        "applied": sum(1 for job in snapshot.jobs if job.status == "applied"),
        "last_run": snapshot.last_run.isoformat(timespec="minutes") if snapshot.last_run else None,
        "built_at": snapshot.built_at.isoformat(timespec="minutes"),
        "buckets": BUCKETS,
    }


@app.get("/api/jobs")
def list_jobs(
    view: str = "ranking",
    bucket: str = "all",
    country: str | None = None,
    q: str | None = None,
    new: bool = False,
    remote: bool = False,
    sort: str = "rank",
    limit: int = 100,
    offset: int = 0,
):
    if view not in VIEWS:
        raise HTTPException(400, f"view must be one of {', '.join(VIEWS)}")
    if sort not in SORTS:
        raise HTTPException(400, f"sort must be one of {', '.join(SORTS)}")

    snapshot = holder.get()
    filters = dict(view=view, bucket=bucket, country=country, q=q, new=new, remote=remote)

    items = [job for job in snapshot.jobs if _matches(job, **filters)]

    if SORTS[sort]:
        items = sorted(items, key=SORTS[sort])

    # Counts for the tabs and the country list: every other filter applied.
    bucket_counts = {name: 0 for name in BUCKETS}
    country_counts = {}

    for job in snapshot.jobs:
        if _matches(job, **{**filters, "bucket": "all"}) and job.application_bucket in bucket_counts:
            bucket_counts[job.application_bucket] += 1
        if _matches(job, **{**filters, "country": None}):
            country_counts[job.country] = country_counts.get(job.country, 0) + 1

    countries = sorted(
        ({"key": key, "name": country_label(key), "count": count} for key, count in country_counts.items()),
        key=lambda item: (-item["count"], item["name"]),
    )

    return {
        "total": len(items),
        "items": [summary(job) for job in items[offset: offset + max(1, min(limit, 500))]],
        "buckets": bucket_counts,
        "countries": countries,
    }


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str):
    job = holder.get().by_id.get(job_id)

    if job is None:
        raise HTTPException(404, "No job with this id. Refresh the list: it may have been removed.")

    data = asdict(job)
    data["country_name"] = country_label(job.country)
    data["bucket_reason"] = reason_text(job.bucket_reason)

    # Skill names as written in job ads ("React", not "react").
    names = {str(skill).lower(): skill for skill in (job.skills or [])}
    nice = lambda skills: [names.get(str(s).lower(), str(s)) for s in skills or []]
    data["matched_skills"] = nice(job.matched_skills)
    data["missing_skills"] = nice(job.missing_skills)

    # The same signals in plain words.
    data["blockers_text"] = codes_text(job.eligibility_blockers)
    data["warnings_text"] = codes_text(job.eligibility_warnings)
    data["positives_text"] = codes_text(job.eligibility_positives)
    return data


class StatusChange(BaseModel):
    status: str
    note: str | None = None


@app.post("/api/jobs/{job_id}/status")
def change_status(job_id: str, change: StatusChange):
    from database import STATUSES
    from scraper import open_store

    if change.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {', '.join(STATUSES)}")

    job = holder.get().by_id.get(job_id)

    if job is None:
        raise HTTPException(404, "No job with this id.")

    with open_store() as store:
        store.set_status(job_id, change.status, change.note)

    # The snapshot follows without a full rebuild.
    job.status = change.status
    job.status_note = change.note

    return summary(job)


@app.post("/api/refresh")
def refresh():
    holder.refresh()
    return overview()