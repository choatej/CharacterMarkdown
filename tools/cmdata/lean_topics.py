"""Compact Markdown sections for the topics beyond the build itself.

Each function takes a ``CharacterExport`` and returns lines of text (empty when the topic was not
collected). The rules for text meant for an AI apply here too: names and counts only, no game ids,
no unnamed enum numbers, no links or emoji.
"""

from __future__ import annotations

import re

from .export import CharacterExport
from .topics import Counted
from .util import fmt_duration as _duration
from .util import fmt_number as _n

# currencies whose key is not a readable name
_CURRENCY_NAMES = {"ap": "Alliance Points", "telvar": "Tel Var Stones"}


def _words(key: str) -> str:
    """'archivalFortunes' -> 'Archival Fortunes'."""
    if key in _CURRENCY_NAMES:
        return _CURRENCY_NAMES[key]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key).title()


def _join(segments: list[str | None]) -> str:
    return " | ".join(s for s in segments if s)


def progression(export: CharacterExport) -> list[str]:
    p = export.progression
    if p is None:
        return []
    points = [
        f"skill {_n(p.unspent_skill_points)}" if p.unspent_skill_points else None,
        f"attribute {_n(p.unspent_attribute_points)}" if p.unspent_attribute_points else None,
        f"champion {_n(p.unspent_champion_points)}" if p.unspent_champion_points else None,
    ]
    unspent = ", ".join(x for x in points if x)
    return [
        "",
        "## Progression",
        _join(
            [
                f"Unspent points: {unspent}" if unspent else "No unspent points",
                f"Vampire: {p.vampire_status} (stage {p.vampire_stage})"
                if p.vampire_status and p.vampire_status != "never"
                else None,
                f"Werewolf: {p.werewolf_status} (stage {p.werewolf_stage})"
                if p.werewolf_status and p.werewolf_status != "never"
                else None,
            ]
        ),
    ]


def skill_lines(export: CharacterExport) -> list[str]:
    s = export.skill_lines
    if s is None or not s.lines:
        return []
    header = _join(
        [
            f"{s.maxed} maxed" if s.maxed is not None else None,
            f"{s.in_progress} in progress" if s.in_progress is not None else None,
            f"{s.early_progress} just started" if s.early_progress else None,
            f"{s.completion_percent}% complete" if s.completion_percent is not None else None,
        ]
    )
    lines = ["", "## Skill lines", header]
    unfinished = [line for line in s.lines if line.status != "maxed"]
    for line in unfinished:
        progress = f", {line.progress_percent}%" if line.progress_percent is not None else ""
        lines.append(f"- {line.name} (rank {_n(line.rank)}{progress})")
    morph_skills = export.skill_morphs.skills if export.skill_morphs else []
    awaiting = [m.name for m in morph_skills if m.awaiting_choice]
    if awaiting:
        lines.append("Morph choice waiting: " + ", ".join(awaiting))
    return lines


def antiquities(export: CharacterExport) -> list[str]:
    a = export.antiquities
    if a is None:
        return []
    leads = a.leads()
    lines = [
        "",
        "## Antiquities",
        _join(
            [
                f"{_n(a.discovered)}/{_n(a.total)} discovered",
                f"{_n(a.sets_completed)}/{_n(a.sets_total)} sets complete",
                f"{len(leads)} active leads",
            ]
        ),
    ]
    soon = a.leads_expiring_within()
    if soon:
        lines.append("Leads expiring within 7 days:")
        lines += [f"- {lead.name} ({_duration(lead.lead_seconds_remaining)})" for lead in soon]
    else:
        lines.append("No leads expire within 7 days.")
    later = [lead for lead in leads if lead not in soon and lead.lead_seconds_remaining]
    if later:
        nxt = ", ".join(
            f"{lead.name} ({_duration(lead.lead_seconds_remaining)})" for lead in later[:5]
        )
        lines.append(f"Next to expire after that: {nxt}")
    return lines


def crafting(export: CharacterExport) -> list[str]:
    c = export.crafting
    if c is None:
        return []
    recipe_lists = len(c.recipe_counts())
    lines = [
        "",
        "## Crafting",
        _join(
            [
                f"Motifs {c.motifs_completed()}/{len(c.motifs)} complete" if c.motifs else None,
                f"{_n(len(c.recipes))} recipes in {recipe_lists} lists" if c.recipes else None,
                f"{len(c.known_styles)} crafting styles known" if c.known_styles else None,
            ]
        ),
    ]
    gaps = c.research_gaps()
    if gaps:
        lines.append("Research still to do:")
        lines += [
            f"- {line}: {item.name} ({item.traits_known}/{item.traits_total} traits)"
            for line, item in gaps
        ]
    elif c.research:
        lines.append("Trait research complete on every crafting line.")
    if c.incomplete_item_sets:
        closest = sorted(c.incomplete_item_sets, key=lambda s: -(s.percent or 0))[:8]
        sets = ", ".join(f"{s.name} {s.percent}%" for s in closest)
        total = c.item_sets_incomplete_count or len(c.incomplete_item_sets)
        lines.append(f"Item set collection, {total} incomplete (closest first): {sets}")
    return lines


def inventory(export: CharacterExport) -> list[str]:
    i = export.inventory
    if i is None:
        return []
    return [
        "",
        "## Inventory",
        _join(
            [
                f"Backpack {_n(i.backpack_used)}/{_n(i.backpack_max)}",
                f"Bank {_n(i.bank_used)}/{_n(i.bank_max)}",
                f"Crafting bag {_n(len(i.crafting_bag_items))} stacks"
                if i.has_crafting_bag
                else None,
            ]
        ),
    ]


def collectibles(export: CharacterExport) -> list[str]:
    c = export.collectibles
    if c is None or not c.groups:
        return []
    owned = [
        f"{_words(kind)} {_n(group.owned)}/{_n(group.total)}"
        for kind, group in sorted(c.groups.items())
        if group.owned
    ]
    return ["", "## Collectibles", _join(owned)] if owned else []


def world(export: CharacterExport) -> list[str]:
    w = export.world_progress
    if w is None:
        return []

    def count(label: str, value: Counted | None) -> str | None:
        if value is None:
            return None
        return f"{label} {_n(value.collected)}/{_n(value.total)}"

    line = _join(
        [
            count("Skyshards", w.skyshards),
            count("Lorebooks", w.lorebooks),
            count("Delves", w.delves),
            count("Public dungeons", w.public_dungeons),
            f"Cadwell: {w.cadwell_level}" if w.cadwell_level else None,
        ]
    )
    return ["", "## World progress", line] if line else []


def quests(export: CharacterExport) -> list[str]:
    q = export.quests
    if q is None or not q.active:
        return []
    lines = ["", f"## Active quests ({len(q.active)})"]
    for quest in q.active:
        where = f" ({quest.zone})" if quest.zone else ""
        lines.append(f"- {quest.name}{where}")
    return lines


def achievements(export: CharacterExport) -> list[str]:
    a = export.achievements
    if a is None:
        return []
    lines = [
        "",
        "## Achievements",
        _join(
            [
                f"{_n(a.points)}/{_n(a.total_points)} points",
                f"{a.completion_percent}% complete" if a.completion_percent is not None else None,
            ]
        ),
    ]
    if a.recent:
        lines.append("Recently completed: " + ", ".join(r.name for r in a.recent))
    return lines


def currency(export: CharacterExport) -> list[str]:
    c = export.currency
    if c is None:
        return []
    shown = [
        f"{_words(key)} {_n(value)}" + (f"/{_n(c.caps[key])}" if c.caps.get(key) else "")
        for key, value in c.amounts.items()
        if value
    ]
    return ["", "## Currency", _join(shown)] if shown else []


def profile(export: CharacterExport) -> list[str]:
    e = export
    where = None
    if e.location and e.location.zone:
        where = e.location.zone + (f" ({e.location.subzone})" if e.location.subzone else "")
    rows = [
        _join(
            [
                f"Location: {where}" if where else None,
                "Riding maxed" if e.riding and e.riding.maxed_out else None,
            ]
        ),
        _join(
            [
                f"Mount: {e.appearance.mount}" if e.appearance and e.appearance.mount else None,
                f"Pet: {e.appearance.pet}" if e.appearance and e.appearance.pet else None,
                f"Outfit: {e.appearance.outfit}" if e.appearance and e.appearance.outfit else None,
            ]
        ),
        f"Buffs: {', '.join(e.buffs)}" if e.buffs else "",
        f"Guilds: {', '.join(g.name for g in e.guilds)}" if e.guilds else "",
        _join(
            [
                f"PvP rank: {e.pvp.rank_name}" if e.pvp and e.pvp.rank_name else None,
                f"Companion: {e.companion.active_name}"
                if e.companion and e.companion.active_name
                else None,
            ]
        ),
    ]
    rows = [r for r in rows if r]
    return ["", "## Profile", *rows] if rows else []


def armory(export: CharacterExport) -> list[str]:
    if not export.armory_builds:
        return []
    lines = ["", "## Armory builds"]
    for build in export.armory_builds:
        sets = ", ".join(f"{s.name} x{s.pieces_worn}" for s in build.sets)
        details = _join(
            [
                sets or None,
                f"Mundus {build.mundus}" if build.mundus else None,
                f"{build.curse}" if build.curse else None,
            ]
        )
        lines.append(f"- {build.name}: {details}" if details else f"- {build.name}")
    return lines


# name -> function; the order here is the order sections appear in the output
EXTRA_SECTIONS = {
    "progression": progression,
    "skill_lines": skill_lines,
    "antiquities": antiquities,
    "crafting": crafting,
    "inventory": inventory,
    "collectibles": collectibles,
    "world": world,
    "quests": quests,
    "achievements": achievements,
    "currency": currency,
    "profile": profile,
    "armory": armory,
}
