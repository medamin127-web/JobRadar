# JobRadar

Personal international job search engine. It scrapes tech jobs from LinkedIn
(Germany for now), scores them against my profile, and checks whether I can
realistically take them from Tunisia (visa, relocation, language, remote scope).

## Setup (Windows PowerShell, Python 3.12)

```powershell
cd path\to\JobsRadar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`

### Your profile

`candidate_profile.py` holds your personal details and is **git-ignored**.
On a fresh copy, create it from the template and edit it:

```powershell
copy candidate_profile.example.py candidate_profile.py
```

Things to check in it: skills, languages (the German level decides which
German-language jobs are blocked) and `work_history` dates (`YYYY-MM`; a job
with no `end_date` is your current one). Experience years are **computed from
the work history**, internships excluded.

### Version control

```powershell
git init
git add .
git status        # candidate_profile.py, data/ and reports/ must NOT be listed
git commit -m "JobRadar phase 0"
```

## Run

```powershell
# 1. Run the tests (should end with OK)
python -m unittest discover -s tests -t .

# 2. Scrape, score and rank jobs
python scraper.py

# 3. Re-score an existing CSV without scraping again
#    (use after editing candidate_profile.py or the analyzers)
python rescore_csv.py
```

## Where things are saved (all git-ignored)

| Path | What |
| --- | --- |
| `data/output/jobs.csv` | ranked jobs. First columns: `application_bucket`, `eligibility_status`, `match_score`, `bucket_reason`, blockers and warnings. If the file is open in Excel, a timestamped copy is written next to it |
| `data/raw/jobs_raw_*.csv` | raw scrape of each run. Also the cache used to recover descriptions LinkedIn refused to serve (HTTP 429). **Keep this folder** |
| `reports/run_*.txt` | full console report of each run (UTF-8) |
| `data/output/jobs_rescored.csv` | output of `rescore_csv.py` |

Open a CSV in Excel via Data > From Text/CSV (UTF-8) if characters look wrong.

## Application buckets

| Bucket | Meaning |
| --- | --- |
| `apply_now` | Good technical fit, positive eligibility signals, seniority or experience known |
| `apply_with_research` | Promising, but verify visa, language or seniority in the listing first |
| `long_shot` | Stretch role or unlikely eligibility |
| `review` | Too little information; read the listing |
| `skip` | Blocked (e.g. German level too high, no sponsorship) or technical gap |

## Project layout

```
scraper.py              entry point: python scraper.py  (main() only, no side effects on import)
config.py               searches, sites, folders  <- edit this to change what is searched
pipeline.py             collect -> dedupe -> normalize -> analyze -> score -> sort
storage.py              raw copies, description cache, CSV saving
reporting.py            everything that is printed + the UTF-8 report file
rescore_csv.py          re-run eligibility on an existing CSV
candidate_profile.py    YOUR profile (git-ignored)
candidate_profile.example.py   template for the file above
models/                 Job, Profile, WorkExperience, Language, CEFR helpers
services/               analyzers (skills, experience, eligibility), matchers, scorer, classifier
sources/                job sources (JobSpy / LinkedIn); new sources implement sources/base.py
tests/                  unit tests (they never use your real profile)
```
