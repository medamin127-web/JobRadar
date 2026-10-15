"""
Check job sources from your computer before adding them to config.py.

    python sources_check.py                    Arbeitnow + the boards in config.py
    python sources_check.py greenhouse n26 celonis
    python sources_check.py lever somecompany
    python sources_check.py guesses            try a starter list of companies

For each source it prints how many jobs it has and how many JobRadar
would keep (tech roles in your countries), plus the line to add to
config.py. Wrong names simply show "not found".

Where to find the names: open the company's careers page and look at a
job link. job-boards.greenhouse.io/<token>/jobs/123 -> Greenhouse token;
jobs.lever.co/<name>/... -> Lever name.
"""

import sys

from config import ARBEITNOW_PAGES, GREENHOUSE_BOARDS, LEVER_COMPANIES, SEARCH_CONFIGS
from sources import ArbeitnowSource, GreenhouseSource, LeverSource
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