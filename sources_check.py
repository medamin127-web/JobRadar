"""
Check job sources from your computer before adding them to config.py.

    python sources_check.py                    Arbeitnow + the boards in config.py
    python sources_check.py greenhouse n26 celonis
    python sources_check.py lever somecompany
    python sources_check.py guesses            try a starter list of companies
    python sources_check.py jaabz              read Jaabz (visa jobs) for your countries
    python sources_check.py relocateme         read Relocate.me (relocation jobs)
    python sources_check.py stepstone          read StepStone (Germany), one search
    python sources_check.py remote             read the remote boards (REMOTE_BOARDS)
    python sources_check.py remote himalayas   ... only these boards
    python sources_check.py jaabz dump         ... and save its HTML in data/samples
                                               (same for: relocateme dump)

For each source it prints how many jobs it has and how many JobRadar
would keep (tech roles in your countries), plus the line to add to
config.py. Wrong names simply show "not found".

Where to find the names: open the company's careers page and look at a
job link. job-boards.greenhouse.io/<token>/jobs/123 -> Greenhouse token;
jobs.lever.co/<name>/... -> Lever name.
"""

import sys

from config import (
    ARBEITNOW_PAGES,
    GREENHOUSE_BOARDS,
    HIMALAYAS_TERMS,
    LEVER_COMPANIES,
    REMOTE_BOARDS,
    SEARCH_CONFIGS,
    YOUR_COUNTRY,
)
from sources import (
    StepStoneSource,
    ArbeitnowSource,
    GreenhouseSource,
    JaabzSource,
    LeverSource,
    RelocateMeSource,
)
from sources.relevance import in_country, is_tech_title

# Guesses only: tech companies with offices in Germany. Most may be wrong
# or use other systems; the check tells you which ones work.
GUESSES = {
    "greenhouse": [
        "n26", "getyourguide", "hellofresh", "celonis", "contentful", "sumup",
        "babbel", "traderepublic", "raisin", "personio", "taxfix", "gorillas",
        "commercetools", "scalablecapital", "solarisbank", "omio", "blinkist",
    ],
    "lever": ["pitch", "taxfix", "mobilede", "adjust", "kraken"],
}

KEYWORDS = [word for config in SEARCH_CONFIGS for word in config.get("location_keywords", [])]


def check(source, output=print, local=True):
    try:
        jobs = source.fetch()
    except Exception as error:
        output(f"  {source.name:32} not found / unreachable ({error})")
        return None

    if jobs.empty:
        output(f"  {source.name:32} works, but 0 open jobs right now")
        return 0

    keep = jobs["title"].map(is_tech_title)

    if local:
        keep &= jobs["location"].map(lambda loc: in_country(loc, KEYWORDS))

    kept = jobs[keep]
    output(f"  {source.name:32} {len(jobs):4} jobs, {len(kept):3} kept")

    for title in kept["title"].head(3):
        output(f"  {'':32}   e.g. {title}")

    return len(kept)


def jaabz_countries():
    return [(c["jaabz"], c["name"]) for c in SEARCH_CONFIGS if c.get("jaabz")]


def check_board(name, source, output=print, dump=False):
    """Read a job board without an API (Jaabz, Relocate.me); say what worked."""

    if dump:
        save_samples(name, source, output)

    try:
        jobs = source.fetch()
    except Exception as error:
        output(f"  {name}: unreachable ({error})")
        return None

    stats = source.stats
    output(
        f"  {name}: {stats.get('listed', 0)} jobs listed, {stats.get('tech', 0)} tech, "
        f"{stats.get('opened', 0)} opened, {stats.get('structured', 0)} with full details"
    )

    if name == "jaabz" and stats.get("opened"):
        output(
            f"  full text from the original posting (LinkedIn...): {stats.get('full_text', 0)}, "
            f"refused: {stats.get('originals_refused', 0)} (those keep Jaabz's short excerpt)"
        )

    if stats.get("listed", 0) == 0:
        output(f"  No job links found: the page layout changed. Run: python sources_check.py {name} dump")
        output("  and send me the files in data/samples.")
    elif stats.get("opened") and not stats.get("structured") and name == "jaabz":
        output("  Job pages have no JobPosting data: only titles and short texts.")
        output(f"  Run: python sources_check.py {name} dump  and send me the files in data/samples.")

    if jobs.empty:
        return 0

    kept = jobs["location"].map(lambda loc: in_country(loc, KEYWORDS))
    output(f"  {int(kept.sum())} of them in your countries")

    print_verdicts(jobs, output)

    return len(jobs)


def print_verdicts(jobs, output=print, profile=None):
    """
    What JobRadar would do with each job (the same analysis as scraper.py):
    a source lists everything with a tech title; the ranking decides.
    """

    import contextlib
    import io

    from pipeline import assign_countries, process_jobs

    if profile is None:
        from scraper import load_profile

        profile = load_profile()

    with contextlib.redirect_stdout(io.StringIO()):
        analyzed = process_jobs(assign_countries(jobs, SEARCH_CONFIGS), profile)

    output("  What JobRadar would do with them (your countries first):")

    analyzed.sort(key=lambda job: job.country is None)

    for job in analyzed:
        where = job.location or "?"
        output(
            f"    {job.application_bucket:19} {job.match_score or 0:5.1f}  "
            f"{str(job.title)[:55]:55} | {str(where)[:22]:22} | "
            f"{str(job.bucket_reason or '')[:70]}"
        )

    good = sum(job.application_bucket in ("apply_now", "apply_with_research") for job in analyzed)
    output(f"  -> {good} recommended, the rest skipped or for review")


def check_jaabz(output=print, dump=False, source=None):
    source = source or JaabzSource(jaabz_countries(), max_pages=1)
    return check_board("jaabz", source, output, dump)


def check_relocateme(output=print, dump=False, source=None):
    source = source or RelocateMeSource(max_pages=2)
    return check_board("relocateme", source, output, dump)


def check_stepstone(output=print, dump=False, source=None):
    from sources.http import browser_get

    if source is None:
        config = next((c for c in SEARCH_CONFIGS if c.get("stepstone")), None)

        if config is None:
            output("  No country in config.py has a StepStone site.")
            return None

        source = StepStoneSource(
            domain=config["stepstone"], terms=["Full Stack Developer"],
            country_key=config["key"], country_name=config["name"], max_pages=1,
        )
        output("  (looking like Chrome with curl_cffi)" if browser_get()
               else "  (plain requests; if refused, try: pip install curl_cffi)")

    result = check_board("stepstone", source, output, dump)

    if result is None and not dump:
        output("  Refused? Try:  pip install curl_cffi   then run this again.")
        output("  Still refused: run  python sources_check.py stepstone dump  and send me the file.")

    return result


def check_remote(names=None, output=print, sources=None):
    """Read each remote board; say what worked and what JobRadar would do."""

    from sources import remote_board_sources

    sources = sources or remote_board_sources(names or REMOTE_BOARDS, HIMALAYAS_TERMS, YOUR_COUNTRY)
    working = []

    for source in sources:
        output(f"\n{source.name}:")

        try:
            jobs = source.fetch()
        except Exception as error:
            output(f"  unreachable ({error})")
            continue

        stats = source.stats
        output(f"  {stats.get('listed', 0)} jobs read, {stats.get('tech', 0)} with a tech title")

        if jobs.empty:
            output("  works, but nothing to show right now")
            working.append(source.name)
            continue

        working.append(source.name)
        tech = jobs[jobs["title"].map(is_tech_title)]

        if not tech.empty:
            print_verdicts(tech, output)

    if working:
        output(f"\nWorking boards. In config.py:  REMOTE_BOARDS = {working!r}")

    return working


def save_samples(name, source, output=print):
    """Save a list page and one job page, to fix the parser if the site changes."""

    import os

    if name == "jaabz":
        from sources.jaabz import BASE, LIST_URL, job_links, list_params

        slug = (source.countries or [("germany", "Germany")])[0][0]
        params = list_params(slug, 1)
        job_url = lambda link: f"{BASE}/jobs/{link[0]}-{link[1]}"
    elif name == "stepstone":
        from sources.stepstone import job_links

        LIST_URL = source.search_url(source.terms[0] if source.terms else "software developer")
        params = None
        job_url = lambda link: f"{source.base}/stellenangebote--{link[1]}--{link[0]}-inline.html"
    else:
        from sources.relocateme import BASE, LIST_URL, job_links

        params = None
        job_url = lambda link: BASE + link["path"]

    os.makedirs("data/samples", exist_ok=True)

    try:
        page = source._page(LIST_URL, params)
    except Exception as error:
        output(f"  {name}: unreachable ({error})")
        return

    with open(f"data/samples/{name}_list.html", "w", encoding="utf-8") as handle:
        handle.write(page)

    links = job_links(page)

    if links:
        with open(f"data/samples/{name}_job.html", "w", encoding="utf-8") as handle:
            handle.write(source._page(job_url(links[0])))

    output(f"  Saved data/samples/{name}_list.html" + (f" and {name}_job.html" if links else ""))


def main(argv=None, output=print):
    argv = sys.argv[1:] if argv is None else argv
    working = {"greenhouse": [], "lever": []}

    def run(kind, names):
        for name in names:
            source = GreenhouseSource(name) if kind == "greenhouse" else LeverSource(name)

            if check(source, output) is not None:
                working[kind].append(name)

    if not argv:
        output("Arbeitnow:")
        check(ArbeitnowSource(max_pages=min(ARBEITNOW_PAGES or 1, 2)), output, local=False)
        output("Your Greenhouse boards:" if GREENHOUSE_BOARDS else "No Greenhouse boards in config.py yet.")
        run("greenhouse", GREENHOUSE_BOARDS)
        output("Your Lever companies:" if LEVER_COMPANIES else "No Lever companies in config.py yet.")
        run("lever", LEVER_COMPANIES)
    elif argv[0] == "guesses":
        for kind, names in GUESSES.items():
            output(f"{kind} guesses:")
            run(kind, names)
    elif argv[0] == "jaabz":
        check_jaabz(output, dump="dump" in argv[1:])
        return
    elif argv[0] == "stepstone":
        check_stepstone(output, dump="dump" in argv[1:])
        return
    elif argv[0] == "relocateme":
        check_relocateme(output, dump="dump" in argv[1:])
        return
    elif argv[0] == "remote":
        check_remote(argv[1:] or None, output)
        return
    elif argv[0] in ("greenhouse", "lever") and len(argv) > 1:
        run(argv[0], argv[1:])
    else:
        output(__doc__)
        return

    for kind, setting in (("greenhouse", "GREENHOUSE_BOARDS"), ("lever", "LEVER_COMPANIES")):
        if working[kind]:
            output(f"\nWorking {kind} names. In config.py:  {setting} = {working[kind]!r}")


if __name__ == "__main__":
    main()