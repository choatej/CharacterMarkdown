"""Crafting: motifs, recipes, trait research and item-set collection progress.

Shrinks what the export repeats or spells out in full:
- a motif lists only its *missing* chapters (its known chapters are implied by the counts)
- each recipe appears once, with the name of the recipe list it belongs to (the export has the same
  recipes both flat and grouped by list)
- trait research is kept as known / total counts per item type; the trait ids of the unknown ones
  stay available for tools
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .util import as_dict, number, records


def _known_count(chapters: list[dict[str, Any]]) -> int:
    return sum(1 for chapter in chapters if chapter.get("known"))


@dataclass
class Motif:
    name: str
    chapters_known: int
    chapters_total: int
    completed: bool
    missing_chapters: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Motif:
        chapters = records(raw.get("chapters"))
        known = raw.get("numKnown")
        total = raw.get("total")
        return cls(
            name=str(raw.get("name", "")),
            chapters_known=known if isinstance(known, int) else _known_count(chapters),
            chapters_total=total if isinstance(total, int) else len(chapters),
            completed=bool(raw.get("isCompleted")),
            missing_chapters=[str(c.get("name", "")) for c in chapters if not c.get("known")],
        )


@dataclass
class Recipe:
    name: str
    # the recipe list it appears under (e.g. "Dining"); None when it is in no list
    recipe_list: str | None = None
    # numeric tool-only values; the list name already says what kind of recipe it is
    craft_type: int | None = None
    quality: int | None = None
    result_id: int | None = None


@dataclass
class ResearchItem:
    name: str
    traits_known: int
    traits_total: int
    seconds_required: int | None = None
    # ids of the traits not yet researched (numbers are for tools; the export has no names for them)
    missing_trait_ids: list[int] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.traits_known >= self.traits_total


@dataclass
class ItemSetProgress:
    id: int | None
    name: str
    unlocked: int | None = None
    total: int | None = None
    percent: int | None = None


@dataclass
class Crafting:
    motifs: list[Motif] = field(default_factory=list)
    recipes: list[Recipe] = field(default_factory=list)
    # crafting line (blacksmithing, clothing, ...) -> its item types
    research: dict[str, list[ResearchItem]] = field(default_factory=dict)
    research_percent: dict[str, int] = field(default_factory=dict)
    incomplete_item_sets: list[ItemSetProgress] = field(default_factory=list)
    item_sets_incomplete_count: int | None = None
    # names of the crafting styles the character knows
    known_styles: list[str] = field(default_factory=list)
    active_research_timers: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Crafting:
        recipes_raw = as_dict(raw.get("recipes"))
        list_of: dict[tuple[Any, Any], str] = {}
        for list_name, members in as_dict(recipes_raw.get("byList")).items():
            for member in records(members):
                list_of[(member.get("name"), member.get("resultId"))] = list_name
        recipes = [
            Recipe(
                name=str(r.get("name", "")),
                recipe_list=list_of.get((r.get("name"), r.get("resultId"))),
                craft_type=r.get("craftType"),
                quality=r.get("quality"),
                result_id=r.get("resultId"),
            )
            for r in records(recipes_raw.get("all"))
        ]

        research: dict[str, list[ResearchItem]] = {}
        for line, items in as_dict(raw.get("research")).items():
            research[line] = [
                ResearchItem(
                    name=str(item.get("name", "")),
                    traits_known=sum(1 for t in records(item.get("traits")) if t.get("known")),
                    traits_total=len(records(item.get("traits"))),
                    seconds_required=item.get("timeRequiredSecs"),
                    missing_trait_ids=[
                        t["id"]
                        for t in records(item.get("traits"))
                        if not t.get("known") and "id" in t
                    ],
                )
                for item in records(items)
            ]

        collection = as_dict(raw.get("itemSetCollection"))
        progress = as_dict(as_dict(raw.get("summary")).get("researchProgress"))
        return cls(
            motifs=[Motif.from_raw(m) for m in records(raw.get("motifs"))],
            recipes=recipes,
            research=research,
            research_percent={k: int(v) for k, v in progress.items() if number(v) is not None},
            incomplete_item_sets=[
                ItemSetProgress(
                    id=s.get("id"),
                    name=str(s.get("name", "")),
                    unlocked=s.get("unlocked"),
                    total=s.get("total"),
                    percent=s.get("percent"),
                )
                for s in records(collection.get("incomplete"))
            ],
            item_sets_incomplete_count=collection.get("count"),
            known_styles=[
                str(s.get("name", "")) for s in records(as_dict(raw.get("styles")).get("list"))
            ],
            active_research_timers=as_dict(raw.get("summary")).get("activeTimers"),
        )

    def motifs_completed(self) -> int:
        return sum(1 for m in self.motifs if m.completed)

    def recipe_counts(self) -> dict[str, int]:
        """Recipes per list name (recipes in no list are counted under ``"(no list)"``)."""
        counts: dict[str, int] = {}
        for recipe in self.recipes:
            key = recipe.recipe_list or "(no list)"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def research_gaps(self) -> list[tuple[str, ResearchItem]]:
        """(crafting line, item type) pairs that still have traits to research."""
        return [
            (line, item)
            for line, items in self.research.items()
            for item in items
            if not item.complete
        ]
