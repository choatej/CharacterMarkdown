"""Print the configuration tree: ``python3 -m tools.cmconfig [--defaults] [--table] [--update-readme]``."""

from __future__ import annotations

import argparse
from pathlib import Path

from .legacy import read_lua_defaults
from .model import DEFAULT_TREE, ConfigCollection

README = Path(__file__).resolve().parents[2] / "data" / "config" / "README.md"
BEGIN, END = "<!-- mapping:begin -->", "<!-- mapping:end -->"


def readme_with_table(text: str, table: str) -> str:
    """Replace the generated table between the markers in the README text."""
    head, _, rest = text.partition(BEGIN)
    _, _, tail = rest.partition(END)
    return f"{head}{BEGIN}\n{table}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m tools.cmconfig", description=__doc__)
    parser.add_argument(
        "--tree", default=str(DEFAULT_TREE), help="tree JSON (default: data/config/tree.json)"
    )
    parser.add_argument(
        "--defaults", action="store_true", help="mark each item on/off as the add-on's defaults do"
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="print the mapping table (Markdown) instead of the tree",
    )
    parser.add_argument(
        "--update-readme",
        action="store_true",
        help="refresh the mapping table in data/config/README.md",
    )
    args = parser.parse_args(argv)

    tree = ConfigCollection.load(args.tree).with_defaults(read_lua_defaults())
    if args.update_readme:
        README.write_text(
            readme_with_table(README.read_text(encoding="utf-8"), tree.mapping_table()),
            encoding="utf-8",
        )
    elif args.table:
        print(tree.mapping_table())
    else:
        print(
            tree.render(tree.data_from_legacy(read_lua_defaults()))
            if args.defaults
            else tree.render()
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
