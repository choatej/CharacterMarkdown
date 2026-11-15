"""Turn a CharacterMarkdown SavedVariables export into .md files.

In game:   /cm save   (or /cm save coach)   then   /reloadui
On the PC: python3 -m tools.sv_export

The game writes SavedVariables/CharacterMarkdown.lua when the UI reloads, logs out or quits.
`/cm save` puts the Markdown there as a list of short strings (`textParts`); this script
joins them and writes one file per saved character:

    <Character>_<YYYY-MM-DD>.md          full export   (/cm save)
    <Character>_coach_<YYYY-MM-DD>.md    compact export (/cm save coach)

Each saved format is written as its own file, so several formats can be saved side by side.

Standard library only. The Lua table reader is shared with tools.setdb.

Usage:
    python3 -m tools.sv_export [FILE] [--out DIR] [--character NAME] [--format NAME]
                               [--server live|pts]

With no file argument the script looks in the usual ESO locations (Windows, WSL and Linux
home folders). Set ESO_SV to a full path to override.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.setdb.reconcile import LuaReader

SV_GLOBAL = "CharacterMarkdownExport"
SV_FILE = "CharacterMarkdown.lua"


class ExportError(Exception):
    """A problem the user can fix; printed without a traceback."""


def candidate_paths(server: str = "live") -> list[Path]:
    """Places ESO keeps SavedVariables, most likely first."""
    rel = Path("Elder Scrolls Online") / server / "SavedVariables" / SV_FILE
    roots: list[Path] = []
    home = Path.home()
    roots += [home / "OneDrive" / "Documents", home / "Documents"]
    # WSL: the Windows profile lives under /mnt/c/Users/<name>
    users = Path("/mnt/c/Users")
    if users.is_dir():
        for user in sorted(users.iterdir()):
            roots += [user / "OneDrive" / "Documents", user / "Documents"]
    return [root / rel for root in roots]


def find_savedvariables(explicit: str | None, server: str = "live") -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ExportError(f"File not found: {path}")
        return path
    env = os.environ.get("ESO_SV")
    if env:
        path = Path(env).expanduser()
        if not path.is_file():
            raise ExportError(f"ESO_SV points to a missing file: {path}")
        return path
    for path in candidate_paths(server):
        if path.is_file():
            return path
    raise ExportError(
        f"Could not find {SV_FILE}. Pass its path, or set ESO_SV.\n"
        f"Looked for it under Documents/Elder Scrolls Online/{server}/SavedVariables."
    )


def read_export(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        export = LuaReader(text).global_assignment(SV_GLOBAL)
    except ValueError as err:
        raise ExportError(f"Could not read {path.name}: {err}") from err
    if not isinstance(export, dict) or not export.get("characters"):
        raise ExportError(
            f"No {SV_GLOBAL} data in {path}.\n"
            "In game: type /cm save, wait for 'Saved ... export', then /reloadui."
        )
    return export


def join_parts(entry: dict[str, Any], name: str) -> str:
    """Rebuild the Markdown text from a character's textParts."""
    parts = entry.get("textParts")
    if not isinstance(parts, list) or not parts:
        # The reader returns a dict when the numbering has a gap, i.e. a part was dropped.
        raise ExportError(
            f"{name}: saved text is incomplete (missing textParts). Run /cm save again."
        )
    text = "".join(parts)
    declared = entry.get("charCount")
    if isinstance(declared, int) and declared != len(text.encode("utf-8")):
        raise ExportError(
            f"{name}: expected {declared} bytes but found {len(text.encode('utf-8'))}. "
            "Part of the text was lost; run /cm save again."
        )
    return text


def safe_name(name: str) -> str:
    """'Little Franny Boo' -> 'Little_Franny_Boo' (keeps accented letters)."""
    return re.sub(r"[^\w-]+", "_", name, flags=re.UNICODE).strip("_") or "character"


# File extension per format; anything not listed is Markdown text.
EXTENSIONS = {"json": "json", "yaml": "yaml"}


def output_name(name: str, fmt: str, entry: dict[str, Any]) -> str:
    """'Little_Franny_Boo_2026-11-11.md' for markdown, '..._coach_...' for other formats."""
    stamp = entry.get("timestamp")
    day = "undated"
    if isinstance(stamp, int):
        day = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")
    kind = "" if fmt == "markdown" else f"_{safe_name(fmt)}"
    return f"{safe_name(name)}{kind}_{day}.{EXTENSIONS.get(fmt, 'md')}"


def convert(
    sv_path: Path,
    out_dir: Path,
    character: str | None = None,
    fmt: str | None = None,
) -> list[Path]:
    export = read_export(sv_path)
    characters: dict[str, Any] = export["characters"]
    if character:
        wanted = {k: v for k, v in characters.items() if k.lower() == character.lower()}
        if not wanted:
            saved = ", ".join(sorted(characters))
            raise ExportError(f"No saved export for '{character}'. Saved characters: {saved}")
        characters = wanted

    # (name, format, entry) for everything that was saved
    items: list[tuple[str, str, dict[str, Any]]] = []
    for name in sorted(characters):
        exports = characters[name].get("exports") if isinstance(characters[name], dict) else None
        if not isinstance(exports, dict) or not exports:
            raise ExportError(f"{name}: no saved exports found. Run /cm save again.")
        for export_format in sorted(exports):
            if fmt is None or export_format.lower() == fmt.lower():
                items.append((name, export_format, exports[export_format]))
    if not items:
        raise ExportError(f"No saved '{fmt}' export. Run /cm save {fmt} in game first.")

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, export_format, entry in items:
        text = join_parts(entry, f"{name} ({export_format})")
        target = out_dir / output_name(name, export_format, entry)
        # newline="" keeps the text byte-for-byte (no CRLF conversion on Windows)
        with open(target, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.sv_export",
        description="Write the Markdown saved by '/cm save' to .md files.",
    )
    parser.add_argument("file", nargs="?", help="path to SavedVariables/CharacterMarkdown.lua")
    parser.add_argument("--out", default=".", help="output folder (default: current folder)")
    parser.add_argument("--character", help="only this character (default: all saved)")
    parser.add_argument("--format", help="only this format, e.g. markdown or coach (default: all)")
    parser.add_argument(
        "--server", default="live", choices=["live", "pts"], help="ESO client folder"
    )
    args = parser.parse_args(argv)

    try:
        sv_path = find_savedvariables(args.file, args.server)
        written = convert(sv_path, Path(args.out).expanduser(), args.character, args.format)
    except ExportError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    print(f"Read {sv_path}", file=sys.stderr)
    for path in written:
        print(f"Wrote {path} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
