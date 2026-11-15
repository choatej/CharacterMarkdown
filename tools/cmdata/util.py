"""Small helpers shared by the topic models.

The data comes from Lua tables, which cannot tell an empty list from an empty table, so an
empty list arrives as ``{}``. These helpers make every ``from_raw`` tolerant of that, and of
keys that are missing because the user's settings left a topic out.
"""

from __future__ import annotations

from typing import Any


def get(raw: Any, *path: str, default: Any = None) -> Any:
    """Nested dict lookup that returns `default` instead of raising."""
    value = raw
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def as_list(value: Any) -> list[Any]:
    """A list, or ``[]`` for ``None``, ``{}`` (an empty Lua table) or anything else."""
    return value if isinstance(value, list) else []


def records(value: Any) -> list[dict[str, Any]]:
    """The dict elements of a list (an empty ``{}`` counts as an empty list)."""
    return [item for item in as_list(value) if isinstance(item, dict)]


def as_dict(value: Any) -> dict[str, Any]:
    """A dict, or ``{}`` for ``None`` or anything else."""
    return value if isinstance(value, dict) else {}


def strings(value: Any) -> list[str]:
    """The string elements of a list."""
    return [item for item in as_list(value) if isinstance(item, str)]


def number(value: Any) -> int | float | None:
    """The value if it is a real number (not a bool), otherwise ``None``."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value


def fmt_number(value: Any) -> str:
    """Number with thousands separators; anything else as text; missing as '?'."""
    if isinstance(value, bool) or value is None:
        return "?"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.1f}".rstrip("0").rstrip(".")
    return str(value)


def fmt_duration(seconds: Any) -> str | None:
    """'11d 5h' for a day or more, '5h 12m' under a day, None if there is nothing to show."""
    if not isinstance(seconds, int | float) or isinstance(seconds, bool) or seconds <= 0:
        return None
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {rest // 60}m"
