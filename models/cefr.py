"""
CEFR language levels as comparable numbers.

A1=1, A2=2, B1=3, B2=4, C1=5, C2=6 (native is treated as 6).
"""

import re
from typing import Optional

CEFR_VALUES = {
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6,
}

CEFR_LABELS = {value: label for label, value in CEFR_VALUES.items()}


def parse_level(label: Optional[str]) -> Optional[int]:
    """
    Convert a level label ("B2", "native", None) into a number.

    Returns None when the level is unknown, so callers can tell
    "unknown" apart from "low".
    """

    if not label:
        return None

    text = str(label).strip().upper()

    if text in {"NATIVE", "MOTHER TONGUE", "BILINGUAL"}:
        return 6

    match = re.search(r"\b([ABC][12])\b", text)

    if match:
        return CEFR_VALUES[match.group(1)]

    return None


def level_label(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None

    return CEFR_LABELS.get(value)
