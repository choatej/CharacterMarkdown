"""Read the add-on's legacy settings defaults straight from ``src/settings/Defaults.lua``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DEFAULTS_LUA = Path(__file__).resolve().parents[2] / "src" / "settings" / "Defaults.lua"

# `    includeHeader = true, -- comment`   (commented-out lines start with `--` and do not match)
_ASSIGNMENT = re.compile(r'^\s*([A-Za-z_]\w*)\s*=\s*(true|false|"[^"]*"|-?\d+(?:\.\d+)?)\s*,')


def read_lua_defaults(path: str | Path = DEFAULTS_LUA) -> dict[str, Any]:
    """The key/value pairs of ``Defaults:GetAll()``; booleans, strings and numbers only."""
    found: dict[str, Any] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = _ASSIGNMENT.match(line)
        if not match:
            continue
        key, raw = match.groups()
        if raw == "true":
            found[key] = True
        elif raw == "false":
            found[key] = False
        elif raw.startswith('"'):
            found[key] = raw[1:-1]
        else:
            found[key] = float(raw) if "." in raw else int(raw)
    return found
