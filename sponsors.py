"""
Official registers of employers allowed to sponsor work visas.

    uk  Home Office "Register of licensed sponsors: workers" (CSV, daily).
        A UK employer NOT on it cannot sponsor a Skilled Worker visa.
    nl  IND "Public register Work" (recognised sponsors, monthly). Highly
        skilled migrant permits go through recognised sponsors.

JobRadar downloads them to data/registers/ (a few MB) and refreshes them
when they are older than REFRESH_DAYS. A job in the UK or the Netherlands
is then marked "on the register" or "not on the register" by its company
name: much stronger evidence than the ad's wording.

    python sponsors.py update           download both registers now
    python sponsors.py check Picnic     is this company on a register?
"""

import csv
import io
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta

REGISTERS_DIR = os.path.join("data", "registers")
REFRESH_DAYS = 14

UK_CONTENT_API = "https://www.gov.uk/api/content/government/publications/register-of-licensed-sponsors-workers"
NL_REGISTER_PAGE = "https://ind.nl/en/public-register-recognised-sponsors/public-register-work"

REGISTER_NAMES = {
    "uk": "UK register of licensed sponsors",
    "nl": "IND register of recognised sponsors",
}


# ==================================================
# COMPANY NAMES
# ==================================================

# Legal forms and filler that differ between an ad and a register.
_LEGAL = re.compile(
    r"\b(?:ltd|limited|plc|llp|lp|llc|inc|incorporated|corp|corporation|co|company"
    r"|b\s?v|n\s?v|v\s?o\s?f|c\s?v|gmbh|ag|se|sa|sas|srl|bvba|holding|holdings"
    r"|group|uk|nl|europe|international|the|t/a|trading as)\b",
    re.IGNORECASE,
)


def _brackets(match) -> str:
    # "(UK)", "(Barneveld)": a note, dropped. "(PORTABLE APPLIANCE SAFETY
    # SERVICES)": part of the name, kept.
    inside = match.group(1)
    return " " if len(inside.split()) <= 2 else f" {inside} "


def normalize_company(name) -> str:
    """'Picnic Technologies B.V.' -> 'picnic technologies'"""

    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ")
    text = re.sub(r"\((.*?)\)", _brackets, text)
    text = text.replace(".", "")                  # "b.v." -> "bv", "booking.com" -> "bookingcom"
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = _LEGAL.sub(" ", text)

    return re.sub(r"\s+", " ", text).strip()


class SponsorRegister:

    def __init__(self, key, names, updated=None):
        self.key = key
        self.title = REGISTER_NAMES.get(key, key)
        self.updated = updated
        self.by_name = {}

        for name in names:
            normal = normalize_company(name)

            if normal:
                self.by_name.setdefault(normal, name)

        self.sorted_names = sorted(self.by_name)

    def __len__(self):
        return len(self.by_name)

    def find(self, company):
        """
        The register's name for this company, or None.

        Exact match after normalizing ("Booking.com" = "BOOKING.COM LIMITED"),
        or the register name = the company's name + only generic company
        words: "Picnic" = "Picnic Technologies B.V.", "Adyen" = "ADYEN N.V.
        LONDON BRANCH". Never "Picnic" = "Picnic Kebab House": with 120,000+
        UK employers, a shared first word means nothing.
        """

        normal = normalize_company(company)

        if not normal:
            return None

        if normal in self.by_name:
            return self.by_name[normal]

        if len(normal.replace(" ", "")) < 4:
            return None

        prefix = normal + " "

        from bisect import bisect_left

        index = bisect_left(self.sorted_names, prefix)
        found = []

        while index < len(self.sorted_names) and self.sorted_names[index].startswith(prefix):
            rest = self.sorted_names[index][len(prefix):].split()

            if rest and all(word in GENERIC_COMPANY_WORDS for word in rest):
                found.append(self.sorted_names[index])

            index += 1

        # Several different companies fit: do not guess.
        return self.by_name[found[0]] if len(found) == 1 else (
            self.by_name[min(found, key=len)] if found else None
        )


# Words a company adds to its brand in its legal name. Anything else
# ("kebab", "school", "accountants", "restaurant") means another company.
GENERIC_COMPANY_WORDS = {
    # Only words that add nothing to WHO the company is. Industry words
    # ("media", "health", "capital", "studios", "consulting") are left out:
    # "Picnic Media" is not Picnic, "Maximus Consulting" is not Maximus.
    "technologies", "technology", "tech", "software", "systems", "solutions",
    "digital", "labs", "lab", "services", "service", "bank", "banking",
    "payments", "global", "worldwide", "eu", "emea", "london", "amsterdam",
    "dublin", "branch", "office", "netherlands", "nederland", "ireland",
    "england", "britain", "british", "operations", "platforms", "platform",
    "online", "europa", "benelux", "and",
}


# ==================================================
# PARSING THE DOWNLOADS
# ==================================================

def parse_uk_csv(text: str) -> list:
    """Organisations with a Skilled Worker route (the work visa you need)."""

    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    names = []

    for row in reader:
        route = (row.get("Route") or "").lower()
        name = (row.get("Organisation Name") or "").strip()

        if name and ("skilled worker" in route or not route):
            names.append(name)

    return names


_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def parse_nl_html(page: str) -> list:
    """Rows of the IND table: organisation | KvK number (8 digits)."""

    import html

    names = []

    for row in _ROW.findall(page or ""):
        cells = [html.unescape(_TAG.sub("", cell)).strip() for cell in _CELL.findall(row)]

        if len(cells) >= 2 and re.fullmatch(r"\d{8}", cells[1].replace(" ", "")):
            names.append(cells[0].strip('" '))

    return names


# ==================================================
# DOWNLOAD / CACHE
# ==================================================

def _path(key):
    return os.path.join(REGISTERS_DIR, f"{key}.json")


def download(key, get=None) -> list:
    from sources.http import get_html, get_json

    if key == "uk":
        meta = get_json(UK_CONTENT_API, get=get)
        attachments = (meta.get("details") or {}).get("attachments") or []
        url = next((a.get("url") for a in attachments if str(a.get("url", "")).endswith(".csv")), None)

        if not url:
            raise RuntimeError("no CSV in the GOV.UK register page")

        return parse_uk_csv(get_html(url, get=get))

    if key == "nl":
        return parse_nl_html(get_html(NL_REGISTER_PAGE, get=get))

    raise ValueError(f"unknown register {key!r}")


def update(key, get=None, output=print) -> int:
    names = download(key, get=get)

    if len(names) < 100:
        raise RuntimeError(f"{REGISTER_NAMES[key]}: only {len(names)} names read; the page layout may have changed")

    os.makedirs(REGISTERS_DIR, exist_ok=True)

    with open(_path(key), "w", encoding="utf-8") as handle:
        json.dump({"updated": datetime.now().isoformat(timespec="seconds"), "names": names}, handle)

    output(f"  {REGISTER_NAMES[key]}: {len(names)} employers saved")
    return len(names)


def load(key, refresh_days=REFRESH_DAYS, auto_update=True, output=print):
    """The register (refreshed when old), or None when it cannot be had."""

    path = _path(key)
    data = None

    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)

    stale = data is None or (
        datetime.now() - datetime.fromisoformat(data["updated"]) > timedelta(days=refresh_days)
    )

    if stale and auto_update:
        try:
            update(key, output=output)
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as error:
            output(f"  {REGISTER_NAMES[key]}: could not download ({error})"
                   + ("; using the saved copy" if data else ""))

    if data is None:
        return None

    return SponsorRegister(key, data["names"], data.get("updated"))


def load_for(configs, auto_update=True, output=print) -> dict:
    """{register key: SponsorRegister} for the countries you search."""

    keys = {config.get("sponsor_register") for config in configs} - {None}
    registers = {}

    for key in sorted(keys):
        register = load(key, auto_update=auto_update, output=output)

        if register is not None:
            registers[key] = register

    return registers


def main(argv=None, output=print):
    argv = sys.argv[1:] if argv is None else argv

    if argv[:1] == ["update"]:
        for key in REGISTER_NAMES:
            try:
                update(key, output=output)
            except Exception as error:
                output(f"  {REGISTER_NAMES[key]}: failed ({error})")
    elif argv[:1] == ["check"] and len(argv) > 1:
        company = " ".join(argv[1:])

        for key in REGISTER_NAMES:
            register = load(key, output=output)

            if register is None:
                output(f"  {REGISTER_NAMES[key]}: not available")
                continue

            found = register.find(company)
            output(f"  {register.title}: " + (f"YES, as '{found}'" if found else "no"))
    else:
        output(__doc__)


if __name__ == "__main__":
    main()