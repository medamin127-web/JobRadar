"""
Extract eligibility signals (visa, work authorization, relocation,
language, remote scope) from a job listing.

This module only READS the job. It knows nothing about the candidate.
Deciding what the signals mean for you happens in
eligibility_evaluator.py.

Everything here is rule-based (regex). Silence is reported as
"unknown", never as "yes": most listings say nothing about visas.
"""

import re
from typing import Optional

from models import Job
from models.cefr import CEFR_VALUES, level_label


# ==================================================
# TEXT HELPERS
# ==================================================

SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?;])\s+|[\r\n]+|[•·▪●■►]|\s[-–—]\s"
)


ABBREVIATIONS = re.compile(
    r"\b(?:mind|ca|bzw|ggf|inkl|evtl|usw|vgl|max|min)\.(?=\s)",
    re.IGNORECASE,
)

INITIALISMS = re.compile(r"\b([zdu])\.\s?([bha])\.", re.IGNORECASE)


def split_sentences(text: str) -> list[str]:
    # "mind. C1", "z.B." and similar must not end a sentence.
    text = ABBREVIATIONS.sub(lambda m: m.group(0)[:-1], text or "")
    text = INITIALISMS.sub(r"\1\2", text)

    parts = SENTENCE_SPLIT.split(text)
    return [p.strip(" \t*#_|") for p in parts if p and p.strip(" \t*#_|")]


def snippet(sentence: str, limit: int = 180) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip()

    if len(sentence) <= limit:
        return sentence

    return sentence[: limit - 1].rstrip() + "…"


def first_match(patterns, text: str):
    for pattern in patterns:
        match = pattern.search(text)

        if match:
            return match

    return None


def compile_all(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# ==================================================
# JOB DESCRIPTION LANGUAGE (German vs English)
# ==================================================

# Words that are (almost) exclusive to one language.
DE_WORDS = {
    "und", "der", "die", "das", "wir", "sie", "mit", "für", "ein", "eine",
    "von", "bei", "oder", "ist", "du", "dich", "deine", "dein", "unser",
    "unsere", "auf", "zu", "im", "den", "dem", "auch", "nicht", "werden",
    "sind", "als", "aus", "nach", "uns", "bist", "hast", "mehr", "über",
    "wenn", "zum", "zur", "deiner", "ihre", "ihr", "bieten", "bringst",
}

EN_WORDS = {
    "and", "the", "you", "we", "with", "for", "our", "of", "to", "is",
    "are", "will", "your", "on", "as", "about", "be", "have", "or",
    "that", "this", "from", "at", "by", "who", "what", "us", "their",
    "experience", "work", "working", "looking", "join",
}


def detect_language(text: Optional[str]) -> Optional[str]:
    """
    Return "de", "en", "mixed" or None (too little text).
    """

    if not text:
        return None

    tokens = re.findall(r"[a-zäöüß]+", text.lower())

    if len(tokens) < 40:
        return None

    de = sum(1 for t in tokens if t in DE_WORDS)
    en = sum(1 for t in tokens if t in EN_WORDS)

    if de + en < 10:
        return None

    if de > en * 1.5:
        return "de"

    if en > de * 1.5:
        return "en"

    return "mixed"


# ==================================================
# GERMAN LANGUAGE REQUIREMENT
# ==================================================

# "German law", "German company", "German clients" describe the country,
# not the language, so they are not counted as a language mention.
_GERMAN_NOT_LANGUAGE = (
    r"(?!\s+(?:law|laws|legislation|regulations?|citizen\w*|nationals?"
    r"|nationality|authorit\w+|government|federal|tax|labou?r|market"
    r"|compan\w+|start-?ups?|security|engineering|mittelstand"
    r"|entit(?:y|ies)|offices?|subsidiar\w+|branch\w*))"
)

GERMAN_TERM = re.compile(
    r"\bgerman\b" + _GERMAN_NOT_LANGUAGE +
    r"|\bdeutsch(?:e|en|er|es|em)?\b|deutschkenntnisse"
    r"|deutschsprach\w*|sprachkenntnisse in deutsch",
    re.IGNORECASE,
)

# Checked only in a small window around the German term, so a
# "German AI company" in the intro does not look like a requirement.
REQUIREMENT_CUES = re.compile(
    r"skill|kenntnis|speak|fluen|proficien|level|niveau|fließend|flüssig"
    r"|verhandlungssicher|sprachkenntnis|native|muttersprach|required"
    r"|erforderlich|vorausgesetzt|must|need|should|sollten|mindestens|\bmind\b"
    r"|at least|\b[abc][12]\b|good|\bgut|excellent|ausgezeichnet|sehr gut"
    r"|knowledge|command|beherrsch|sprichst|sprechen|fluent|mandatory",
    re.IGNORECASE,
)

NOT_REQUIRED_CUES = re.compile(
    r"no german|ohne deutsch|keine deutschkenntnisse|kein deutsch"
    r"|german (?:is )?not (?:required|needed|necessary|mandatory)"
    r"|deutsch(?:kenntnisse)? (?:sind |ist )?nicht (?:erforderlich|notwendig|nötig|zwingend)"
    r"|english is sufficient|englisch genügt|no need (?:for|to speak) german"
    r"|(?:isn'?t|is not|not|aren'?t|are not) (?:strictly )?(?:required|needed|mandatory|necessary)"
    r"|language courses?|sprachkurs\w*|deutschkurs\w*|german courses?",
    re.IGNORECASE,
)

OPTIONAL_CUES = re.compile(
    r"\bplus\b|nice[- ]to[- ]have|advantage|beneficial|bonus|desirable"
    r"|preferred|wünschenswert|von vorteil|vorteilhaft|idealerweise"
    r"|ideally|willingness to learn|bereitschaft|zu lernen|to learn"
    r"|english or german|german or english|englisch oder\W+(?:und\W+)?deutsch"
    r"|deutsch oder\W+(?:und\W+)?englisch",
    re.IGNORECASE,
)

# Level keywords -> CEFR value, strongest first.
LEVEL_KEYWORDS = [
    (re.compile(r"native|muttersprach|mother tongue", re.I), 6),
    (
        re.compile(
            r"fluen\w*|fließend\w*|fliessend\w*|verhandlungssicher\w*|business[- ]fluent|bilingual"
            r"|excellent|exzellent|ausgezeichnet\w*|perfekt|proficien\w*"
            r"|advanced|fortgeschritten\w*"
            r"|sehr hohe[nm]?\s+niveau|hohe[nm]?\s+niveau|\bc[- ]niveau|high level",
            re.I,
        ),
        5,
    ),
    (
        re.compile(
            r"sehr gute?[rsn]?|very good|strong|\bgood\b|\bgute[rsn]?\b|\bsolid\b"
            r"|conversational|intermediate|working knowledge|gesprächssicher",
            re.I,
        ),
        4,
    ),
    (
        re.compile(
            r"\bbasic\b|grundkenntnis\w*|grundlegend\w*|elementary|\bbasics\b",
            re.I,
        ),
        2,
    ),
]

CEFR_TOKEN = re.compile(r"\b([ABC][12])\b")


SHARED_FILLER = {
    "and", "und", "or", "oder", "both", "beide", "sowie", "auf", "in",
    "at", "skills", "kenntnisse", "kenntnissen", "level", "niveau",
    "sprachkenntnisse", "language", "sprache", "sprachen", "der", "die", "of",
    "mind", "mindestens", "min", "minimum", "least",
}

OTHER_LANGUAGE = re.compile(
    r"english|englisch|french|französisch|arabic|arabisch|spanish|spanisch",
    re.IGNORECASE,
)


def _nearest_level(
    window: str, anchor_start: int, anchor_end: int, other=None
) -> Optional[int]:
    """
    Find the level that belongs to the German term.

    - An explicit CEFR level (C1) beats a keyword ("fluent").
    - A level separated from German by another language name
      ("German and fluent English") is ignored.
    - Overlapping keywords ("sehr gute" vs "gute") keep the longest.
    """

    other = other or OTHER_LANGUAGE

    def usable(start: int, end: int) -> bool:
        if end <= anchor_start:
            between = window[end:anchor_start]
        else:
            between = window[anchor_end:start]

        if not other.search(between):
            return True

        # "Fluent English and German" / "German and English at C1":
        # the level is shared when only languages and filler words sit
        # between the level and the German term.
        leftover = other.sub(" ", between)
        words = re.findall(r"[a-zäöüß]+", leftover.lower())

        return all(word in SHARED_FILLER for word in words)

    def distance(start: int, end: int) -> int:
        if end <= anchor_start:
            return anchor_start - end

        return max(0, start - anchor_end)

    cefr = [
        (distance(m.start(), m.end()), CEFR_VALUES[m.group(1)])
        for m in CEFR_TOKEN.finditer(window)
        if usable(m.start(), m.end())
    ]

    if cefr:
        cefr.sort(key=lambda item: item[0])
        return cefr[0][1]

    spans = []

    for pattern, value in LEVEL_KEYWORDS:
        for m in pattern.finditer(window):
            spans.append((m.start(), m.end(), value))

    # Drop spans fully contained in a longer span.
    spans = [
        s for s in spans
        if not any(
            o is not s and o[0] <= s[0] and o[1] >= s[1]
            and (o[1] - o[0]) > (s[1] - s[0])
            for o in spans
        )
    ]

    spans = [s for s in spans if usable(s[0], s[1])]

    if not spans:
        return None

    spans.sort(key=lambda s: distance(s[0], s[1]))
    return spans[0][2]


def _window(sentence: str, match: re.Match, size: int = 70):
    start = max(0, match.start() - size)
    end = min(len(sentence), match.end() + size)
    chunk = sentence[start:end]

    # Do not start or end in the middle of a word.
    if start > 0 and " " in chunk:
        cut = chunk.index(" ") + 1
        chunk = chunk[cut:]
        start += cut

    if end < len(sentence) and " " in chunk:
        chunk = chunk[: chunk.rindex(" ")]

    return chunk, start


# Hints that only make German optional when no level is attached to it.
WEAK_OPTIONAL = re.compile(r"willingness to learn|bereitschaft|zu lernen|to learn", re.IGNORECASE)

_CLAUSE_BREAK = re.compile(r"[,;()\[\]]|\bsowie\b|\bas well as\b", re.IGNORECASE)


def _clause(sentence: str, match: re.Match) -> str:
    """The part of the sentence around the match, between commas, brackets,
    semicolons, 'sowie' or 'as well as'."""

    start, end = 0, len(sentence)

    for brk in _CLAUSE_BREAK.finditer(sentence):
        if brk.end() <= match.start():
            start = brk.end()
        elif brk.start() >= match.end():
            end = brk.start()
            break

    return sentence[start:end]


def analyze_german_requirement(text: str, language: Optional[str]) -> dict:
    """
    Returns:
        requirement: none_mentioned | not_required | optional |
                     required | implied
        level_value: 1-6 or None
        evidence: matching sentence or None
    """

    best = None  # (level_value or 0, sentence)
    optional_hit = None
    not_required_hit = None

    for sentence in split_sentences(text):
        german = GERMAN_TERM.search(sentence)

        if not german:
            continue

        window, offset = _window(sentence, german)

        if NOT_REQUIRED_CUES.search(window):
            not_required_hit = not_required_hit or window
            continue

        # Optional words count only in the same clause as the German term:
        #   "Excellent English skills, German is a plus"          -> optional
        #   "verhandlungssicheres Englisch und idealerweise Deutsch" -> optional
        #   "Sehr gute Deutsch- und Englischkenntnisse sowie
        #    idealerweise Erfahrung ..."  ("ideally" = experience) -> required
        clause = _clause(sentence, german)
        cues = [m.group(0) for m in OPTIONAL_CUES.finditer(clause)]

        if cues:
            strong = any(not WEAK_OPTIONAL.search(cue) for cue in cues)
            clause_start = sentence.find(clause)
            level_in_clause = _nearest_level(
                clause, german.start() - clause_start, german.end() - clause_start
            )

            # "Bereitschaft ... und verhandlungssichere Deutschkenntnisse":
            # a weak hint loses against a level attached to German.
            if strong or level_in_clause is None:
                optional_hit = optional_hit or window
                continue

        if not REQUIREMENT_CUES.search(window):
            continue

        level = _nearest_level(
            window,
            german.start() - offset,
            german.end() - offset,
        )

        rank = level or 0

        if best is None or rank > best[0]:
            best = (rank, window, level)

    if best is not None:
        return {
            "requirement": "required",
            "level_value": best[2],
            "evidence": snippet(best[1]),
        }

    if not_required_hit:
        return {
            "requirement": "not_required",
            "level_value": None,
            "evidence": snippet(not_required_hit),
        }

    if optional_hit:
        return {
            "requirement": "optional",
            "level_value": None,
            "evidence": snippet(optional_hit),
        }

    if language == "de":
        return {
            "requirement": "implied",
            "level_value": None,
            "evidence": "Listing is written in German.",
        }

    return {
        "requirement": "none_mentioned",
        "level_value": None,
        "evidence": None,
    }


# ==================================================
# VISA / WORK AUTHORIZATION / RELOCATION
# ==================================================

VISA_TOPIC = re.compile(
    r"visa|visum|work permit|residence permit|aufenthalt\w*"
    r"|arbeitserlaubnis|arbeitsgenehmigung|work authori[sz]ation"
    r"|authori[sz]ed to work|right to work|(?:legally )?(?:allowed|permitted|entitled|eligible) to work"
    r"|blue card|blaue karte|\bsponsor\w*|\beu[- ]?(?:citizen|national|b(?:ü|u)rger|staatsb)"
    r"|staatsangeh\w+|arbeitsberechtigung"
    r"|berechtigung zur beschäftigung|beschäftigungserlaubnis"
    r"|skilled worker|highly skilled migrant|kennismigrant|\bhsm\b|critical skills"
    r"|employment permit|stamp\s*(?:4|1g)|settled status|indefinite leave"
    # Canada, Austria, Switzerland
    r"|canadian citizen|permanent residen\w+|\blmia\b|red[- ]white[- ]red|rot[- ]weiß[- ]rot"
    r"|\brwr\b|swiss (?:work )?permit|\b(?:b|c|g) permit|eu/efta",
    re.IGNORECASE,
)

NEGATIVE_VISA = compile_all([
    r"\bno (?:visa )?sponsorship\b",
    r"\bno visa\b",
    r"(?:not|n't|unable to|cannot|can't|won't|will not|do not|does not)\s+(?:\w+\s+){0,3}(?:sponsor|provide visa|offer visa)",
    r"sponsorship (?:is |are )?not (?:available|offered|provided|possible)",
    r"without (?:the need for )?(?:visa )?sponsorship",
    r"keine?n?\s+(?:\w+\s+){0,3}(?:visum|visa|sponsoring|aufenthaltstitel)",
    r"nicht\s+(?:\w+\s+){0,4}(?:sponsern|visum|visa)",
    # "ein Visa- oder Relocation-Sponsoring können wir ... nicht anbieten"
    r"(?:visa|visum|sponsoring)[^.;\n]{0,80}?\b(?:nicht|keine?n?)\b[^.;\n]{0,40}?"
    r"\b(?:anbieten|bieten|übernehmen|unterstützen|sponsern|leisten|möglich)",
])

# Conditional statements: not a promise, not a refusal.
# "Visa sponsorship may be considered for exceptional candidates"
SOFT_SPONSOR = re.compile(
    r"(?:visa|work permit|blue card)s?\W+(?:\w+\W+){0,2}sponsor\w*\W+(?:\w+\W+){0,3}"
    r"(?:may|might|could)\W+(?:\w+\W+){0,2}(?:considered|discussed|possible|available|offered)"
    r"|(?:may|might|could)\W+(?:\w+\W+){0,3}(?:consider|offer|provide|support|sponsor)\w*\W+"
    r"(?:\w+\W+){0,3}(?:visa|work permit|blue card)"
    r"|(?:visa|sponsorship)\W+(?:\w+\W+){0,4}case[- ]by[- ]case",
    re.IGNORECASE,
)

POSITIVE_VERBS = re.compile(
    r"\b(?:offer\w*|provid\w+|available|possible|included|includ\w+"
    r"|support\w*|assist\w*|help\w*|we sponsor|will sponsor|can sponsor"
    r"|able to sponsor|happy to|ready to|übernehm\w+|unterstütz\w*|bieten)\b",
    re.IGNORECASE,
)

_PERMITS = (
    r"(?:visa|work permit|blue card|skilled worker|highly skilled migrant|kennismigrant"
    r"|critical skills|employment permit|lmia|red[- ]white[- ]red card|rot[- ]weiß[- ]rot[- ]karte"
    r"|rwr[- ]karte|rwr card)"
)

SPONSOR_TERM = re.compile(
    _PERMITS + r"s?\W+(?:\w+\W+){0,2}sponsor\w*"
    r"|sponsor\w*\W+(?:\w+\W+){0,3}" + _PERMITS + r"s?"
    r"|sponsor\w*\W+(?:\w+\W+){0,3}permits?",
    re.IGNORECASE,
)

SUPPORT_VISA = re.compile(
    r"(?:support|assist|help|unterstütz\w*|begleit\w*|kümmern\w*)\W+(?:\w+\W+){0,6}"
    r"(?:visa|visum|work permit|aufenthalt\w*|arbeitserlaubnis|arbeitsgenehmigung|blue card|blaue karte|einreise"
    r"|employment permit|critical skills|highly skilled migrant|kennismigrant|skilled worker"
    r"|lmia|red[- ]white[- ]red card|rot[- ]weiß[- ]rot[- ]karte|rwr[- ]karte)"
    r"|(?:visa|visum|work permit|aufenthalt\w*|arbeitserlaubnis|blue card|blaue karte)\W+(?:\w+\W+){0,4}"
    r"(?:support|assistance|unterstützung|unterstützen|übernehmen|help)",
    re.IGNORECASE,
)

# Gulf wording: the employer gives the visa as part of the package.
#   "Employment visa will be provided", "Company-sponsored residence visa",
#   "Benefits: Visa, medical insurance, annual air ticket"
VISA_PROVIDED = re.compile(
    r"(?:employment|work|residence|residency|working)\s+visas?\W+(?:\w+\W+){0,3}"
    r"(?:provided|sponsored|included|covered|arranged|processed|paid)"
    r"|(?:company|employer)[- ](?:sponsored|provided|paid)\s+(?:\w+\s+){0,2}visas?"
    r"|visas?\s+(?:will be\s+|is\s+|are\s+)?(?:provided|sponsored|arranged|covered|processed)"
    r"\s+by\s+(?:the\s+)?(?:company|employer|us)"
    r"|(?:company|employer|we)\s+(?:will\s+)?(?:provides?|sponsors?|arranges?|issues?)\s+(?:the\s+|your\s+)?"
    r"(?:employment\s+|work\s+|residence\s+|residency\s+)?visas?"
    r"|\bvisas?\s*(?:,|\+|&|and)\s*(?:medical|health|insurance|flights?|air|tickets?|accommodation)"
    r"|(?:medical|health insurance|tickets?|accommodation)\s*(?:,|\+|&|and)\s*(?:employment\s+|residence\s+)?visas?\b",
    re.IGNORECASE,
)

# "You must already have the right to work..." style requirements.
# Deliberately narrow: a sentence only counts when it states a
# REQUIREMENT. Mentioning nationality or citizenship in an
# equal-opportunity sentence is not a work-authorization rule.
_AUTH_WORDS = (
    "work permit|work visa|residence permit|right to work|work authori[sz]ation"
    "|arbeitserlaubnis|arbeitsgenehmigung|aufenthaltstitel"
    "|aufenthaltsgenehmigung|arbeitsberechtigung"
    "|berechtigung zur beschäftigung|beschäftigungserlaubnis"
    # UK / Ireland: already holding a status that allows work
    "|stamp\\s*(?:4|1g)|settled status|pre-settled status|indefinite leave to remain"
    "|eu passport|irish citizenship|british citizenship|uk passport"
    # Canada / Switzerland
    "|canadian citizen\\w*|permanent residen\\w+|\\bpr status|swiss work permit"
    "|(?:b|c|g) permit|eu/efta (?:citizenship|passport|nationality)"
)

_ALLOWED_TO_WORK = (
    "authori[sz]ed to work|eligible to work"
    "|(?:legally )?(?:allowed|permitted|entitled) to work"
)

WORK_AUTH_REQUIRED = compile_all([
    r"(?:valid|existing|current|unrestricted|gültige[rn]?|bestehende[rn]?)\s+(?:\w+\s+){0,2}(?:"
    + _AUTH_WORDS + ")",
    r"(?:must|need to|needs to|have to|required to|should|müssen|musst|solltest|sollten)\s+(?:\w+\s+){0,6}(?:"
    + _AUTH_WORDS + "|" + _ALLOWED_TO_WORK + ")",
    "(?:" + _AUTH_WORDS + r")\s+(?:\w+\s+){0,5}(?:is |are |ist |sind )?"
    r"(?:required|mandatory|needed|necessary|erforderlich|notwendig|vorausgesetzt|zwingend|nachzuweisen)",
    r"(?:authori[sz]ed|eligible|legally (?:allowed|permitted|entitled)|allowed|permitted) to work (?:in|within) (?:the )?(?:germany|eu|europe|european union|uk|united kingdom|ireland|netherlands|eea"
    r"|canada|austria|österreich|switzerland|schweiz|eu/efta)",
    r"\beu[- ]?(?:citizens?|nationals?)\s+(?:\w+\s+){0,3}(?:only|required)"
    r"|\bonly\s+(?:\w+\s+){0,2}eu[- ]?(?:citizens?|nationals?)"
    r"|\bnur\s+(?:\w+\s+){0,2}eu[- ]?b(?:ü|u)rger",
    r"(?:eu|deutsche)[- ]?staatsangeh\w+\s+(?:\w+\s+){0,3}(?:erforderlich|voraussetzung|vorausgesetzt)",
])

EQUAL_OPPORTUNITY = re.compile(
    r"regardless|irrespective|independent of|unabhängig|ungeachtet"
    r"|diskriminier|discriminat|equal opportunit|chancengleichheit"
    r"|diversity|vielfalt|inclusive|inklusi",
    re.IGNORECASE,
)


def is_work_auth_requirement(sentence: str) -> bool:
    if EQUAL_OPPORTUNITY.search(sentence):
        return False

    return first_match(WORK_AUTH_REQUIRED, sentence) is not None


RELOCATION_POSITIVE = compile_all([
    r"relocation (?:support|assistance|package|bonus|budget|allowance|help|services?|benefits?|stipend|expenses|costs?|payment|offered|available|provided|possible)",
    r"(?:help|support|assist|cover|pay)\w*\W+(?:\w+\W+){0,4}relocat\w+",
    r"relocat\w+\W+(?:\w+\W+){0,3}(?:support|assist|help|covered|paid|package)",
    r"umzugs\w*\W*(?:hilfe|unterstützung|kosten|zuschuss|pauschale|prämie)",
    r"unterstützung\w*\s+(?:\w+\s+){0,3}(?:beim|bei)\s+(?:umzug|relocation)",
    r"relocation[- ]?(?:hilfe|unterstützung|paket|bonus|zuschuss)",
])

RELOCATION_NEGATIVE = compile_all([
    r"no relocation",
    r"(?:not|n't|unable to|cannot)\s+(?:\w+\s+){0,4}(?:support|offer|provide|cover|assist|help)\w*"
    r"\W+(?:\w+\W+){0,6}relocat\w+",
    r"relocation (?:is )?not (?:offered|available|provided|possible)",
    r"keine?\w*\s+(?:\w+\s+){0,2}(?:relocation|umzug\w*)",
    r"without relocation",
])


def analyze_visa(text: str) -> dict:
    """
    Returns visa_status (yes | maybe | no | mixed | unknown),
    visa_evidence, work_authorization_required, work_authorization_evidence.
    """

    positive_hit = None
    negative_hit = None
    soft_hit = None
    auth_hit = None

    for sentence in split_sentences(text):
        if not VISA_TOPIC.search(sentence):
            continue

        # "Sponsor" alone is often marketing ("event sponsor");
        # only trust it next to visa/permit words.
        negative = first_match(NEGATIVE_VISA, sentence)

        if negative:
            negative_hit = negative_hit or sentence
            continue

        # Checked before the positive rules: "sponsorship may be
        # available" contains "available" but promises nothing.
        if SOFT_SPONSOR.search(sentence):
            soft_hit = soft_hit or sentence
            continue

        positive = (
            (SPONSOR_TERM.search(sentence) and POSITIVE_VERBS.search(sentence))
            or SUPPORT_VISA.search(sentence)
            or VISA_PROVIDED.search(sentence)
        )

        if positive:
            positive_hit = positive_hit or sentence
            continue

        if is_work_auth_requirement(sentence):
            auth_hit = auth_hit or sentence

    if positive_hit and negative_hit:
        status, evidence = "mixed", snippet(negative_hit)
    elif negative_hit:
        status, evidence = "no", snippet(negative_hit)
    elif positive_hit:
        status, evidence = "yes", snippet(positive_hit)
    elif soft_hit:
        status, evidence = "maybe", snippet(soft_hit)
    else:
        status, evidence = "unknown", "No clear visa statement detected."

    return {
        "visa_status": status,
        "visa_evidence": evidence,
        "work_authorization_required": bool(auth_hit),
        "work_authorization_evidence": snippet(auth_hit) if auth_hit else None,
    }


def analyze_relocation(text: str) -> dict:
    positive_hit = None
    negative_hit = None

    for sentence in split_sentences(text):
        if first_match(RELOCATION_NEGATIVE, sentence):
            negative_hit = negative_hit or sentence
        elif first_match(RELOCATION_POSITIVE, sentence):
            positive_hit = positive_hit or sentence

    if negative_hit and not positive_hit:
        return {
            "relocation_support": "no",
            "relocation_evidence": snippet(negative_hit),
        }

    if positive_hit:
        return {
            "relocation_support": "yes",
            "relocation_evidence": snippet(positive_hit),
        }

    return {
        "relocation_support": "unknown",
        "relocation_evidence": "No relocation statement detected.",
    }


# ==================================================
# REMOTE WORK
# ==================================================

STRONG_REMOTE = re.compile(
    r"fully remote|100 ?% remote|remote[- ]first|completely remote"
    r"|full[- ]remote|work fully remote(?:ly)?|vollständig remote"
    r"|komplett remote|vollremote|100 ?% (?:homeoffice|home office)"
    r"|remote (?:position|role|job)|remote work (?:is )?(?:possible|available)"
    r"|work from anywhere|\(remote\)|\bremote\s*[-–|/]",
    re.IGNORECASE,
)

HYBRID = re.compile(
    r"hybrid|hybrides? arbeit\w*|teilweise (?:remote|homeoffice|home office|im homeoffice)"
    r"|\b(?:\d|two|three|zwei|drei)\s*(?:days?|tage?)\s*(?:per|a|pro|in the|im|in der|/)\s*(?:week|woche|office|büro)"
    r"|(?:option|possibility|möglichkeit)\s+(?:to\s+)?(?:work|working|arbeiten)\s+(?:remote|remotely|mobil|im homeoffice)"
    r"|(?:remote|remotely|homeoffice)\s+(?:on|am)\s+(?:mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|montag|dienstag|mittwoch|donnerstag|freitag)"
    r"|in the office (?:monday|\d|two|three|four)",
    re.IGNORECASE,
)

REMOTE_WORLDWIDE = re.compile(
    r"(?:remote|work)\W+(?:\w+\W+){0,6}(?:worldwide|anywhere|globally|any country|any location|all countries)"
    r"|(?:worldwide|anywhere in the world|globally)\W+(?:\w+\W+){0,3}remote"
    r"|work from anywhere"
    r"|remote\W+(?:\w+\W+){0,3}(?:from )?(?:any|every) (?:country|location)",
    re.IGNORECASE,
)

# A perk, not a remote job: "work from anywhere for up to 4 weeks a year".
WORK_FROM_ANYWHERE_PERK = re.compile(
    r"(?:work(?:ing)?|remote)\W+(?:\w+\W+){0,3}(?:anywhere|abroad)\W+(?:\w+\W+){0,3}?"
    r"(?:\d+|one|two|three|four|six|several|a few)\s*(?:weeks?|days?|months?)",
    re.IGNORECASE,
)

REMOTE_GERMANY_ONLY = re.compile(
    r"(?:remote|home ?office|mobiles arbeiten|work from home)\W+(?:\w+\W+){0,8}(?:within|in|from|aus|innerhalb|nur|only|inside)\W+(?:\w+\W+){0,2}(?:germany|deutschland)"
    r"|(?:based|located|living|residing|resident|wohnhaft|ansässig|wohnsitz)\W+(?:\w+\W+){0,4}(?:germany|deutschland)"
    r"|deutschlandweit|bundesweit|remote[ -]?(?:de|germany)\b",
    re.IGNORECASE,
)

# Remote, but only from inside one of the countries JobRadar searches.
REMOTE_COUNTRY_ONLY = re.compile(
    r"(?:remote|home ?office|work from home|wfh)\W+(?:\w+\W+){0,6}(?:within|in|from|inside|only)\W+(?:the\W+)?"
    r"(?:uk|united kingdom|england|netherlands|nederland|ireland|uae|united arab emirates|saudi arabia|ksa|qatar"
    r"|canada|austria|österreich|switzerland|schweiz|kuwait|oman)\b"
    r"|(?:based|located|living|residing|resident|residents)\W+(?:\w+\W+){0,4}(?:the\W+)?"
    r"(?:uk|united kingdom|netherlands|ireland|canada|austria|switzerland)\b"
    r"|\bremote\s*[-–(]\s*(?:uk|united kingdom|netherlands|nl|ireland|ie|canada|ca|austria|at|switzerland|ch)\b"
    r"|\b(?:uk|netherlands|ireland|canada|austria|switzerland)[- ](?:based|remote)\b"
    r"|österreichweit|schweizweit",
    re.IGNORECASE,
)

REMOTE_EU_ONLY = re.compile(
    r"\beu[- ]based|\beu only|\beu residents?|\beea residents?"
    r"|(?:based|located|residing|living|resident|residents)\W+(?:\w+\W+){0,3}(?:the )?(?:eu|european union|eea|europe)\b"
    r"|within the (?:eu|european union|eea)"
    r"|remote\s+(?:in|within|across|from)\s+(?:the\s+)?(?:eu|europe|european union|eea)\b"
    r"|(?:eu|europe)[- ]remote"
    r"|remote\s*(?:[-–]\s*)?(?:in|within|across|from)\s+(?:the\s+)?(?:eu|european union|europe|eea)\b"
    r"|remote\s*[(\[]\s*(?:eu|europe|eea)\s*[)\]]|\bremote\s+(?:eu|europe)\b"
    r"|work (?:permit|authori[sz]ation) (?:for|in) (?:the )?eu",
    re.IGNORECASE,
)

REMOTE_LIMITED = re.compile(
    r"eligible countries|selected countries|certain countries|supported countries"
    r"|approved countries|listed countries|countries where we (?:operate|have)",
    re.IGNORECASE,
)

REMOTE_EMEA = re.compile(r"\bemea\b|\bafrica\b", re.IGNORECASE)

INTERNATIONAL_FRIENDLY = re.compile(
    # The Dutch 30% ruling is a tax benefit for people hired from abroad.
    r"30\s?%\s*(?:tax\s*)?(?:ruling|regeling|facility)|\bexpat (?:tax|ruling|package)"
    r"|(?:international|global|diverse)\s+(?:team|teams|applicants|candidates|talent|workforce|environment)"
    r"|applicants? from (?:all over|around) the world|open to (?:international|candidates from)"
    r"|candidates from abroad|bewerber\w* aus dem ausland|internationale\w* team"
    r"|applicants? (?:from )?outside (?:of )?(?:the )?eu",
    re.IGNORECASE,
)

ENGLISH_WORKING_LANGUAGE = re.compile(
    r"(?:company|working|team|business|corporate|office|everyday|daily)\s+language\s+(?:is|will be)?\s*(?:english|englisch)"
    r"|arbeitssprache\s+(?:ist\s+)?englisch|english[- ]speaking\s+(?:team|environment|company|workplace)"
    r"|(?:our|the) team (?:speaks|communicates in) english|english only|we speak english"
    r"|(?:kommunikations|unternehmens)sprache\s+(?:ist\s+)?englisch",
    re.IGNORECASE,
)


def analyze_remote(job: Job, text: str) -> dict:
    headline = f"{job.title or ''} {job.location or ''}"

    has_remote = bool(
        STRONG_REMOTE.search(text)
        or re.search(r"\bremote\b|homeoffice", headline, re.IGNORECASE)
    )
    has_hybrid = bool(HYBRID.search(text))
    fully = bool(re.search(r"fully remote|100 ?% remote|vollständig remote|komplett remote|vollremote", text, re.IGNORECASE))

    if has_hybrid and not fully:
        work_mode = "hybrid"
    elif has_remote:
        work_mode = "remote"
    else:
        work_mode = "unclear"

    if work_mode != "remote":
        return {"work_mode": work_mode, "remote_scope": "unknown"}

    scope_text = f"{headline} {text}"

    worldwide = bool(REMOTE_WORLDWIDE.search(WORK_FROM_ANYWHERE_PERK.sub(" ", scope_text)))
    germany = bool(REMOTE_GERMANY_ONLY.search(scope_text))
    country = bool(REMOTE_COUNTRY_ONLY.search(scope_text))
    eu = bool(REMOTE_EU_ONLY.search(scope_text))
    emea = bool(REMOTE_EMEA.search(scope_text))
    limited = bool(REMOTE_LIMITED.search(scope_text))

    restricted = germany or eu or country

    if worldwide and restricted:
        scope = "unknown"
    elif limited:
        scope = "limited_countries"
    elif germany:
        scope = "germany_only"
    elif country:
        scope = "country_only"
    elif eu:
        scope = "eu_only"
    elif worldwide:
        scope = "worldwide"
    elif emea:
        scope = "emea"
    else:
        scope = "unknown"

    return {"work_mode": work_mode, "remote_scope": scope}


# ==================================================
# SALARY HINT (used only as a seniority warning)
# ==================================================

SALARY_K = re.compile(
    r"€\s*(\d{2,3})(?:\s*[–—-]\s*(\d{2,3}))?\s*k\b"
    r"|(\d{2,3})(?:\s*[–—-]\s*(\d{2,3}))?\s*k\s*€",
    re.IGNORECASE,
)

SALARY_FULL = re.compile(
    r"(\d{2,3})[.,](\d{3})\s*(?:€|eur)|(?:€|eur)\s*(\d{2,3})[.,](\d{3})",
    re.IGNORECASE,
)


def extract_salary_hint(job: Job) -> Optional[float]:
    """
    Best-effort yearly EUR salary ceiling from structured data or the
    title. Returns None when nothing reliable is found.
    """

    amounts = []

    try:
        maximum = float(job.max_amount) if job.max_amount else None
    except (TypeError, ValueError):
        maximum = None

    interval = (getattr(job, "interval", None) or "").lower()
    currency = (getattr(job, "currency", None) or "EUR").upper()

    if maximum and currency in ("EUR", "€"):
        if interval in ("yearly", "year", "annual"):
            amounts.append(maximum)
        elif interval in ("monthly", "month"):
            amounts.append(maximum * 12)

    title = job.title or ""

    for match in SALARY_K.finditer(title):
        numbers = [g for g in match.groups() if g]
        amounts.append(max(float(n) for n in numbers) * 1000)

    for match in SALARY_FULL.finditer(title):
        groups = [g for g in match.groups() if g]
        amounts.append(float(groups[0]) * 1000 + float(groups[1]))

    return max(amounts) if amounts else None


# ==================================================
# OTHER LANGUAGES (Arabic, Dutch, French...)
# ==================================================

# German has its own, finer analysis above. These use a simpler one:
# required (with a level) / optional / not required.

_NOT_A_LANGUAGE = (
    r"(?!\W+(?:law|laws|market\w*|compan\w+|clients?|customers?|government"
    r"|nationals?|citizens?|nationality|content|localization|localisation"
    r"|rtl|nlp|text|fonts?|interfaces?|ui|websites?|apps?|version|speaking market"
    r"|cuisine|food|team|office|entity|subsidiary|tech|riviera|alps)\b)"
)

LANGUAGE_TERMS = {
    "Arabic": r"\barabic\b|\barabisch\b|العربية|عربي",
    "French": r"\bfrench\b|\bfrançais\b|\bfrancais\b|französisch",
    "Dutch": r"\bdutch\b|\bnederlands\b|niederländisch",
    "Spanish": r"\bspanish\b|\bespañol\b|\bespanol\b|spanisch",
    "Italian": r"\bitalian\b|\bitaliano\b|italienisch",
    "Portuguese": r"\bportuguese\b|\bportuguês\b",
    "Swedish": r"\bswedish\b|\bsvenska\b",
    "Danish": r"\bdanish\b|\bdansk\b",
    "Norwegian": r"\bnorwegian\b|\bnorsk\b",
    "Finnish": r"\bfinnish\b|\bsuomi\b",
    "Turkish": r"\bturkish\b|\btürkçe\b",
    "Russian": r"\brussian\b",
    "Hindi": r"\bhindi\b",
    "Urdu": r"\burdu\b",
    "Japanese": r"\bjapanese\b",
    "Mandarin": r"\bmandarin\b|\bchinese\b",
    "Korean": r"\bkorean\b",
    "Hebrew": r"\bhebrew\b",
}

LANGUAGE_PATTERNS = {
    name: re.compile("(?:" + term + ")" + _NOT_A_LANGUAGE, re.IGNORECASE)
    for name, term in LANGUAGE_TERMS.items()
}

# Every language name (German and English included): a level separated
# from the language by another language does not belong to it.
ANY_LANGUAGE = re.compile(
    "|".join(LANGUAGE_TERMS.values())
    + r"|\benglish\b|\benglisch\b|\bgerman\b|\bdeutsch\w*",
    re.IGNORECASE,
)

LANGUAGE_CUES = re.compile(
    r"speak|speaker|speaking|fluen|proficien|native|mother tongue|bilingual"
    r"|language|written|spoken|verbal|communication|command of|knowledge of"
    r"|\blevel\b|\b[abc][12]\b|skills?\b|kenntnis|sprach"
    r"|إجادة|يشترط|مطلوب|طلاقة|اللغة",
    re.IGNORECASE,
)

LANGUAGE_REQUIRED_CUES = re.compile(
    r"\bmust\b|required|mandatory|essential|necessary|\bneed|fluen|proficien"
    r"|native|mother tongue|bilingual|excellent|strong|good|\b[abc][12]\b"
    r"|erforderlich|vorausgesetzt|يشترط|مطلوب|إجادة|طلاقة",
    re.IGNORECASE,
)

LANGUAGE_OPTIONAL_CUES = re.compile(
    r"\bplus\b|nice[- ]to[- ]have|advantage\w*|beneficial|bonus|desirable"
    r"|preferred|preferabl\w+|ideally|\basset\b|would be great|helpful"
    r"|appreciated|encouraged|optional|von vorteil|wünschenswert",
    re.IGNORECASE,
)

LANGUAGE_NOT_REQUIRED = re.compile(
    r"(?:is |are )?not (?:required|needed|necessary|mandatory|a requirement)"
    r"|\bno\s+$|\bwithout\s+$",
    re.IGNORECASE,
)

# Used when a listing requires a language but names no level.
DEFAULT_LANGUAGE_LEVEL = 4  # B2

_RANK = {"required": 3, "not_required": 2, "optional": 1}


def analyze_other_languages(text: str) -> dict:
    """
    -> {"Arabic": {"requirement": "required", "level_value": 5,
                   "evidence": "..."}, ...}
    Only languages the listing actually talks about as languages.
    """

    found = {}

    for sentence in split_sentences(text):
        for name, pattern in LANGUAGE_PATTERNS.items():
            for match in pattern.finditer(sentence):
                window, offset = _window(sentence, match)

                clause = _clause(sentence, match)
                after = sentence[match.end(): match.end() + 40]

                # "Arabic content", "French clients" are not about the
                # language; "Dutch is a plus" is, even without a cue word.
                if not (
                    LANGUAGE_CUES.search(window)
                    or LANGUAGE_OPTIONAL_CUES.search(after[:30])
                    or LANGUAGE_NOT_REQUIRED.match(after.strip())
                ):
                    continue

                before = sentence[max(0, match.start() - 12): match.start()]

                if LANGUAGE_NOT_REQUIRED.match(after.strip()) or LANGUAGE_NOT_REQUIRED.search(before):
                    result = ("not_required", None)
                elif LANGUAGE_OPTIONAL_CUES.search(clause):
                    result = ("optional", None)
                elif LANGUAGE_REQUIRED_CUES.search(window):
                    level = _nearest_level(
                        window,
                        match.start() - offset,
                        match.end() - offset,
                        other=ANY_LANGUAGE,
                    )
                    result = ("required", level or DEFAULT_LANGUAGE_LEVEL)
                else:
                    continue

                current = found.get(name)
                better = current is None or (
                    _RANK[result[0]] > _RANK[current["requirement"]]
                    or (
                        result[0] == current["requirement"] == "required"
                        and result[1] > current["level_value"]
                    )
                )

                if better:
                    found[name] = {
                        "requirement": result[0],
                        "level_value": result[1],
                        "evidence": snippet(sentence),
                    }

    return found


# ==================================================
# LOCAL HIRING ONLY (mostly Gulf)
# ==================================================

_GULF_PEOPLE = (
    r"(?:uae|emirati|saudi|qatari|kuwaiti|omani|bahraini|gcc|local)"
)
_GULF_PLACES = (
    r"(?:the\s+)?(?:uae|u\.a\.e\.?|united arab emirates|dubai|abu dhabi|sharjah"
    r"|saudi arabia|ksa|the kingdom|riyadh|jeddah|dammam|khobar|qatar|doha"
    r"|kuwait|oman|muscat|bahrain|manama|gcc|middle east)"
)

NATIONALS_ONLY = compile_all([
    _GULF_PEOPLE + r"\s+nationals?\s+only",
    r"(?:only|exclusively)\s+(?:for\s+|open to\s+)?" + _GULF_PEOPLE + r"\s+(?:nationals?|citizens?)",
    r"(?:open|available|restricted|limited)\s+(?:only\s+)?to\s+" + _GULF_PEOPLE + r"\s+(?:nationals?|citizens?)",
    r"must be (?:a |an )?" + _GULF_PEOPLE + r"\s+(?:nationals?|citizens?)",
    r"\bemiratis?\s+only|(?:uae|saudi|qatari|kuwaiti|omani|bahraini)\s+nationality\s+(?:is\s+)?(?:required|only|mandatory)",
    r"(?:emiratisation|emiratization|saudization|saudisation|qatarization|qatarisation"
    r"|omanization|omanisation|kuwaitization|bahrainization)\s+(?:role|position|job|vacancy|opportunit\w+|only|program\w*\s+(?:role|position|vacancy))",
    r"للمواطنين فقط|للسعوديين فقط|سعوديين فقط|للإماراتيين|للقطريين",
])

NATIONALS_PREFERRED = re.compile(
    _GULF_PEOPLE + r"\s+(?:nationals?|citizens?)\s+(?:\w+\s+){0,2}(?:preferred|encouraged|prioriti[sz]ed|first)"
    r"|(?:preference|priority)\s+(?:\w+\s+){0,3}" + _GULF_PEOPLE + r"\s+(?:nationals?|citizens?)",
    re.IGNORECASE,
)

IN_COUNTRY_ONLY = compile_all([
    r"(?:candidates?|applicants?|only)\s+(?:\w+\s+){0,3}(?:currently\s+)?(?:based|residing|living|located|present)\s+in\s+"
    + _GULF_PLACES + r"\W+(?:\w+\W+){0,2}(?:only|can apply|will be considered|need apply)",
    r"(?:must|should)\s+(?:\w+\s+){0,2}currently\s+(?:be\s+)?(?:based|residing|living|located|present)\s+in\s+" + _GULF_PLACES,
    r"\bin[- ]country\s+(?:candidates?|applicants?|hires?|only)",
    r"\blocal\s+(?:candidates?|applicants?|hires?)\s+only|only\s+local\s+(?:candidates?|applicants?)",
    r"transferr?able\s+(?:iqama|visa|residence)",
    r"(?:own|valid)\s+(?:\w+\s+){0,2}(?:iqama|residence visa|residency visa|uae visa|qatar id|qid)",
    r"(?:husband|father|family|spouse|parents?)'?s?\s+(?:visa|sponsorship)",
    r"visit visa (?:holders?|candidates?)",
    r"(?:no|without)\s+visa\s+(?:sponsorship|processing|provided)\s+(?:\w+\s+){0,3}(?:in|within|for)\s+" + _GULF_PLACES,
])

IN_COUNTRY_PREFERRED = re.compile(
    r"(?:candidates?|applicants?)\s+(?:\w+\s+){0,3}(?:currently\s+)?(?:based|residing|living|located)\s+in\s+"
    + _GULF_PLACES + r"\W+(?:\w+\W+){0,3}(?:preferred|preference|advantage|plus|priority)"
    r"|(?:must|should)\s+be\s+(?:based|residing|living|located)\s+in\s+" + _GULF_PLACES
    + r"|immediate joiners?",
    re.IGNORECASE,
)

RELOCATION_WORDS = re.compile(r"relocat\w+|willing to move|move to", re.IGNORECASE)


# In a title, naming the nationality is enough:
#   "Full Stack Development & UX Design – Onsite-KSA_Saudi Nationals"
NATIONALS_IN_TITLE = re.compile(
    r"(?:saudi|emirati|uae|qatari|kuwaiti|omani|bahraini)[\s_\-]*nationals?\b"
    r"|(?:saudi|emirati|qatari|kuwaiti|omani|bahraini)[\s_\-]*nation\b"
    r"|\b(?:saudization|saudisation|emiratisation|emiratization|qatarization)\b"
    r"|\bemiratis? only\b",
    re.IGNORECASE,
)


def analyze_local_hire(text: str, title: str = "") -> dict:
    """
    -> local_hire: nationals_only | in_country_only | preferred | None
       local_hire_evidence
    """

    if title and NATIONALS_IN_TITLE.search(title):
        return {"local_hire": "nationals_only", "local_hire_evidence": f"Title: {title}"}

    preferred = None

    for sentence in split_sentences(text):
        if first_match(NATIONALS_ONLY, sentence):
            return {"local_hire": "nationals_only", "local_hire_evidence": snippet(sentence)}

        # "must be based in Dubai or willing to relocate" is not local only.
        if RELOCATION_WORDS.search(sentence):
            continue

        if first_match(IN_COUNTRY_ONLY, sentence):
            return {"local_hire": "in_country_only", "local_hire_evidence": snippet(sentence)}

        if not preferred and (
            NATIONALS_PREFERRED.search(sentence) or IN_COUNTRY_PREFERRED.search(sentence)
        ):
            preferred = sentence

    if preferred:
        return {"local_hire": "preferred", "local_hire_evidence": snippet(preferred)}

    return {"local_hire": None, "local_hire_evidence": None}


# ==================================================
# PUBLIC ENTRY POINT
# ==================================================

class EligibilityAnalyzer:
    """
    Fills the eligibility signal fields on a Job.
    """

    @classmethod
    def extract(cls, job: Job) -> dict:
        text = re.sub(r"[ \t]+", " ", job.description or "")

        if not text.strip():
            return {
                "job_language": None,
                "german_requirement": "none_mentioned",
                "german_level_required": None,
                "german_level_value": None,
                "german_evidence": None,
                "other_languages": {},
                **analyze_local_hire("", job.title or ""),
                "english_working_language": False,
                "visa_status": "unknown",
                "visa_evidence": "No job description available.",
                "work_authorization_required": False,
                "work_authorization_evidence": None,
                "relocation_support": "unknown",
                "relocation_evidence": "No job description available.",
                "work_mode": "unclear",
                "remote_scope": "unknown",
                "international_friendly": False,
                "has_description": False,
                "salary_hint_max_eur": extract_salary_hint(job),
            }

        language = detect_language(text)
        german = analyze_german_requirement(text, language)
        visa = analyze_visa(text)
        relocation = analyze_relocation(text)
        remote = analyze_remote(job, text)

        # A company that refuses relocation will not bring someone over
        # from outside the EU either (your label on Wolt's ad).
        if visa["visa_status"] == "unknown" and relocation["relocation_support"] == "no":
            visa["visa_status"] = "no"
            visa["visa_evidence"] = relocation["relocation_evidence"]

        return {
            "job_language": language,
            "german_requirement": german["requirement"],
            "german_level_required": level_label(german["level_value"]),
            "german_level_value": german["level_value"],
            "german_evidence": german["evidence"],
            "other_languages": analyze_other_languages(text),
            **analyze_local_hire(text, job.title or ""),
            "english_working_language": bool(
                ENGLISH_WORKING_LANGUAGE.search(text)
            ),
            **visa,
            **relocation,
            **remote,
            "international_friendly": bool(
                INTERNATIONAL_FRIENDLY.search(text)
            ),
            "has_description": True,
            "salary_hint_max_eur": extract_salary_hint(job),
        }

    @classmethod
    def analyze(cls, job: Job) -> Job:
        signals = cls.extract(job)

        job.job_language = signals["job_language"]
        job.german_requirement = signals["german_requirement"]
        job.german_level_required = signals["german_level_required"]
        job.german_level_value = signals["german_level_value"]
        job.german_evidence = signals["german_evidence"]
        job.other_languages = signals["other_languages"]
        job.local_hire = signals["local_hire"]
        job.local_hire_evidence = signals["local_hire_evidence"]
        job.english_working_language = signals["english_working_language"]

        job.visa_sponsorship_status = signals["visa_status"]
        job.visa_sponsorship_evidence = signals["visa_evidence"]
        job.work_authorization_required = signals["work_authorization_required"]
        job.work_authorization_evidence = signals["work_authorization_evidence"]

        job.relocation_support = signals["relocation_support"]
        job.relocation_evidence = signals["relocation_evidence"]

        job.work_mode = signals["work_mode"]
        job.remote_scope = signals["remote_scope"]
        job.international_friendly = signals["international_friendly"]
        job.has_description = signals["has_description"]
        job.salary_hint_max_eur = signals["salary_hint_max_eur"]

        return job