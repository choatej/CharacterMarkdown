"""Typed models for the remaining topics of a structured export.

Each class has a tolerant ``from_raw``: a missing key becomes ``None`` / empty, and an empty Lua
table (``{}``) is accepted wherever a list is expected. Numbers that are only game ids or enums
without a name in the export are kept for tools (they appear in the JSON) but never given an
invented name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .clean import none_if_blank, strip_markup
from .util import as_dict, get, number, records, strings

# Item quality names. 2 (fine), 3 (superior), 4 (epic) and 5 (legendary) were checked against real
# exports (items that carry both the name and the number); 0 and 1 follow the game's enumeration.
QUALITY_NAMES = {0: "trash", 1: "normal", 2: "fine", 3: "superior", 4: "epic", 5: "legendary"}


def quality_name(value: Any) -> str | None:
    return QUALITY_NAMES.get(value) if isinstance(value, int) else None


# --------------------------------------------------------------------------- progression


@dataclass
class Progression:
    achievement_points: int | None = None
    achievement_percent: int | None = None
    unspent_skill_points: int | None = None
    unspent_attribute_points: int | None = None
    unspent_champion_points: int | None = None
    vampire_status: str | None = None
    vampire_stage: int | None = None
    werewolf_status: str | None = None
    werewolf_stage: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Progression:
        return cls(
            achievement_points=raw.get("achievementPoints"),
            achievement_percent=raw.get("achievementPercent"),
            unspent_skill_points=raw.get("unspentSkillPoints"),
            unspent_attribute_points=raw.get("unspentAttributePoints"),
            unspent_champion_points=raw.get("availableChampionPoints"),
            vampire_status=none_if_blank(raw.get("vampireStatus")),
            vampire_stage=raw.get("vampireStage"),
            werewolf_status=none_if_blank(raw.get("werewolfStatus")),
            werewolf_stage=raw.get("werewolfStage"),
        )


# --------------------------------------------------------------------------- skills


@dataclass
class SkillPassive:
    name: str
    rank: int | None = None
    max_rank: int | None = None
    purchased: bool | None = None
    ability_id: int | None = None


@dataclass
class SkillLine:
    name: str
    rank: int | None = None
    # "maxed", "inProgress", ... as the export states it
    status: str | None = None
    progress_percent: int | None = None
    xp_current: int | None = None
    xp_next_rank: int | None = None
    passives: list[SkillPassive] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> SkillLine:
        xp = as_dict(raw.get("xp"))
        return cls(
            name=str(raw.get("name", "")),
            rank=raw.get("rank"),
            status=none_if_blank(raw.get("status")),
            progress_percent=raw.get("progress"),
            xp_current=xp.get("current"),
            xp_next_rank=xp.get("max"),
            passives=[
                SkillPassive(
                    name=str(p.get("name", "")),
                    rank=p.get("currentRank", p.get("rank")),
                    max_rank=p.get("maxRank"),
                    purchased=p.get("purchased"),
                    ability_id=p.get("abilityId"),
                )
                for p in records(raw.get("passives"))
            ],
        )


@dataclass
class SkillLines:
    lines: list[SkillLine] = field(default_factory=list)
    completion_percent: int | None = None
    maxed: int | None = None
    in_progress: int | None = None
    early_progress: int | None = None
    total_passives: int | None = None
    total_skills: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> SkillLines:
        summary = as_dict(raw.get("summary"))
        return cls(
            lines=[SkillLine.from_raw(line) for line in records(raw.get("lines"))],
            completion_percent=summary.get("completionPercent"),
            maxed=summary.get("maxedCount"),
            in_progress=summary.get("inProgressCount"),
            early_progress=summary.get("earlyProgressCount"),
            total_passives=summary.get("totalPassives"),
            total_skills=summary.get("totalSkills"),
        )


@dataclass
class MorphSkill:
    name: str
    skill_line: str
    skill_type: str
    purchased: bool | None = None
    ultimate: bool = False
    rank: int | None = None
    # the morph that is active (None when the skill is not morphed yet)
    chosen_morph: str | None = None
    morph_options: list[str] = field(default_factory=list)
    awaiting_choice: bool = False


@dataclass
class SkillMorphs:
    class_name: str | None = None
    skills: list[MorphSkill] = field(default_factory=list)
    chosen: int | None = None
    available: int | None = None
    total: int | None = None
    completion_percent: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> SkillMorphs:
        skills = []
        for skill_type in records(raw.get("skillTypes")):
            for line in records(skill_type.get("skillLines")):
                for ability in records(line.get("abilities")):
                    options = records(ability.get("morphs"))
                    chosen = next((m.get("name") for m in options if m.get("selected")), None)
                    skills.append(
                        MorphSkill(
                            name=str(ability.get("name", "")),
                            skill_line=str(line.get("name", "")),
                            skill_type=str(skill_type.get("name", "")),
                            purchased=ability.get("purchased"),
                            ultimate=bool(ability.get("ultimate")),
                            rank=ability.get("currentRank"),
                            chosen_morph=chosen,
                            morph_options=[str(m.get("name", "")) for m in options],
                            awaiting_choice=bool(ability.get("atMorphChoice")),
                        )
                    )
        summary = as_dict(raw.get("summary"))
        return cls(
            class_name=none_if_blank(raw.get("class")),
            skills=skills,
            chosen=summary.get("chosenMorphs"),
            available=summary.get("availableMorphs"),
            total=summary.get("totalMorphs"),
            completion_percent=summary.get("completionPercent"),
        )


# --------------------------------------------------------------------------- currency


@dataclass
class Currency:
    """Every currency by name (gold, transmute, telvar, ...) and its cap where the game has one."""

    amounts: dict[str, int | float] = field(default_factory=dict)
    caps: dict[str, int | float] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Currency:
        amounts: dict[str, int | float] = {}
        caps: dict[str, int | float] = {}
        for key, value in raw.items():
            if key == "summary" or number(value) is None:
                continue
            if key.endswith("Max") and len(key) > 3:
                caps[key[:-3]] = value
            else:
                amounts[key] = value
        return cls(amounts=amounts, caps=caps)

    @property
    def gold(self) -> int | float | None:
        return self.amounts.get("gold")


# --------------------------------------------------------------------------- inventory


@dataclass
class InventoryItem:
    name: str
    stack: int | None = None
    quality: int | None = None
    quality_name: str | None = None
    item_type: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> InventoryItem:
        return cls(
            name=str(raw.get("name", "")),
            stack=raw.get("stack"),
            quality=raw.get("quality"),
            quality_name=quality_name(raw.get("quality")),
            item_type=none_if_blank(raw.get("itemTypeName")),
        )


@dataclass
class Inventory:
    backpack_used: int | None = None
    backpack_max: int | None = None
    bank_used: int | None = None
    bank_max: int | None = None
    has_crafting_bag: bool | None = None
    backpack_items: list[InventoryItem] = field(default_factory=list)
    bank_items: list[InventoryItem] = field(default_factory=list)
    crafting_bag_items: list[InventoryItem] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Inventory:
        def items(key: str) -> list[InventoryItem]:
            return [InventoryItem.from_raw(i) for i in records(raw.get(key))]

        return cls(
            backpack_used=raw.get("backpackUsed"),
            backpack_max=raw.get("backpackMax"),
            bank_used=raw.get("bankUsed"),
            bank_max=raw.get("bankMax"),
            has_crafting_bag=raw.get("hasCraftingBag"),
            backpack_items=items("bagItems"),
            bank_items=items("bankItems"),
            crafting_bag_items=items("craftingBagItems"),
        )


# --------------------------------------------------------------------------- collectibles


@dataclass
class Collectible:
    id: int | None
    name: str
    nickname: str | None = None


@dataclass
class CollectibleGroup:
    owned: int
    total: int | None = None
    items: list[Collectible] = field(default_factory=list)


@dataclass
class Collectibles:
    """Owned collectibles by kind (mounts, pets, costumes, ...)."""

    groups: dict[str, CollectibleGroup] = field(default_factory=dict)
    eso_plus: bool | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Collectibles:
        groups = {}
        for kind, group in as_dict(raw.get("collections")).items():
            if not isinstance(group, dict):
                continue
            groups[kind] = CollectibleGroup(
                owned=group.get("count") or 0,
                total=group.get("total"),
                items=[
                    Collectible(
                        id=c.get("id"),
                        name=str(c.get("fullName") or c.get("name", "")),
                        nickname=none_if_blank(c.get("nickname")),
                    )
                    for c in records(group.get("list"))
                ],
            )
        return cls(groups=groups, eso_plus=raw.get("esoPlus"))


@dataclass
class OutfitStyles:
    count: int
    names: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> OutfitStyles:
        styles = records(get(raw, "categories", "all"))
        names = [str(s.get("fullName") or s.get("name", "")) for s in styles]
        return cls(count=raw.get("count") or len(names), names=names)


@dataclass
class Titles:
    current: str | None = None
    owned: list[str] = field(default_factory=list)
    available: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Titles:
        return cls(
            current=none_if_blank(raw.get("current")),
            owned=[str(t.get("name", "")) for t in records(raw.get("owned"))],
            available=get(raw, "summary", "totalAvailable"),
        )


@dataclass
class House:
    name: str
    nickname: str | None = None
    furniture_count: int | None = None
    listed_on_tours: bool | None = None


@dataclass
class Housing:
    owned: list[House] = field(default_factory=list)
    primary: House | None = None
    total_available: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Housing:
        primary = as_dict(raw.get("primary"))
        return cls(
            owned=[
                House(name=str(h.get("name", "")), nickname=none_if_blank(h.get("nickname")))
                for h in records(raw.get("owned"))
            ],
            primary=House(
                name=str(primary.get("name", "")),
                furniture_count=primary.get("furnitureCount"),
                listed_on_tours=primary.get("isListedOnTours"),
            )
            if primary
            else None,
            total_available=get(raw, "summary", "totalAvailable"),
        )


# --------------------------------------------------------------------------- quests


@dataclass
class QuestCondition:
    text: str
    current: int | None = None
    maximum: int | None = None
    complete: bool | None = None
    failed: bool | None = None


@dataclass
class Quest:
    name: str
    quest_type: str | None = None
    zone: str | None = None
    level: int | None = None
    step: str | None = None
    tracked: bool | None = None
    conditions: list[QuestCondition] = field(default_factory=list)


@dataclass
class Quests:
    active: list[Quest] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Quests:
        return cls(
            active=[
                Quest(
                    name=str(q.get("name", "")),
                    quest_type=none_if_blank(q.get("type")),
                    zone=none_if_blank(q.get("zone")),
                    level=q.get("level"),
                    step=none_if_blank(q.get("stepText") or q.get("activeStepText")),
                    tracked=q.get("isTracked"),
                    conditions=[
                        QuestCondition(
                            text=str(c.get("text", "")),
                            current=c.get("current"),
                            maximum=c.get("max"),
                            complete=c.get("isComplete"),
                            failed=c.get("isFail"),
                        )
                        for c in records(q.get("conditions"))
                    ],
                )
                for q in records(raw.get("active"))
            ]
        )


# --------------------------------------------------------------------------- world progress


@dataclass
class Counted:
    collected: int
    total: int | None = None


@dataclass
class WorldProgress:
    skyshards: Counted | None = None
    skyshards_by_zone: dict[str, Counted] = field(default_factory=dict)
    lorebooks: Counted | None = None
    lorebooks_by_category: dict[str, Counted] = field(default_factory=dict)
    delves: Counted | None = None
    public_dungeons: Counted | None = None
    cadwell_level: str | None = None
    cadwell_zones: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> WorldProgress:
        def counted(block: Any, done: str = "collected") -> Counted | None:
            block = as_dict(block)
            if done not in block:
                return None
            return Counted(collected=block.get(done) or 0, total=block.get("total"))

        skyshards = as_dict(raw.get("skyshards"))
        lorebooks = as_dict(raw.get("lorebooks"))
        dungeons = as_dict(raw.get("dungeons"))
        cadwell = as_dict(raw.get("cadwell"))
        return cls(
            skyshards=counted(skyshards),
            skyshards_by_zone={
                zone: Counted(collected=v.get("collected") or 0, total=v.get("total"))
                for zone, v in as_dict(skyshards.get("zones")).items()
                if isinstance(v, dict)
            },
            lorebooks=counted(lorebooks),
            lorebooks_by_category={
                name: Counted(collected=v.get("collected") or 0, total=v.get("total"))
                for name, v in as_dict(lorebooks.get("categories")).items()
                if isinstance(v, dict)
            },
            delves=counted(dungeons.get("delves"), "completed"),
            public_dungeons=counted(dungeons.get("publicDungeons"), "completed"),
            cadwell_level=none_if_blank(cadwell.get("levelName")),
            cadwell_zones=[str(z.get("name", "")) for z in records(cadwell.get("zones"))],
        )


# --------------------------------------------------------------------------- achievements


@dataclass
class AchievementCategory:
    name: str
    earned: int | None = None
    total: int | None = None
    percent: int | None = None


@dataclass
class RecentAchievement:
    name: str
    date: str | None = None
    time: str | None = None


@dataclass
class Achievements:
    """Achievement totals (per-achievement progress is the separate ``achievements`` export)."""

    points: int | None = None
    total_points: int | None = None
    completion_percent: int | None = None
    categories: list[AchievementCategory] = field(default_factory=list)
    recent: list[RecentAchievement] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Achievements:
        summary = as_dict(raw.get("summary"))
        return cls(
            points=raw.get("points", summary.get("earnedPoints")),
            total_points=raw.get("total", summary.get("totalPoints")),
            completion_percent=summary.get("completionPercent"),
            categories=[
                AchievementCategory(
                    name=str(c.get("name", "")),
                    earned=c.get("earned"),
                    total=c.get("total"),
                    percent=c.get("percent"),
                )
                for c in records(raw.get("categories"))
            ],
            recent=[
                RecentAchievement(
                    name=str(r.get("name", "")),
                    date=none_if_blank(r.get("date")),
                    time=none_if_blank(r.get("time")),
                )
                for r in records(raw.get("recent"))
            ],
        )


# --------------------------------------------------------------------------- companion, pvp, guilds


@dataclass
class CompanionItem:
    name: str
    slot: str | None = None
    quality: str | None = None
    level: int | None = None
    set_name: str | None = None
    trait: str | None = None


@dataclass
class Companion:
    active_name: str | None = None
    active_level: int | None = None
    rapport_level: int | None = None
    known_companions: list[str] = field(default_factory=list)
    equipment: list[CompanionItem] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    ultimate: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Companion:
        active = as_dict(raw.get("active"))
        skills = as_dict(raw.get("skills"))
        return cls(
            active_name=none_if_blank(active.get("name")),
            active_level=active.get("level"),
            rapport_level=raw.get("rapportLevel"),
            known_companions=[str(c.get("name", "")) for c in records(raw.get("companions"))],
            equipment=[
                CompanionItem(
                    name=str(i.get("name", "")),
                    slot=none_if_blank(i.get("slot")),
                    quality=none_if_blank(i.get("quality")),
                    level=i.get("level"),
                    set_name=none_if_blank(i.get("setName")),
                    trait=none_if_blank(strip_markup(str(i.get("traitName") or ""))),
                )
                for i in records(raw.get("equipment"))
            ],
            abilities=[str(a.get("name", "")) for a in records(skills.get("abilities"))],
            ultimate=none_if_blank(skills.get("ultimate")),
        )


@dataclass
class PvP:
    rank: int | None = None
    rank_name: str | None = None
    rank_points: int | None = None
    points_to_next_rank: int | None = None
    alliance: str | None = None
    campaign: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> PvP:
        basic = as_dict(raw.get("basic"))
        pvp = as_dict(get(raw, "stats", "pvp"))
        return cls(
            rank=basic.get("rank"),
            rank_name=none_if_blank(basic.get("rankName")),
            rank_points=basic.get("rankPoints"),
            points_to_next_rank=get(pvp, "progression", "pointsToNext"),
            alliance=none_if_blank(pvp.get("allianceName")),
            campaign=none_if_blank(basic.get("campaignName")),
        )


@dataclass
class Guild:
    name: str
    rank_name: str | None = None
    member_count: int | None = None
    alliance: str | None = None


def guilds_from_raw(raw: dict[str, Any]) -> list[Guild]:
    return [
        Guild(
            name=str(g.get("name", "")),
            rank_name=none_if_blank(g.get("rankName")),
            member_count=g.get("memberCount"),
            alliance=none_if_blank(get(g, "alliance", "name")),
        )
        for g in records(raw.get("list"))
    ]


# --------------------------------------------------------------------------- small topics


@dataclass
class Appearance:
    hat: str | None = None
    pet: str | None = None
    mount: str | None = None
    mount_skin: str | None = None
    outfit: str | None = None
    dyes_known: int | None = None
    dyes_total: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Appearance:
        return cls(
            hat=none_if_blank(get(raw, "active", "hat", "name")),
            pet=none_if_blank(get(raw, "active", "pet", "name")),
            mount=none_if_blank(get(raw, "mount", "name")),
            mount_skin=none_if_blank(get(raw, "mount", "skinName")),
            outfit=none_if_blank(get(raw, "outfit", "name")),
            dyes_known=get(raw, "dyes", "known"),
            dyes_total=get(raw, "dyes", "total"),
        )


@dataclass
class Location:
    zone: str | None = None
    subzone: str | None = None
    world: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Location:
        return cls(
            zone=none_if_blank(raw.get("zone")),
            subzone=none_if_blank(raw.get("subzone")),
            world=none_if_blank(raw.get("world")),
        )


@dataclass
class Riding:
    speed: int | None = None
    stamina: int | None = None
    capacity: int | None = None
    maxed_out: bool | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Riding:
        return cls(
            speed=raw.get("speed"),
            stamina=raw.get("stamina"),
            capacity=raw.get("capacity"),
            maxed_out=raw.get("maxedOut"),
        )


@dataclass
class Mundus:
    names: list[str] = field(default_factory=list)
    active: bool | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Mundus:
        single = [n for n in (raw.get("primary"), raw.get("name")) if isinstance(n, str)]
        names = strings(raw.get("names")) or single
        return cls(names=list(dict.fromkeys(names)), active=raw.get("active"))


@dataclass
class DlcAccess:
    accessible: list[str] = field(default_factory=list)
    locked: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> DlcAccess:
        return cls(accessible=strings(raw.get("accessible")), locked=strings(raw.get("locked")))


@dataclass
class Mail:
    total: int = 0
    unread: int = 0

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Mail:
        summary = as_dict(raw.get("summary"))
        return cls(total=summary.get("totalMail") or 0, unread=summary.get("unreadCount") or 0)


def undaunted_keys_from_raw(raw: dict[str, Any]) -> int | None:
    """Undaunted keys held (the pledge lists in this topic are empty unless a pledge is active)."""
    return get(raw, "keys", "total")
