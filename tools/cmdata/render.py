"""Output formats for a CharacterExport.

``to_dict`` / ``to_json`` give the full structured form. ``to_lean_markdown`` gives a compact
text form without links, HTML, badges or emoji, meant to be read by a person or a language model.
Add another format by writing another function that takes a ``CharacterExport``.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .model import CharacterExport

# --------------------------------------------------------------------------- dict / JSON


def _prune(value: Any) -> Any:
    """Drop ``None`` values and empty containers (keeps ``0`` and ``False``)."""
    if isinstance(value, dict):
        pruned = {k: _prune(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if v is not None and v != {} and v != []}
    if isinstance(value, list):
        return [_prune(v) for v in value]
    return value


def to_dict(export: CharacterExport, *, include_extra: bool = True, prune: bool = True) -> dict:
    """The export as plain dicts and lists.

    ``include_extra`` keeps the topics that have no typed model; ``prune`` removes ``None`` values
    and empty containers so the result is compact.
    """
    result = asdict(export)
    if not include_extra:
        result.pop("extra", None)
    return _prune(result) if prune else result


def to_json(export: CharacterExport, *, include_extra: bool = True, indent: int | None = 2) -> str:
    return (
        json.dumps(to_dict(export, include_extra=include_extra), ensure_ascii=False, indent=indent)
        + "\n"
    )


# --------------------------------------------------------------------------- lean Markdown


def _n(value: Any) -> str:
    """Number with thousands separators; anything else as text; missing as '?'."""
    if isinstance(value, bool) or value is None:
        return "?"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.1f}".rstrip("0").rstrip(".")
    return str(value)


def _duration(seconds: int | None) -> str | None:
    if not isinstance(seconds, int) or seconds <= 0:
        return None
    days, rest = divmod(seconds, 86400)
    hours = rest // 3600
    return f"{days}d {hours}h" if days else f"{hours}h"


def _identity_lines(export: CharacterExport) -> list[str]:
    c = export.character
    facts = [
        c.class_name,
        c.race,
        c.gender,
        f"Level {c.level}" if c.level else None,
        f"CP {_n(c.champion_points)}" if c.champion_points else None,
        c.alliance,
        c.server,
    ]
    lines = [f"# {c.name}", " | ".join(f for f in facts if f)]
    extras = [
        f"Title: {c.title}" if c.title else None,
        f"Played: {_duration(c.played_seconds)}" if _duration(c.played_seconds) else None,
        "ESO Plus" if c.eso_plus else None,
        f"Play style: {export.play_style.replace('_', ' ')}" if export.play_style else None,
    ]
    if any(extras):
        lines.append(" | ".join(e for e in extras if e))
    return lines


def _pair(label: str, first: Any, second: Any, suffix: str = "") -> str | None:
    """'Label a / b' when at least one value is known, otherwise nothing."""
    if first is None and second is None:
        return None
    return f"{label} {_n(first)}{suffix} / {_n(second)}{suffix}"


def _join(segments: list[str | None]) -> str:
    return " | ".join(seg for seg in segments if seg)


def _notes_lines(export: CharacterExport) -> list[str]:
    if not export.build_notes:
        return []
    return ["", "## Build notes", export.build_notes]


def _stats_lines(export: CharacterExport) -> list[str]:
    s = export.stats
    if s is None:
        return []
    resources = _join(
        [
            f"Health {_n(s.health)}" if s.health is not None else None,
            f"Magicka {_n(s.magicka)}" if s.magicka is not None else None,
            f"Stamina {_n(s.stamina)}" if s.stamina is not None else None,
        ]
    )
    offense = _join(
        [
            _pair("Weapon / spell power", s.weapon_power, s.spell_power),
            _pair("Crit chance", s.weapon_crit_chance, s.spell_crit_chance, "%"),
            f"Crit damage {_n(s.critical_damage)}%" if s.critical_damage is not None else None,
        ]
    )
    defense = _join(
        [
            _pair("Penetration", s.physical_penetration, s.spell_penetration),
            _pair("Resistance", s.physical_resistance, s.spell_resistance),
            _pair("Mitigation", s.physical_mitigation, s.spell_mitigation, "%"),
        ]
    )
    lines = [line for line in (resources, offense, defense) if line]
    if s.effective_health.get("average"):
        lines.append(f"Effective health {_n(s.effective_health['average'])}")
    if s.dps_estimate.get("average"):
        lines.append(f"DPS estimate {_n(s.dps_estimate['average'])}")
    return ["", "## Stats", *lines] if lines else []


def _gear_lines(export: CharacterExport) -> list[str]:
    eq = export.equipment
    if eq is None or not eq.items:
        return []
    lines = ["", "## Gear"]
    for item in eq.items:
        details = [
            item.set_name,
            item.quality,
            item.trait,
            f"{item.armor_weight} armor" if item.armor_weight else None,
            # leave it out when the item name already says it ("Dagger of Julianos")
            item.weapon_name
            if item.weapon_name and item.weapon_name not in item.name.lower()
            else None,
            item.enchantment,
        ]
        shown = ", ".join(d for d in details if d)
        lines.append(f"- {item.slot}: {item.name}" + (f" ({shown})" if shown else ""))
    if eq.trait_counts:
        traits = ", ".join(f"{k} {v}" for k, v in sorted(eq.trait_counts.items()))
        lines.append(f"Traits: {traits}")
    if not eq.sets:
        return lines
    lines += ["", "## Sets"]
    for active in eq.sets:
        count = active.pieces_worn
        worn = f" ({count} piece{'' if count == 1 else 's'})" if count is not None else ""
        lines.append(f"- {active.name}{worn}")
        for bonus in active.bonuses:
            state = "" if bonus.active in (True, None) else " (inactive)"
            lines.append(f"  - {bonus.text}{state}")
    return lines


def _skill_lines(export: CharacterExport) -> list[str]:
    bars = export.skill_bars
    if bars is None or not bars.bars:
        return []
    lines = ["", "## Skill bars"]
    for bar in bars.bars:
        abilities = [a.name for a in sorted(bar.abilities, key=lambda a: a.slot or 0)]
        ultimate = f" | Ultimate: {bar.ultimate.name}" if bar.ultimate else ""
        lines.append(f"- {bar.name}: {' | '.join(abilities)}{ultimate}")
    return lines


def _cp_lines(export: CharacterExport) -> list[str]:
    cp = export.champion_points
    if cp is None or not cp.disciplines:
        return []
    lines = [
        "",
        "## Champion points",
        f"Total {_n(cp.total)} (spent {_n(cp.spent)}, unspent {_n(cp.unspent)})",
    ]
    for disc in cp.disciplines:
        stars = [
            f"{s.name} {s.points}" + ("*" if s.slottable else "")
            for s in sorted(disc.stars, key=lambda s: -s.points)
            if s.points
        ]
        lines.append(f"- {disc.name} ({_n(disc.points_spent)}): {', '.join(stars) or 'none'}")
    if any(s.slottable for d in cp.disciplines for s in d.stars):
        lines.append("(* = slottable star)")
    return lines


def to_lean_markdown(export: CharacterExport) -> str:
    """Compact text for the modelled topics. Topics without a model are not included."""
    lines = (
        _identity_lines(export)
        + _notes_lines(export)
        + _stats_lines(export)
        + _gear_lines(export)
        + _skill_lines(export)
        + _cp_lines(export)
    )
    return "\n".join(lines) + "\n"


FORMATS = {
    "json": to_json,
    "md": to_lean_markdown,
}
