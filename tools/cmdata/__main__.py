"""CLI: ``python3 -m tools.cmdata FILE [--format json|md] [--out FILE]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import FORMATS, load_export


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
    args = parser.parse_args(argv)

    try:
        export = load_export(args.file)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    text = FORMATS[args.format](export)
    if args.out:
        Path(args.out).expanduser().write_text(text, encoding="utf-8", newline="")
        print(f"Wrote {args.out} ({len(text.encode('utf-8')):,} bytes)", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
