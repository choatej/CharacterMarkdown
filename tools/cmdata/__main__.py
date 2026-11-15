"""CLI: ``python3 -m tools.cmdata FILE [--format json|md] [--out FILE]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import FORMATS, load_export
from .render import ALL_SECTIONS, DEFAULT_SECTIONS, to_lean_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.cmdata",
        description="Render a '/cm save data' export (the JSON from tools.sv_export).",
    )
    parser.add_argument("file", help="the *_data_*.json file written by tools.sv_export")
    parser.add_argument(
        "--format", default="md", choices=sorted(FORMATS), help="output format (default: md)"
    )
    parser.add_argument("--out", help="write to this file instead of standard output")
    parser.add_argument(
        "--topics",
        help="md only: comma-separated sections to include, or 'all' "
        f"(default: {','.join(DEFAULT_SECTIONS)}; others: "
        f"{','.join(s for s in ALL_SECTIONS if s not in DEFAULT_SECTIONS)})",
    )
    args = parser.parse_args(argv)

    try:
        export = load_export(args.file)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    try:
        if args.format == "md" and args.topics:
            names = list(ALL_SECTIONS) if args.topics == "all" else args.topics.split(",")
            text = to_lean_markdown(export, [n.strip() for n in names])
        else:
            text = FORMATS[args.format](export)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).expanduser().write_text(text, encoding="utf-8", newline="")
        print(f"Wrote {args.out} ({len(text.encode('utf-8')):,} bytes)", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
