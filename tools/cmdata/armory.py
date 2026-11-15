"""Armory builds: saved loadouts (gear, skill bars, champion points, attributes, mundus)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .clean import none_if_blank, strip_decoration
from .model import Ability, ActiveSet, EquippedItem, SkillBar
from .util import as_dict, number, records

_EMPTY_NAMES = ("", "[Empty]", "[Empty Slot]")


def _numbers(value: Any) -> dict[str, int]:
    """The numeric entries of a dict (attribute points, points per champion discipline)."""
    return {k: v for k, v in as_dict(value).items() if number(v) is not None}


@dataclass
class ArmoryBuild:
    name: str
    index: int | None = None
    curse: str | None = None
    mundus: str | None = None
    skill_points: int | None = None
    attributes: dict[str, int] = field(default_factory=dict)
    # points per champion discipline (craft, fitness, warfare) and the total
    champion_points: dict[str, int] = field(default_factory=dict)
    equipment: list[EquippedItem] = field(default_factory=list)
    sets: list[ActiveSet] = field(default_factory=list)
    bars: list[SkillBar] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ArmoryBuild:
        bars = []
        for bar in records(raw.get("hotbars")):
            abilities = [
                Ability(
                    name=str(a.get("name", "")),
                    slot=a.get("slot"),
                    is_ultimate=bool(a.get("isUltimate")),
                )
                for a in records(bar.get("abilities"))
                if a.get("name") not in _EMPTY_NAMES
            ]
            name = strip_decoration(str(bar.get("name", "")))
            bars.append(SkillBar(name=name, abilities=abilities))
        return cls(
            name=str(raw.get("name", "")),
            index=raw.get("index"),
            curse=none_if_blank(raw.get("curse")),
            mundus=none_if_blank(as_dict(raw.get("mundus")).get("primary")),
            skill_points=raw.get("skillPoints"),
            attributes=_numbers(raw.get("attributes")),
            champion_points=_numbers(raw.get("champion")),
            equipment=[
                EquippedItem.from_raw(item)
                for item in records(raw.get("equipment"))
                if item.get("name") not in _EMPTY_NAMES
            ],
            sets=[
                ActiveSet(name=str(s.get("name", "")), pieces_worn=s.get("count"))
                for s in records(raw.get("sets"))
            ],
            bars=bars,
        )


def armory_builds_from_raw(raw: dict[str, Any]) -> list[ArmoryBuild]:
    return [ArmoryBuild.from_raw(b) for b in records(raw.get("builds"))]
