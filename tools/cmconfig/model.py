"""The configuration tree: structure (ConfigItem, ConfigCollection) apart from values (ConfigData).

The structure is the same for every user and is loaded from ``data/config/tree.json``. The values
are one flat ``path -> bool`` table, which is the only part that has to be saved. Keeping them apart
matters in Lua too: SavedVariables cannot store functions, metatables or cycles, and a tree with
parent links is full of cycles.

Semantics:

* Switching a node off switches off everything under it (``is_effective``), whatever the stored
  values of its descendants say.
* A node's stored value is its own switch. ``cascade`` writes a value to a node and its subtree.
* A node's ``state`` is ``on``, ``off`` or ``mixed`` (on, but something under it is not).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KINDS = ("item", "detail")
DOMAINS = ("content", "format", "profile")

DEFAULT_TREE = Path(__file__).resolve().parents[2] / "data" / "config" / "tree.json"


class ConfigItem:
    """One node of the tree. Holds structure and metadata, never a value."""

    def __init__(
        self,
        id: str,  # noqa: A002 - the JSON key is "id"
        label: str,
        *,
        kind: str = "item",
        domain: str = "content",
        settings: tuple[str, ...] = (),
        topics: tuple[str, ...] = (),
        description: str = "",
        parent: ConfigItem | None = None,
        is_root: bool = False,
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"{id}: unknown kind {kind!r}")
        if domain not in DOMAINS:
            raise ValueError(f"{id}: unknown domain {domain!r}")
        if "." in id or not id:
            raise ValueError(f"item id {id!r} must be non-empty and contain no '.'")
        self.is_root = is_root
        self.id = id
        self.label = label
        self.kind = kind
        self.domain = domain
        self.settings = settings
        self.topics = topics
        self.description = description
        self.parent = parent
        self.children: list[ConfigItem] = []
        if parent is not None:
            parent.children.append(self)

    # ---- structure -------------------------------------------------------------------------

    def get_parent(self) -> ConfigItem | None:
        """The parent item, or None for a top-level section."""
        return self.parent if self.parent is not None and not self.parent.is_root else None

    def get_children(self) -> list[ConfigItem]:
        return list(self.children)

    @property
    def path(self) -> str:
        """Dotted path from the top-level section, such as ``crafting.knowledge.recipes``."""
        parent = self.get_parent()
        return f"{parent.path}.{self.id}" if parent else self.id

    @property
    def depth(self) -> int:
        parent = self.get_parent()
        return parent.depth + 1 if parent else 0

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def ancestors(self) -> list[ConfigItem]:
        """Parent first, top-level section last."""
        found: list[ConfigItem] = []
        node = self.get_parent()
        while node is not None:
            found.append(node)
            node = node.get_parent()
        return found

    def descendants(self) -> Iterator[ConfigItem]:
        """Every item below this one, depth first."""
        for child in self.children:
            yield child
            yield from child.descendants()

    def walk(self) -> Iterator[ConfigItem]:
        """This item, then its descendants."""
        yield self
        yield from self.descendants()

    def siblings(self) -> list[ConfigItem]:
        parent = self.parent
        return [c for c in parent.children if c is not self] if parent else []

    @property
    def setting(self) -> str | None:
        """The legacy setting this item replaces (the first, if several)."""
        return self.settings[0] if self.settings else None

    # ---- values (the item only reads and writes through a ConfigData) -----------------------

    def is_enabled(self, data: ConfigData) -> bool:
        """This item's own switch, ignoring its ancestors."""
        return data.get(self)

    def is_effective(self, data: ConfigData) -> bool:
        """On, and every ancestor is on too."""
        return self.is_enabled(data) and all(a.is_enabled(data) for a in self.ancestors())

    def state(self, data: ConfigData) -> str:
        """``off`` if the item or an ancestor is off; ``mixed`` if something below is off."""
        if not self.is_effective(data):
            return "off"
        if any(not d.is_effective(data) for d in self.descendants()):
            return "mixed"
        return "on"

    def cascade(self, data: ConfigData, value: bool) -> None:
        """Apply ``value`` to this item and everything under it."""
        for node in self.walk():
            data.set(node, value)

    def select(self, data: ConfigData) -> None:
        """Pick this item: its whole subtree on, and its ancestors on so it can take effect."""
        self.cascade(data, True)
        for ancestor in self.ancestors():
            data.set(ancestor, True)

    def __repr__(self) -> str:
        return f"ConfigItem({self.path!r})"


@dataclass
class ConfigData:
    """The saved part: one stored bool per item path. Missing paths fall back to the default."""

    collection: ConfigCollection
    values: dict[str, bool] = field(default_factory=dict)

    def get(self, item: ConfigItem | str) -> bool:
        node = self.collection[item] if isinstance(item, str) else item
        return self.values.get(node.path, self.collection.default_for(node))

    def set(self, item: ConfigItem | str, value: bool) -> None:
        node = self.collection[item] if isinstance(item, str) else item
        self.values[node.path] = bool(value)

    def copy(self) -> ConfigData:
        return ConfigData(self.collection, dict(self.values))

    def to_dict(self) -> dict[str, bool]:
        """The saved form: only what differs from the defaults."""
        return {
            path: value
            for path, value in sorted(self.values.items())
            if value != self.collection.default_for(self.collection[path])
        }

    @classmethod
    def from_dict(cls, collection: ConfigCollection, saved: dict[str, Any]) -> ConfigData:
        """Rebuild from a saved table. Paths the tree no longer has are ignored (old saves)."""
        data = cls(collection)
        for path, value in saved.items():
            if path in collection and isinstance(value, bool):
                data.values[path] = value
        return data


class ConfigCollection:
    """The whole tree. A named holder for the sections, with lookups across all of them."""

    def __init__(
        self,
        sections: list[ConfigItem],
        root: ConfigItem,
        not_in_tree: dict[str, str] | None = None,
    ) -> None:
        self.root = root
        self.sections = sections
        self._defaults: dict[str, bool] = {}
        self.not_in_tree = not_in_tree or {}
        self._by_path: dict[str, ConfigItem] = {}
        self._by_setting: dict[str, ConfigItem] = {}
        for item in self.items():
            if item.path in self._by_path:
                raise ValueError(f"duplicate path {item.path}")
            self._by_path[item.path] = item
            for key in item.settings:
                if key in self._by_setting:
                    raise ValueError(
                        f"setting {key} is on both {self._by_setting[key].path} and {item.path}"
                    )
                self._by_setting[key] = item

    # ---- loading ---------------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path = DEFAULT_TREE) -> ConfigCollection:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        root = ConfigItem("root", "All settings", is_root=True)  # hidden: never part of a path

        def build(raw: dict[str, Any], parent: ConfigItem, domain: str) -> ConfigItem:
            item = ConfigItem(
                raw["id"],
                raw.get("label", raw["id"]),
                kind=raw.get("kind", "item"),
                domain=raw.get("domain", domain),
                settings=tuple(raw.get("settings", ())),
                topics=tuple(raw.get("topics", ())),
                description=raw.get("description", ""),
                parent=parent,
            )
            for child in raw.get("children", ()):
                build(child, item, item.domain)
            return item

        sections = [build(raw, root, "content") for raw in document["sections"]]
        return cls(sections, root, document.get("not_in_tree"))

    # ---- lookups ---------------------------------------------------------------------------

    def items(self) -> Iterator[ConfigItem]:
        """Every item, depth first, in tree order."""
        for section in self.sections:
            yield from section.walk()

    def __getitem__(self, path: str) -> ConfigItem:
        try:
            return self._by_path[path]
        except KeyError:
            raise KeyError(f"no config item {path!r}") from None

    def __contains__(self, path: object) -> bool:
        return path in self._by_path

    def __len__(self) -> int:
        return len(self._by_path)

    def by_setting(self, key: str) -> ConfigItem | None:
        """The item that replaces a legacy setting key."""
        return self._by_setting.get(key)

    def settings(self) -> set[str]:
        return set(self._by_setting)

    def topics(self) -> set[str]:
        """Top-level export topics that some item feeds (``stats.advanced`` counts as ``stats``)."""
        return {t.split(".")[0] for item in self.items() for t in item.topics}

    def items_for_topic(self, topic: str) -> list[ConfigItem]:
        return [i for i in self.items() if any(t.split(".")[0] == topic for t in i.topics)]

    # ---- defaults and migration ------------------------------------------------------------

    def default_for(self, item: ConfigItem) -> bool:
        return self._defaults.get(item.path, True)

    def with_defaults(self, legacy_defaults: dict[str, Any]) -> ConfigCollection:
        """Set every item's default from the add-on's legacy defaults (Defaults.lua)."""
        self._defaults = dict(self.values_from_legacy(legacy_defaults))
        return self

    def values_from_legacy(self, settings: dict[str, Any]) -> dict[str, bool]:
        """Map the old flat settings table onto the tree.

        An item with a legacy setting takes that value. An item without one but with children is
        on if any child is. A leaf without one follows the nearest ancestor that has a setting.
        """
        values: dict[str, bool] = {}

        def resolve(item: ConfigItem, inherited: bool) -> bool:
            key = item.setting
            if key is not None and key in settings:
                own: bool | None = bool(settings[key])
            else:
                own = None
            basis = own if own is not None else inherited
            child_values = [resolve(child, basis) for child in item.children]
            if own is None and child_values:
                own = any(child_values)
            values[item.path] = basis if own is None else own
            return values[item.path]

        for section in self.sections:
            resolve(section, True)
        return values

    def data_from_legacy(self, settings: dict[str, Any]) -> ConfigData:
        return ConfigData(self, self.values_from_legacy(settings))

    def legacy_settings(self, data: ConfigData) -> dict[str, bool]:
        """The old flat flags for the current choices, so code that still reads them keeps working.

        Uses the effective value: an item below an off ancestor is off.
        """
        flags: dict[str, bool] = {}
        for item in self.items():
            for key in item.settings:
                flags[key] = item.is_effective(data)
        return flags

    # ---- selection by path -----------------------------------------------------------------

    def from_paths(self, paths: list[str]) -> ConfigData:
        """Everything off except the given items (each with its subtree) and their ancestors."""
        data = ConfigData(self, {item.path: False for item in self.items()})
        for path in paths:
            self[path].select(data)
        return data

    def selected_paths(self, data: ConfigData) -> list[str]:
        """The shortest list of paths that ``from_paths`` turns back into the same selection."""
        found: list[str] = []

        def visit(item: ConfigItem) -> None:
            state = item.state(data)
            if state == "on":
                found.append(item.path)
            elif state == "mixed":
                for child in item.children:
                    visit(child)

        for section in self.sections:
            visit(section)
        return found

    def topics_for(self, data: ConfigData, domain: str | None = "content") -> set[str]:
        """Top-level export topics fed by at least one effective item."""
        return {
            t.split(".")[0]
            for item in self.items()
            if (domain is None or item.domain == domain) and item.is_effective(data)
            for t in item.topics
        }

    # ---- display ---------------------------------------------------------------------------

    def render(self, data: ConfigData | None = None) -> str:
        """Indented text view; with data, each line shows on/off/mixed."""
        marks = {"on": "[x]", "mixed": "[-]", "off": "[ ]"}
        lines = []
        for item in self.items():
            mark = marks[item.state(data)] + " " if data else ""
            note = "  (detail)" if item.kind == "detail" else ""
            lines.append(f"{'  ' * item.depth}{mark}{item.id}: {item.label}{note}")
        return "\n".join(lines)

    def mapping_table(self) -> str:
        """Markdown table of every item: its legacy setting, default and the topics it feeds."""
        rows = [
            "| Path | Label | Kind | Legacy setting | Default | Export topics |",
            "|---|---|---|---|---|---|",
        ]
        for item in self.items():
            setting = ", ".join(f"`{s}`" for s in item.settings)
            topics = ", ".join(f"`{t}`" for t in item.topics)
            default = "on" if self.default_for(item) else "off"
            rows.append(
                f"| `{item.path}` | {item.label} | {item.kind} | {setting} | {default} | {topics} |"
            )
        return "\n".join(rows)
