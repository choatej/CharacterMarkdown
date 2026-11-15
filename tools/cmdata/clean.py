"""Text cleanup for values that come out of the game.

The game decorates strings for its own UI: colour codes (``|cffffff657|r``), gender/plural
markup and emoji added by the add-on for the Markdown output. None of that is useful to a
program or a language model reading the data.
"""

from __future__ import annotations

import re

# |cRRGGBB ... |r  -> keep the text between the codes
_COLOUR = re.compile(r"\|c[0-9a-fA-F]{6}(.*?)(?:\|r|$)", re.S)
# a stray |r with no opening code
_STRAY_RESET = re.compile(r"\|r")
# leading emoji / symbols / spaces before the first letter, digit or bracket
_LEADING_DECORATION = re.compile(r"^[^\w(\[]+", re.UNICODE)
_WHITESPACE = re.compile(r"[ \t]+")


def strip_markup(text: str) -> str:
    """Remove ESO colour codes: ``"Adds |cffffff657|r Critical Chance"`` -> ``"Adds 657 ..."``."""
    text = _COLOUR.sub(r"\1", text)
    text = _STRAY_RESET.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def single_line(text: str) -> str:
    """Join a multi-paragraph description into one line."""
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def strip_decoration(text: str) -> str:
    """Remove leading emoji and symbols: ``"⚔️ Front Bar"`` -> ``"Front Bar"``."""
    return _LEADING_DECORATION.sub("", text).strip()


def none_if_blank(value: object) -> str | None:
    """The game uses ``""``, ``"-"``, ``"None"`` and ``False`` for "nothing here"."""
    if value is None or value is False:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned in ("", "-", "None", "none"):
            return None
        return cleaned
    return str(value)
