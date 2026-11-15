"""Typed model of a ``/cm save data`` export.

Only the topics that matter for build analysis are modelled (character, stats, equipment, skill
bars, champion points). Everything else the game collected is kept untouched in
``CharacterExport.extra`` so nothing is lost.

Every ``from_raw`` is tolerant of missing keys: a missing value becomes ``None`` / empty rather
than an error, because which topics are present depends on the user's settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .clean import none_if_blank, single_line, strip_decoration, strip_markup
from .util import get as _get

# Armor weight values used by the game (seen in real exports: gloves of a light set are 1, a medium
# crafted helm is 2). Other enum values (weapon type, bind type, style) stay numeric on purpose:
# their names are not stored in the export and guessing them risks being wrong.
ARMOR_TYPES = {0: "none", 1: "light", 2: "medium", 3: "heavy"}

# Weapon type values confirmed against real exports (a dagger is 11, a lightning staff is 15). The
# other values are left out until they have been seen with an item name to check them against; an
# unknown number stays numeric in the JSON and is left out of the Markdown (the item name says it).
WEAPON_TYPES = {11: "dagger", 15: "lightning staff"}


# --------------------------------------------------------------------------- character


@dataclass
class ClassSkillLine:
    name: str
    rank: int | None = None


@dataclass
class Character:
    name: str
    account: str | None = None
    server: str | None = None
    class_name: str | None = None
    race: str | None = None
    gender: str | None = None
    alliance: str | None = None
    level: int | None = None
    champion_points: int | None = None
    title: str | None = None
    eso_plus: bool | None = None
    # points put into each attribute
    attributes: dict[str, int] = field(default_factory=dict)
    played_seconds: int | None = None
    class_skill_lines: list[ClassSkillLine] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Character:
        lines = [
            ClassSkillLine(name=str(line.get("name", "")), rank=line.get("rank"))
            for line in _get(raw, "subclass", "native", default=[]) or []
            if isinstance(line, dict)
        ]
        attributes = _get(raw, "attributes", default={}) or {}
        return cls(
            name=str(raw.get("name", "Unknown")),
            account=none_if_blank(raw.get("account")),
            server=none_if_blank(raw.get("server")),
            class_name=none_if_blank(raw.get("class")),
            race=none_if_blank(raw.get("race")),
            gender=none_if_blank(raw.get("gender")),
            alliance=none_if_blank(raw.get("alliance")),
            level=raw.get("level"),
            champion_points=raw.get("cp"),
            title=none_if_blank(raw.get("title")),
            eso_plus=raw.get("esoPlus"),
            attributes={k: v for k, v in attributes.items() if isinstance(v, int | float)},
            played_seconds=_get(raw, "ageMetrics", "seconds"),
            class_skill_lines=lines,
        )


# --------------------------------------------------------------------------- stats


@dataclass
class Stats:
    health: int | None = None
    magicka: int | None = None
    stamina: int | None = None
    health_recovery: int | None = None
    magicka_recovery: int | None = None
    stamina_recovery: int | None = None
    weapon_power: int | None = None
    spell_power: int | None = None
    weapon_crit_chance: float | None = None
    spell_crit_chance: float | None = None
    critical_damage: float | None = None
    physical_penetration: int | None = None
    spell_penetration: int | None = None
    physical_resistance: int | None = None
    spell_resistance: int | None = None
    physical_mitigation: float | None = None
    spell_mitigation: float | None = None
    effective_health: dict[str, int] = field(default_factory=dict)
    dps_estimate: dict[str, int] = field(default_factory=dict)
    # the detailed block (damage and resistances by type, utility, ...) as the game gave it
    advanced: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Stats:
        return cls(
            health=raw.get("health"),
            magicka=raw.get("magicka"),
            stamina=raw.get("stamina"),
            health_recovery=raw.get("healthRecovery"),
            magicka_recovery=raw.get("magickaRecovery"),
            stamina_recovery=raw.get("staminaRecovery"),
            weapon_power=raw.get("weaponPower"),
            spell_power=raw.get("spellPower"),
            weapon_crit_chance=raw.get("weaponCritChance"),
            spell_crit_chance=raw.get("spellCritChance"),
            critical_damage=_get(raw, "advanced", "damage", "criticalDamage"),
            physical_penetration=raw.get("physicalPenetration"),
            spell_penetration=raw.get("spellPenetration"),
            physical_resistance=raw.get("physicalResist"),
            spell_resistance=raw.get("spellResist"),
            physical_mitigation=raw.get("physicalMitigation"),
            spell_mitigation=raw.get("spellMitigation"),
            effective_health=dict(raw.get("effectiveHealth") or {}),
            dps_estimate=dict(raw.get("dpsEstimates") or {}),
            advanced=dict(raw.get("advanced") or {}),
        )


# --------------------------------------------------------------------------- equipment


@dataclass
class EquippedItem:
    slot: str
    slot_index: int | None
    name: str
    set_name: str | None = None
    quality: str | None = None
    quality_level: int | None = None
    trait: str | None = None
    enchantment: str | None = None
    armor_weight: str | None = None
    armor_type: int | None = None
    weapon_name: str | None = None
    weapon_type: int | None = None
    bind_type: int | None = None
    style: int | None = None
    is_crafted: bool | None = None
    required_level: int | None = None
    required_champion_points: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> EquippedItem:
        armor = raw.get("armorType")
        weapon = raw.get("weaponType") or None
        return cls(
            slot=str(raw.get("slotName", "")),
            slot_index=raw.get("slotIndex"),
            name=str(raw.get("name", "")),
            set_name=none_if_blank(raw.get("setName")),
            quality=none_if_blank(raw.get("quality")),
            quality_level=raw.get("qualityNumeric"),
            trait=none_if_blank(raw.get("trait")),
            enchantment=none_if_blank(raw.get("enchantment")),
            armor_weight=ARMOR_TYPES.get(armor) if isinstance(armor, int) and armor else None,
            armor_type=armor,
            weapon_name=WEAPON_TYPES.get(weapon) if isinstance(weapon, int) else None,
            weapon_type=weapon,
            bind_type=raw.get("bindType"),
            style=raw.get("style") or None,
            is_crafted=raw.get("isCrafted"),
            required_level=raw.get("requiredLevel"),
            required_champion_points=raw.get("requiredCP") or None,
        )


@dataclass
class SetBonus:
    pieces_required: int | None
    text: str
    active: bool | None = None


@dataclass
class ActiveSet:
    name: str
    pieces_worn: int | None = None
    bonuses: list[SetBonus] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ActiveSet:
        bonuses = [
            SetBonus(
                pieces_required=bonus.get("numRequired"),
                text=single_line(strip_markup(str(bonus.get("description", "")))),
                active=bonus.get("isActive"),
            )
            for bonus in raw.get("bonuses") or []
            if isinstance(bonus, dict)
        ]
        return cls(name=str(raw.get("name", "")), pieces_worn=raw.get("count"), bonuses=bonuses)


@dataclass
class Equipment:
    items: list[EquippedItem] = field(default_factory=list)
    sets: list[ActiveSet] = field(default_factory=list)
    trait_counts: dict[str, int] = field(default_factory=dict)
    gear_score: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Equipment:
        items = [
            EquippedItem.from_raw(item)
            for item in raw.get("items") or []
            if isinstance(item, dict) and not item.get("isEmpty")
        ]
        sets = [ActiveSet.from_raw(s) for s in raw.get("sets") or [] if isinstance(s, dict)]
        score = raw.get("gearScore")
        return cls(
            items=items,
            sets=sets,
            trait_counts=dict(raw.get("traitDistribution") or {}),
            gear_score=int(score) if str(score).isdigit() else None,
        )


# --------------------------------------------------------------------------- skill bars


@dataclass
class Ability:
    name: str
    ability_id: int | None = None
    slot: int | None = None
    is_ultimate: bool = False
    is_crafted: bool = False


@dataclass
class SkillBar:
    name: str
    abilities: list[Ability] = field(default_factory=list)
    ultimate: Ability | None = None


@dataclass
class SkillBars:
    active_bar: str | None = None
    bars: list[SkillBar] = field(default_factory=list)
    unspent_skill_points: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> SkillBars:
        bars = []
        for bar in raw.get("bars") or []:
            if not isinstance(bar, dict):
                continue
            abilities = [
                Ability(
                    name=str(a.get("name", "")),
                    ability_id=a.get("id"),
                    slot=a.get("slot"),
                    is_ultimate=bool(a.get("isUltimate")),
                    is_crafted=bool(a.get("isCrafted")),
                )
                for a in bar.get("abilities") or []
                if isinstance(a, dict)
            ]
            ultimate_name = none_if_blank(bar.get("ultimate"))
            ultimate = None
            if ultimate_name:
                ultimate = Ability(
                    name=ultimate_name,
                    ability_id=bar.get("ultimateId"),
                    is_ultimate=True,
                    is_crafted=bool(bar.get("ultimateIsCrafted")),
                )
            bars.append(
                SkillBar(
                    name=strip_decoration(str(bar.get("name", ""))),
                    abilities=abilities,
                    ultimate=ultimate,
                )
            )
        return cls(
            active_bar=none_if_blank(_get(raw, "activeWeaponPair", "label")),
            bars=bars,
            unspent_skill_points=_get(raw, "points", "unspent"),
        )


# --------------------------------------------------------------------------- champion points


@dataclass
class ChampionStar:
    name: str
    points: int
    max_points: int | None = None
    skill_id: int | None = None
    kind: str | None = None
    slottable: bool | None = None


@dataclass
class ChampionDiscipline:
    name: str
    points_spent: int | None = None
    points_available: int | None = None
    stars: list[ChampionStar] = field(default_factory=list)


@dataclass
class ChampionPoints:
    total: int | None = None
    spent: int | None = None
    unspent: int | None = None
    disciplines: list[ChampionDiscipline] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ChampionPoints:
        disciplines = []
        for disc in raw.get("disciplines") or []:
            if not isinstance(disc, dict):
                continue
            maxima = {
                s.get("skillId"): s.get("maxPoints")
                for s in disc.get("allStars") or []
                if isinstance(s, dict)
            }
            stars = [
                ChampionStar(
                    name=str(s.get("name", "")),
                    points=int(s.get("points") or 0),
                    max_points=maxima.get(s.get("skillId")),
                    skill_id=s.get("skillId"),
                    kind=none_if_blank(s.get("type")),
                    slottable=s.get("isSlottable"),
                )
                for s in disc.get("skills") or []
                if isinstance(s, dict)
            ]
            disciplines.append(
                ChampionDiscipline(
                    name=str(disc.get("name", "")),
                    points_spent=disc.get("spent"),
                    points_available=disc.get("available"),
                    stars=stars,
                )
            )
        return cls(
            total=raw.get("total"),
            spent=raw.get("spent"),
            unspent=raw.get("available"),
            disciplines=disciplines,
        )
