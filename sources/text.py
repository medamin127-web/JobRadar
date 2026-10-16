"""Turn job-board HTML into readable plain text (standard library only)."""

import html
import re

_BLOCK_END = re.compile(r"</(?:p|div|h[1-6]|ul|ol|tr|section|article)\s*>", re.IGNORECASE)
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LIST_ITEM = re.compile(r"<li[^>]*>", re.IGNORECASE)
_HEADING = re.compile(r"<h[1-6][^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def html_to_text(value) -> str:
    """
    '<h2>About</h2><ul><li>React</li></ul>' -> 'About\\n* React'

    Also works on HTML that was escaped once more (Greenhouse sends
    '&lt;p&gt;...'), and on plain text (returned unchanged, trimmed).
    """

    if not isinstance(value, str) or not value.strip():
        return ""

    text = value

    # Greenhouse escapes its HTML, and some Arbeitnow ads are escaped
    # inside real HTML: unescape (at most twice) until the tags are real.
    for _ in range(2):
        if "&lt;" in text:
            text = html.unescape(text)

    text = _BREAK.sub("\n", text)
    text = _HEADING.sub("\n", text)
    text = _LIST_ITEM.sub("\n* ", text)
    text = _BLOCK_END.sub("\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text).replace("\xa0", " ")

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]

    # One line per paragraph / list item, no empty lines.
    return "\n".join(line for line in lines if line)