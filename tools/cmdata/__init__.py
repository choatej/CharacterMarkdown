"""Typed model and output formats for ``/cm save data`` exports.

    from tools.cmdata import load_export, to_json, to_lean_markdown
    export = load_export("Name_data_2026-11-14.json")   # written by tools.sv_export
    print(to_lean_markdown(export))

Command line: ``python3 -m tools.cmdata FILE [--format json|md] [--out FILE]``
"""

from __future__ import annotations

import json
from pathlib import Path

from .export import CharacterExport
from .render import FORMATS, to_dict, to_json, to_lean_markdown

__all__ = [
    "FORMATS",
    "CharacterExport",
    "load_export",
    "to_dict",
    "to_json",
    "to_lean_markdown",
]


def load_export(path: str | Path) -> CharacterExport:
    """Read the JSON file ``tools.sv_export`` writes for a ``/cm save data`` export."""
    document = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    return CharacterExport.from_document(document)
