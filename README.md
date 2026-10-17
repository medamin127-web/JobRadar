# JobRadar

Personal international job search engine. It collects tech jobs from several
sources (LinkedIn, Indeed, Bayt, Arbeitnow, Jaabz, company career pages) in
several countries (Germany and the Gulf for now), scores them against my profile, and checks whether I can realistically take
them from Tunisia (visa, relocation, language, remote scope).

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

# 2. Scrape, save to the database, then score and rank
python scraper.py                        # the countries whose turn it is
python scraper.py --countries uae,qatar  # these countries this time
python scraper.py --all-countries        # every country (many searches!)

# 3. No scraping: rank what is already in the database
#    (after editing candidate_profile.py or the code, or while LinkedIn
#    is refusing requests)
python scraper.py --offline
python scraper.py --raw data\raw\jobs_raw_20261014_011247.csv   # one raw file only

# 4. Your applications
python track.py                         # what to look at now + your applications
python track.py applied 4477572741 "sent CV 15/10"
python track.py no 4460378155           # not interested: hide it
python track.py closed 4460378155       # posting closed: hide it
python track.py open 4460378155         # undo
```

Every run ranks all saved jobs posted in the last 30 days (`MAX_JOB_AGE_DAYS`
in `config.py`) that you have not marked. Jobs found for the first time are
marked **NEW**. The id to use with `track.py` is shown at the end of each
ranking line (`id 4477572741`); the last 6 digits are enough.

### Countries

`COUNTRIES` in `config.py` lists the countries to search. Each one has a
profile in `countries.py`: the search location, the search terms, which
sites make sense there (Bayt is Gulf only), the city names used to place
feed jobs, the local language, and how visas usually work there:

- **explicit** (Germany, Netherlands, Ireland, UK): an ad that says nothing
  about visas is not counted as visa support.
- **employer_sponsored** (UAE, Saudi Arabia, Qatar, Kuwait, Oman, Bahrain):
  the employer normally arranges the work visa, so a silent ad is a cautious
  "possible". Ads for nationals only (UAE nationals, Emiratisation,
  Saudization roles) or for people already in the country (transferable
  iqama, own residence visa, "currently residing in the UAE") are blocked.

**Countries take turns.** LinkedIn refuses requests when one run makes too
many searches, so each run searches `COUNTRIES_PER_RUN` countries (the most
overdue ones) and says which ones come next. `COUNTRY_PRIORITY` makes the
countries you prefer (Saudi Arabia, Qatar) come back about twice as often,
and their jobs rank a little higher (+5 points) inside the same bucket. The ranking always
shows every country, with a "Jobs per country" summary.

**Official sponsor registers (UK, Netherlands).** In these two countries
only registered employers can sponsor a work permit (UK Skilled Worker,
Dutch highly skilled migrant). `sponsors.py` downloads the official lists
to `data/registers/` every 2 weeks; a job there shows "on the register"
(a good sign) or "not on the register" (probably cannot sponsor you):

```powershell
python sponsors.py update          # download both registers now
python sponsors.py check Picnic    # is this company on a register?
```

Languages: German keeps its detailed check. Other languages (Arabic, Dutch,
French, Swedish...) are read as required (with a level) / a plus / not
required and compared with the languages in your profile: "Arabic required"
is a plus for you, "fluent Dutch required" blocks.

### The database

`data/jobradar.db` (SQLite, built into Python, nothing to install) remembers
every job ever scraped, when it was first and last seen, the best
description found and your status for it. On the first run it imports the
old files in `data/raw`. To start over, delete the file.

### Sources

Set in `config.py`:

| Source | Setting | How it works |
| --- | --- | --- |
| LinkedIn, Indeed, Bayt, Glassdoor | `SITES` | JobSpy runs every search term on each site, in the countries whose profile lists that site (Bayt: Gulf only; Glassdoor: not in the Gulf) |
| StepStone (Germany's biggest board) | `STEPSTONE_PAGES` | searches StepStone in the countries whose profile has a `stepstone` site, opens each new tech job once. Bot-protected: check with `python sources_check.py stepstone`; if refused, `pip install curl_cffi` |
| Arbeitnow (German job board, free API) | `ARBEITNOW_PAGES` | reads the newest pages, keeps tech jobs |
| Jaabz (jobs with visa sponsorship) | `JAABZ_PAGES` | reads its visa-sponsorship list for each of your countries, opens each new tech job once; the jobs count as "maybe visa" unless the ad says otherwise |
| Relocate.me (jobs with a relocation package) | `RELOCATEME_PAGES` | reads its list pages, opens each new tech job once; "maybe visa" when the package includes visa services, else "relocation" |
| Company career pages on Greenhouse | `GREENHOUSE_BOARDS` | all of the company's jobs; keeps tech jobs in your countries |
| Company career pages on Lever | `LEVER_COMPANIES` | same |

The same job found on several sites is shown once ("Found on: indeed,
linkedin"), keeping the longest description.

Check a source from your computer before adding it:

```powershell
python sources_check.py                       # Arbeitnow + your configured boards
python sources_check.py greenhouse n26 celonis
python sources_check.py guesses               # try a starter list of companies
python sources_check.py jaabz                 # read Jaabz for your countries
python sources_check.py relocateme            # read Relocate.me
python sources_check.py stepstone             # one StepStone search (bot protection test)
python sources_check.py jaabz dump            # ... and save its HTML in data/samples
```

It prints how many jobs each source has, how many JobRadar would keep, and
the line to paste into `config.py`.

### Rate limits (HTTP 429 / 403)

LinkedIn, Indeed and Bayt refuse requests when you scrape too often. JobRadar
pauses between searches, retries a refused search once, and stops a site
cleanly after repeated refusals while the other sites continue (settings in
`config.py`). If a run says "Stopped early",
wait a few hours and use `--offline` in the meantime. Refused job
descriptions are recovered from earlier runs when possible.

### Measuring accuracy (labels)

```powershell
python labels.py label      # one job at a time, 4 questions, one key each
python labels.py evaluate   # where JobRadar disagrees with you (re-analyzes first)
python labels.py review     # go through each disagreement: who is right?
```

`label` shows a job and asks: would you apply? is it your field? what does it
say about visa? about German? Enter accepts JobRadar's guess in [brackets],
`d` shows the whole description, `o` opens the job in your browser, `s` skips,
`q` stops (answers are saved after every job). About 20 jobs is enough.

## Where things are saved (all git-ignored)

| Path | What |
| --- | --- |
| `data/output/jobs.csv` | ranked jobs. First columns: `application_bucket`, `eligibility_status`, `match_score`, `bucket_reason`, blockers and warnings. If the file is open in Excel, a timestamped copy is written next to it |
| `data/jobradar.db` | the database: every job + your status. **Keep this file** |
| `data/raw/jobs_raw_*.csv` | backup copy of each raw scrape (the database is the main store) |
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
scraper.py              entry point: python scraper.py [--offline | --raw FILE | --countries ...]
config.py               countries, sites, folders  <- edit this to change what is searched
countries.py            one profile per country: searches, sites, cities, visa rules
sponsors.py             official sponsor registers (UK, NL): download + company lookup
pipeline.py             collect -> dedupe -> normalize -> analyze -> score -> sort
database.py             SQLite memory: jobs, first/last seen, your status
track.py                mark jobs applied / not interested / closed
storage.py              raw backup copies, CSV saving
reporting.py            everything that is printed + the UTF-8 report file
labels.py               your answers: label / evaluate accuracy
candidate_profile.py    YOUR profile (git-ignored)
candidate_profile.example.py   template for the file above
models/                 Job, Profile, WorkExperience, Language, CEFR helpers
services/               analyzers (skills, experience, eligibility), matchers, scorer, classifier
sources/                job sources: jobspy_source (LinkedIn, Indeed, Bayt, Glassdoor), arbeitnow,
                        jaabz, relocateme, stepstone,
                        greenhouse, lever; jsonld reads job pages (schema.org JobPosting)
sources_check.py        test a source / company board from your computer
tests/                  unit tests (they never use your real profile)
```