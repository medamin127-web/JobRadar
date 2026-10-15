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

# 2. Scrape LinkedIn, then score and rank
python scraper.py

# 3. No scraping: re-analyze everything saved in data/raw
#    (after editing candidate_profile.py or the code, or while LinkedIn
#    is refusing requests)
python scraper.py --offline
python scraper.py --raw data\raw\jobs_raw_20261014_011247.csv   # one file only
```

### LinkedIn rate limits (HTTP 429)

LinkedIn refuses requests when you scrape too often. JobRadar now pauses
between searches, retries a refused search once, and stops cleanly after
repeated refusals (settings in `config.py`). If a run says "Stopped early",
wait a few hours and use `--offline` in the meantime. Refused job
descriptions are recovered from earlier runs when possible.

### Measuring accuracy (labels)

```powershell
python labels.py export     # writes data\labels\labels.csv
#   open it in Excel, fill the true_... columns, save as CSV
python labels.py evaluate   # accuracy per field + every disagreement
```

Re-running `export` keeps your answers. Instructions are at the top of
`labels.py`.

## Where things are saved (all git-ignored)

| Path | What |
| --- | --- |
| `data/output/jobs.csv` | ranked jobs. First columns: `application_bucket`, `eligibility_status`, `match_score`, `bucket_reason`, blockers and warnings. If the file is open in Excel, a timestamped copy is written next to it |
| `data/raw/jobs_raw_*.csv` | raw scrape of each run. Used by `--offline`, by `labels.py` and to recover refused descriptions. **Keep this folder** |
| `data/labels/labels.csv` | your hand labels |
| `reports/run_*.txt` | full console report of each run (UTF-8) |

Open a CSV in Excel via Data > From Text/CSV (UTF-8) if characters look wrong.

## Application buckets

| Bucket | Meaning |
| --- | --- |
| `apply_now` | Good technical fit, positive eligibility signals, seniority or experience known |
| `apply_with_research` | Promising, but verify visa, language or seniority in the listing first |
| `long_shot` | Stretch role or unlikely eligibility |
| `review` | Too little information; read the listing |
| `skip` | Blocked (e.g. German level too high, no sponsorship), technical gap, or weak technical match (score < 40) |

Only an explicit visa statement makes a job `likely` eligible. Relocation help
alone is not visa help. Inside a bucket, jobs that state visa support come first.

## Project layout

```
scraper.py              entry point: python scraper.py [--offline | --raw FILE]
config.py               searches, sites, folders  <- edit this to change what is searched
pipeline.py             collect -> dedupe -> normalize -> analyze -> score -> sort
storage.py              raw copies, description cache, CSV saving
reporting.py            everything that is printed + the UTF-8 report file
labels.py               hand labels: export / evaluate accuracy
candidate_profile.py    YOUR profile (git-ignored)
candidate_profile.example.py   template for the file above
models/                 Job, Profile, WorkExperience, Language, CEFR helpers
services/               analyzers (skills, experience, eligibility), matchers, scorer, classifier
sources/                job sources (JobSpy / LinkedIn); new sources implement sources/base.py
tests/                  unit tests (they never use your real profile)
```