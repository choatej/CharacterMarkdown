"""CharacterExport: one character's structured export, with a typed object for each topic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .antiquities import Antiquities
from .armory import ArmoryBuild, armory_builds_from_raw
from .clean import none_if_blank
from .crafting import Crafting
from .model import ChampionPoints, Character, Equipment, SkillBars, Stats
from .topics import (
    Achievements,
    Appearance,
    Collectibles,
    Companion,
    Currency,
    DlcAccess,
    Guild,
    Housing,
    Inventory,
    Location,
    Mail,
    Mundus,
    OutfitStyles,
    Progression,
    PvP,
    Quests,
    Riding,
    SkillLines,
    SkillMorphs,
    Titles,
    WorldProgress,
    guilds_from_raw,
    undaunted_keys_from_raw,
)
from .util import as_dict, strings

# topic in the export -> (attribute on CharacterExport, function that builds it from the raw topic)
TOPICS: dict[str, tuple[str, Any]] = {
    "stats": ("stats", Stats.from_raw),
    "equipment": ("equipment", Equipment.from_raw),
    "skillBar": ("skill_bars", SkillBars.from_raw),
    "cp": ("champion_points", ChampionPoints.from_raw),
    "antiquities": ("antiquities", Antiquities.from_raw),
    "skill": ("skill_lines", SkillLines.from_raw),
    "skillMorphs": ("skill_morphs", SkillMorphs.from_raw),
    "progression": ("progression", Progression.from_raw),
    "currency": ("currency", Currency.from_raw),
    "inventory": ("inventory", Inventory.from_raw),
    "collectibles": ("collectibles", Collectibles.from_raw),
    "styles": ("outfit_styles", OutfitStyles.from_raw),
    "titles": ("titles", Titles.from_raw),
    "housing": ("housing", Housing.from_raw),
    "crafting": ("crafting", Crafting.from_raw),
    "quests": ("quests", Quests.from_raw),
    "armoryBuilds": ("armory_builds", armory_builds_from_raw),
    "worldProgress": ("world_progress", WorldProgress.from_raw),
    "achievements": ("achievements", Achievements.from_raw),
    "companion": ("companion", Companion.from_raw),
    "pvp": ("pvp", PvP.from_raw),
    "guilds": ("guilds", guilds_from_raw),
    "appearance": ("appearance", Appearance.from_raw),
    "location": ("location", Location.from_raw),
    "riding": ("riding", Riding.from_raw),
    "mundus": ("mundus", Mundus.from_raw),
    "dlc": ("dlc_access", DlcAccess.from_raw),
    "mail": ("mail", Mail.from_raw),
    "undauntedPledges": ("undaunted_keys", undaunted_keys_from_raw),
    "buffs": ("buffs", lambda raw: strings(raw.get("other"))),
    "role": ("role", lambda raw: none_if_blank(raw.get("selected"))),
}

# Handled outside TOPICS: the character itself and the player's own text settings.
OTHER_MODELLED = ("character", "customNotes", "playStyle")

# Topics the export builds by combining others; they add no information, so they are not kept.
#   titlesHousing = titles + housing + collectibles
#   characterAttributes = character + mundus + location + riding + buffs (a copy of those)
DERIVED_TOPICS = ("titlesHousing", "characterAttributes")


@dataclass
class CharacterExport:
    """One character's structured export plus the context it was saved with.

    A topic that was not collected (the user's settings left it out) is ``None``.
    """

    character: Character
    stats: Stats | None = None
    equipment: Equipment | None = None
    skill_bars: SkillBars | None = None
    champion_points: ChampionPoints | None = None
    # free text the player wrote for the AI (settings: Build Notes, Play Style)
    build_notes: str | None = None
    play_style: str | None = None
    antiquities: Antiquities | None = None
    skill_lines: SkillLines | None = None
    skill_morphs: SkillMorphs | None = None
    progression: Progression | None = None
    currency: Currency | None = None
    inventory: Inventory | None = None
    collectibles: Collectibles | None = None
    outfit_styles: OutfitStyles | None = None
    titles: Titles | None = None
    housing: Housing | None = None
    crafting: Crafting | None = None
    quests: Quests | None = None
    armory_builds: list[ArmoryBuild] = field(default_factory=list)
    world_progress: WorldProgress | None = None
    achievements: Achievements | None = None
    companion: Companion | None = None
    pvp: PvP | None = None
    guilds: list[Guild] = field(default_factory=list)
    appearance: Appearance | None = None
    location: Location | None = None
    riding: Riding | None = None
    mundus: Mundus | None = None
    dlc_access: DlcAccess | None = None
    mail: Mail | None = None
    undaunted_keys: int | None = None
    buffs: list[str] = field(default_factory=list)
    role: str | None = None
    exported_at: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    # any topic this version does not know about, exactly as the game gave it
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> CharacterExport:
        """Build from the JSON that ``tools.sv_export`` writes for ``/cm save data``.

        A bare data table (the value of the document's ``data`` key) is accepted too.
        """
        wrapped = isinstance(document.get("data"), dict)
        data = document["data"] if wrapped else document
        character_raw = data.get("character")
        if not isinstance(character_raw, dict):
            raise ValueError("this export has no 'character' topic (is it a /cm save data export?)")

        typed: dict[str, Any] = {}
        for topic, (attribute, build) in TOPICS.items():
            raw = data.get(topic)
            if isinstance(raw, dict) and raw:
                typed[attribute] = build(raw)

        known = {*TOPICS, *OTHER_MODELLED, *DERIVED_TOPICS}
        return cls(
            character=Character.from_raw(character_raw),
            build_notes=none_if_blank(data.get("customNotes")),
            play_style=none_if_blank(data.get("playStyle")),
            exported_at=document.get("exported") if wrapped else None,
            meta=as_dict(document.get("meta")) if wrapped else {},
            report=as_dict(document.get("report")) if wrapped else {},
            extra={k: v for k, v in data.items() if k not in known},
            **typed,
        )
