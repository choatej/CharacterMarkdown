"""Tests for the topic models. Run: python3 -m unittest tools.cmdata.test_topics

Set CM_DUMP to the path of a real ``*_data_*.json`` file to also run the checks against it.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.cmdata import CharacterExport, load_export, to_dict, to_json, to_lean_markdown
from tools.cmdata.__main__ import main
from tools.cmdata.antiquities import WEEK_SECONDS, Antiquities
from tools.cmdata.crafting import Crafting
from tools.cmdata.render import ALL_SECTIONS, DEFAULT_SECTIONS
from tools.cmdata.topics import (
    Collectibles,
    Currency,
    Inventory,
    Mundus,
    SkillMorphs,
    WorldProgress,
    quality_name,
)
from tools.cmdata.util import as_list, records

DAY = 86400


def lead(ident: int, name: str, seconds: int | None, **extra: object) -> dict:
    """An antiquity record as the export stores it."""
    return {
        "id": ident,
        "name": name,
        "hasLead": seconds is not None,
        "leadSecondsRemaining": seconds,
        "leadExpiresAt": 1_760_000_000 + seconds if seconds else None,
        "isDiscovered": False,
        "isCompleted": False,
        "isRepeatable": True,
        "numGoals": 6,
        "numAchieved": 0,
        "numRecovered": 0,
        "quality": 1,
        **extra,
    }


ANTIQUITIES = {
    "summary": {
        "totalAntiquities": 5,
        "discoveredAntiquities": 1,
        "completedSets": 0,
        "totalSets": 2,
        "activeLeads": 4,
    },
    "sets": [
        {
            "id": 0,
            "name": "",
            "numAntiquities": 0,
            "discoveredAntiquities": 1,
            "completedAntiquities": 0,
            "antiquities": [
                lead(1, "Later", 20 * DAY),
                lead(2, "Soon", 2 * DAY),
                lead(3, "Exactly a week", WEEK_SECONDS),
                lead(4, "No lead", None),
            ],
        },
        {
            "id": 7,
            "name": "Some Set",
            "numAntiquities": 1,
            "antiquities": [lead(5, "Just over a week", WEEK_SECONDS + 1)],
        },
    ],
    # the export repeats the leads here; one of them (id 9) is in no set at all
    "activeLeads": [lead(1, "Later", 20 * DAY), lead(2, "Soon", 2 * DAY), lead(9, "Orphan", 5 * DAY)],
}

CRAFTING = {
    "summary": {"activeTimers": 0, "researchProgress": {"blacksmithing": 100, "clothing": 80}},
    "motifs": [
        {
            "name": "Full Motif",
            "isCompleted": True,
            "numKnown": 2,
            "total": 2,
            "chapters": [{"name": "Axes", "known": True}, {"name": "Belts", "known": True}],
        },
        {
            "name": "Partial Motif",
            "isCompleted": False,
            "numKnown": 1,
            "total": 3,
            "chapters": [
                {"name": "Axes", "known": True},
                {"name": "Belts", "known": False},
                {"name": "Boots", "known": False},
            ],
        },
    ],
    "recipes": {
        "all": [
            {"name": "Stew", "craftType": 5, "quality": 1, "resultId": 11},
            {"name": "Loose Recipe", "craftType": 5, "quality": 0, "resultId": 12},
        ],
        "byList": {"Dining": [{"name": "Stew", "craftType": 5, "quality": 1, "resultId": 11}]},
        "count": 2,
    },
    "research": {
        "blacksmithing": [
            {"name": "Axe", "timeRequiredSecs": 100, "traits": [{"id": 1, "known": True}]}
        ],
        "clothing": [
            {
                "name": "Robe",
                "timeRequiredSecs": 200,
                "traits": [{"id": 1, "known": True}, {"id": 2, "known": False}, {"id": 5, "known": False}],
            }
        ],
    },
    "itemSetCollection": {
        "count": 2,
        "incomplete": [
            {"id": 1, "name": "Low", "percent": 10, "total": 10, "unlocked": 1},
            {"id": 2, "name": "High", "percent": 90, "total": 10, "unlocked": 9},
        ],
    },
    "styles": {"count": 2, "list": [{"id": 1, "name": "Breton"}, {"id": 2, "name": "Orc"}]},
    "timers": {},
}

TOPICS = {
    "character": {"name": "Tester", "class": "Templar", "level": 50, "cp": 100},
    "antiquities": ANTIQUITIES,
    "crafting": CRAFTING,
    "skill": {
        "lines": [
            {
                "name": "Aedric Spear",
                "rank": 50,
                "status": "maxed",
                "progress": 100,
                "xp": {"current": 5, "min": 1, "max": 5},
                "passives": [{"name": "Piercing", "currentRank": 2, "maxRank": 2, "purchased": True}],
            },
            {"name": "Bow", "rank": 34, "status": "inProgress", "progress": 3, "passives": {}},
        ],
        "summary": {"maxedCount": 1, "inProgressCount": 1, "completionPercent": 50},
    },
    "skillMorphs": {
        "class": "Templar",
        "skillTypes": [
            {
                "name": "Class",
                "skillLines": [
                    {
                        "name": "Aedric Spear",
                        "abilities": [
                            {
                                "name": "Sweep",
                                "purchased": True,
                                "currentRank": 4,
                                "atMorphChoice": False,
                                "morphs": [
                                    {"name": "Everlasting", "selected": False},
                                    {"name": "Crescent", "selected": True},
                                ],
                            },
                            {
                                "name": "Wait",
                                "atMorphChoice": True,
                                "morphs": [{"name": "A"}, {"name": "B"}],
                            },
                        ],
                    }
                ],
            }
        ],
        "summary": {"chosenMorphs": 1, "totalMorphs": 2},
    },
    "progression": {
        "achievementPoints": 10,
        "unspentSkillPoints": 2,
        "vampireStatus": "active",
        "vampireStage": 1,
        "werewolfStatus": "never",
        "werewolfStage": 0,
    },
    "currency": {"gold": 500, "transmute": 10, "transmuteMax": 100, "ap": 7, "summary": {"totalGold": 500}},
    "inventory": {
        "backpackUsed": 2,
        "backpackMax": 100,
        "bankUsed": 1,
        "bankMax": 50,
        "hasCraftingBag": True,
        "bagItems": [{"name": "Sword", "quality": 4, "stack": 1, "slot": 3}],
        "bankItems": {},
        "craftingBagItems": [{"name": "Berry", "quality": 1, "stack": 9, "itemTypeName": "Ingredient"}],
    },
    "collectibles": {
        "esoPlus": True,
        "collections": {
            "mounts": {
                "count": 1,
                "total": 10,
                "list": [{"id": 2, "name": "Horse", "fullName": "Sorrel Horse", "nickname": "Pal"}],
            },
            "hair": {"count": 0, "total": 5, "list": {}},
        },
    },
    "styles": {"count": 1, "categories": {"all": [{"id": 5, "name": "Robe", "fullName": "Breton Robe"}]}},
    "titles": {"current": "Hero", "owned": [{"id": 1, "name": "Hero"}], "summary": {"totalAvailable": 9}},
    "housing": {
        "owned": [{"id": 1, "name": "House", "nickname": "Home"}],
        "primary": {"name": "Gardner", "furnitureCount": 5, "isListedOnTours": False},
        "summary": {"totalAvailable": 124},
    },
    "quests": {
        "active": [
            {
                "name": "Quest",
                "type": "Main",
                "zone": "Zone",
                "level": 5,
                "stepText": "Do it",
                "conditions": [{"text": "Kill", "current": 1, "max": 3, "isComplete": False}],
            }
        ]
    },
    "worldProgress": {
        "skyshards": {"collected": 5, "total": 10, "zones": {"Auridon": {"collected": 5, "total": 5}}},
        "lorebooks": {"collected": 1, "total": 2, "categories": {"Mages": {"collected": 1, "total": 2}}},
        "dungeons": {"delves": {"completed": 3, "total": 4}, "publicDungeons": {"completed": 1, "total": 2}},
        "cadwell": {"levelName": "Gold", "zones": [{"name": "Deshaan"}]},
    },
    "achievements": {
        "points": 10,
        "total": 100,
        "summary": {"completionPercent": 10},
        "categories": [{"name": "Combat", "earned": 5, "total": 50, "percent": 10}],
        "recent": [{"name": "Done", "date": "11/13/2026", "time": "22:28:31"}],
    },
    "companion": {
        "active": {"name": "Bastian", "level": 20},
        "rapportLevel": 7,
        "companions": [{"id": 1, "name": "Bastian"}],
        "equipment": [
            {
                "name": "Staff",
                "slot": "Main Hand",
                "quality": "Superior",
                "traitName": "Reduces cooldowns by |cffffff4.4|r%.",
                "setName": "",
            }
        ],
        "skills": {"abilities": [{"id": 1, "name": "Char"}], "ultimate": "Gore"},
    },
    "pvp": {
        "basic": {"rank": 6, "rankName": "Tyro", "rankPoints": 90, "campaignName": "None"},
        "stats": {"pvp": {"allianceName": "Covenant", "progression": {"pointsToNext": 55}}},
    },
    "guilds": {"list": [{"name": "Guild", "rankName": "Trader", "memberCount": 5, "alliance": {"name": "Pact"}}]},
    "appearance": {
        "active": {"hat": {"name": "Hide"}, "pet": {"name": "Bird"}},
        "mount": {"name": "Mammoth", "skinName": "Skin"},
        "outfit": {"name": "Default"},
        "dyes": {"known": 1, "total": 2},
    },
    "location": {"zone": "Shadowfen", "subzone": "Hamlet", "world": "NA", "zoneId": 117},
    "riding": {"speed": 60, "stamina": 60, "capacity": 60, "maxedOut": True},
    "mundus": {"active": True, "name": "The Thief", "names": ["The Thief"], "primary": "The Thief"},
    "dlc": {"accessible": ["Cyrodiil"], "locked": {}},
    "mail": {"count": 0, "list": {}, "summary": {"totalMail": 3, "unreadCount": 1}},
    "undauntedPledges": {"keys": {"total": 193}, "active": {}},
    "buffs": {"other": ["Gallop"]},
    "role": {"selected": "None", "emoji": "?"},
    "armoryBuilds": {
        "builds": [
            {
                "name": "Build 1",
                "index": 1,
                "curse": "Vampire",
                "mundus": {"primary": "The Thief"},
                "skillPoints": 291,
                "attributes": {"health": 44, "magicka": 20, "stamina": 0},
                "champion": {"craft": 265, "total": 793},
                "equipment": [
                    {"name": "Helm", "slotName": "Head", "slotIndex": 0, "armorType": 2, "setName": "Set A"},
                    {"name": "[Empty Slot]", "slotName": "Neck", "slotIndex": 1},
                ],
                "hotbars": [
                    {
                        "name": "⚔️ Front Bar",
                        "abilities": [
                            {"name": "Strike", "slot": 3},
                            {"name": "[Empty Slot]", "slot": 4},
                        ],
                    }
                ],
                "sets": [{"name": "Set A", "count": 5}],
            }
        ]
    },
    # redundant composites the export builds from other topics
    "titlesHousing": {"titles": {"current": "Hero"}},
    "characterAttributes": {"name": "Tester", "buffs": {"other": ["Gallop"]}},
    "somethingNew": {"x": 1},
}


def build() -> CharacterExport:
    return CharacterExport.from_document({"data": TOPICS, "exported": 1_760_000_000})


class UtilTest(unittest.TestCase):
    def test_empty_lua_table_is_an_empty_list(self) -> None:
        self.assertEqual(as_list({}), [])
        self.assertEqual(as_list(None), [])
        self.assertEqual(records({}), [])
        self.assertEqual(records([{"a": 1}, "x", 3]), [{"a": 1}])


class AntiquitiesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.a = Antiquities.from_raw(ANTIQUITIES)

    def test_every_antiquity_appears_once(self) -> None:
        ids = sorted(x.id for x in self.a.antiquities)
        self.assertEqual(ids, [1, 2, 3, 4, 5, 9])  # 9 only existed in activeLeads
        self.assertEqual(len(ids), len(set(ids)))

    def test_set_without_a_name_has_no_name_and_counts_its_members(self) -> None:
        no_set, some = self.a.sets
        self.assertIsNone(no_set.name)
        self.assertEqual(no_set.total, 4)  # numAntiquities says 0, but it holds four
        self.assertEqual((some.name, some.total), ("Some Set", 1))
        member = next(x for x in self.a.antiquities if x.id == 5)
        self.assertEqual(member.set_id, 7)
        self.assertIsNone(next(x for x in self.a.antiquities if x.id == 1).set_id)

    def test_leads_are_sorted_soonest_first_and_skip_antiquities_without_one(self) -> None:
        names = [x.name for x in self.a.leads()]
        self.assertEqual(
            names, ["Soon", "Orphan", "Exactly a week", "Just over a week", "Later"]
        )

    def test_expiring_within_a_week_includes_exactly_a_week(self) -> None:
        names = [x.name for x in self.a.leads_expiring_within()]
        self.assertEqual(names, ["Soon", "Orphan", "Exactly a week"])
        self.assertEqual([x.name for x in self.a.leads_expiring_within(3 * DAY)], ["Soon"])

    def test_a_lead_with_no_timer_sorts_last(self) -> None:
        raw = {"sets": [{"id": 1, "antiquities": [lead(1, "Timed", DAY), lead(2, "Untimed", 5)]}]}
        raw["sets"][0]["antiquities"][1]["leadSecondsRemaining"] = None
        self.assertEqual([x.name for x in Antiquities.from_raw(raw).leads()], ["Timed", "Untimed"])

    def test_leads_are_not_repeated_in_the_json(self) -> None:
        data = to_dict(build())["antiquities"]
        self.assertNotIn("leads", data)
        self.assertEqual(len(data["antiquities"]), 6)


class CraftingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.c = Crafting.from_raw(CRAFTING)

    def test_motifs_list_only_missing_chapters(self) -> None:
        full, partial = self.c.motifs
        self.assertEqual((full.chapters_known, full.chapters_total, full.missing_chapters), (2, 2, []))
        self.assertEqual(partial.missing_chapters, ["Belts", "Boots"])
        self.assertEqual(self.c.motifs_completed(), 1)

    def test_recipes_keep_their_list_name_and_none_when_unlisted(self) -> None:
        stew, loose = self.c.recipes
        self.assertEqual((stew.recipe_list, loose.recipe_list), ("Dining", None))
        self.assertEqual(self.c.recipe_counts(), {"Dining": 1, "(no list)": 1})

    def test_research_is_counted_and_missing_trait_ids_are_kept_for_tools(self) -> None:
        robe = self.c.research["clothing"][0]
        self.assertEqual((robe.traits_known, robe.traits_total, robe.missing_trait_ids), (1, 3, [2, 5]))
        self.assertEqual([(line, i.name) for line, i in self.c.research_gaps()], [("clothing", "Robe")])
        self.assertEqual(self.c.research_percent, {"blacksmithing": 100, "clothing": 80})

    def test_item_sets_styles_and_timers(self) -> None:
        self.assertEqual([s.name for s in self.c.incomplete_item_sets], ["Low", "High"])
        self.assertEqual(self.c.known_styles, ["Breton", "Orc"])
        self.assertEqual(self.c.active_research_timers, 0)


class TopicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.export = build()

    def test_skill_lines_tolerate_empty_lists(self) -> None:
        s = self.export.skill_lines
        self.assertEqual([line.name for line in s.lines], ["Aedric Spear", "Bow"])
        self.assertEqual((s.maxed, s.in_progress, s.completion_percent), (1, 1, 50))
        self.assertEqual(s.lines[0].passives[0].rank, 2)
        self.assertEqual(s.lines[1].passives, [])  # the export gave {}

    def test_morphs(self) -> None:
        m = SkillMorphs.from_raw(TOPICS["skillMorphs"])
        sweep, wait = m.skills
        self.assertEqual((sweep.chosen_morph, sweep.morph_options), ("Crescent", ["Everlasting", "Crescent"]))
        self.assertEqual((wait.chosen_morph, wait.awaiting_choice), (None, True))
        self.assertEqual(sweep.skill_line, "Aedric Spear")

    def test_progression(self) -> None:
        p = self.export.progression
        self.assertEqual((p.unspent_skill_points, p.vampire_status, p.vampire_stage), (2, "active", 1))

    def test_currency_splits_caps_and_ignores_the_summary(self) -> None:
        c = Currency.from_raw(TOPICS["currency"])
        self.assertEqual(c.amounts, {"gold": 500, "transmute": 10, "ap": 7})
        self.assertEqual(c.caps, {"transmute": 100})
        self.assertEqual(c.gold, 500)

    def test_inventory_names_confirmed_qualities_only(self) -> None:
        inv = Inventory.from_raw(TOPICS["inventory"])
        self.assertEqual((inv.backpack_items[0].quality, inv.backpack_items[0].quality_name), (4, "epic"))
        self.assertEqual(inv.bank_items, [])  # {} from the export
        self.assertEqual(inv.crafting_bag_items[0].item_type, "Ingredient")
        self.assertEqual([quality_name(n) for n in (2, 3, 4, 5)], ["fine", "superior", "epic", "legendary"])
        self.assertIsNone(quality_name(99))

    def test_collectibles(self) -> None:
        c = Collectibles.from_raw(TOPICS["collectibles"])
        mounts = c.groups["mounts"]
        self.assertEqual((mounts.owned, mounts.total), (1, 10))
        self.assertEqual((mounts.items[0].name, mounts.items[0].nickname), ("Sorrel Horse", "Pal"))
        self.assertEqual(c.groups["hair"].items, [])

    def test_titles_housing_styles(self) -> None:
        e = self.export
        self.assertEqual((e.titles.current, e.titles.owned, e.titles.available), ("Hero", ["Hero"], 9))
        self.assertEqual(e.housing.primary.name, "Gardner")
        self.assertEqual(e.housing.owned[0].nickname, "Home")
        self.assertEqual((e.outfit_styles.count, e.outfit_styles.names), (1, ["Breton Robe"]))

    def test_quests(self) -> None:
        quest = self.export.quests.active[0]
        self.assertEqual((quest.name, quest.quest_type, quest.zone, quest.step), ("Quest", "Main", "Zone", "Do it"))
        self.assertEqual((quest.conditions[0].current, quest.conditions[0].maximum), (1, 3))

    def test_world_progress(self) -> None:
        w = WorldProgress.from_raw(TOPICS["worldProgress"])
        self.assertEqual((w.skyshards.collected, w.skyshards.total), (5, 10))
        self.assertEqual(w.skyshards_by_zone["Auridon"].total, 5)
        self.assertEqual((w.delves.collected, w.public_dungeons.total), (3, 2))
        self.assertEqual((w.cadwell_level, w.cadwell_zones), ("Gold", ["Deshaan"]))

    def test_achievements_companion_pvp_guilds(self) -> None:
        e = self.export
        self.assertEqual((e.achievements.points, e.achievements.total_points), (10, 100))
        self.assertEqual(e.achievements.recent[0].name, "Done")
        self.assertEqual(e.companion.equipment[0].trait, "Reduces cooldowns by 4.4%.")
        self.assertIsNone(e.companion.equipment[0].set_name)
        self.assertEqual((e.companion.ultimate, e.companion.abilities), ("Gore", ["Char"]))
        self.assertEqual((e.pvp.rank_name, e.pvp.points_to_next_rank, e.pvp.campaign), ("Tyro", 55, None))
        self.assertEqual((e.guilds[0].name, e.guilds[0].alliance), ("Guild", "Pact"))

    def test_small_topics(self) -> None:
        e = self.export
        self.assertEqual((e.appearance.mount, e.appearance.pet, e.appearance.dyes_total), ("Mammoth", "Bird", 2))
        self.assertEqual((e.location.zone, e.riding.maxed_out), ("Shadowfen", True))
        self.assertEqual(e.mundus.names, ["The Thief"])  # primary + name + names are not repeated
        self.assertEqual((e.dlc_access.accessible, e.dlc_access.locked), (["Cyrodiil"], []))
        self.assertEqual((e.mail.total, e.mail.unread), (3, 1))
        self.assertEqual((e.undaunted_keys, e.buffs, e.role), (193, ["Gallop"], None))
        self.assertEqual(Mundus.from_raw({"primary": "X", "name": "X"}).names, ["X"])

    def test_armory_build_skips_empty_slots_and_bars(self) -> None:
        build_ = self.export.armory_builds[0]
        self.assertEqual((build_.name, build_.curse, build_.mundus), ("Build 1", "Vampire", "The Thief"))
        self.assertEqual([i.name for i in build_.equipment], ["Helm"])
        self.assertEqual(build_.equipment[0].armor_weight, "medium")
        self.assertEqual(build_.bars[0].name, "Front Bar")
        self.assertEqual([a.name for a in build_.bars[0].abilities], ["Strike"])
        self.assertEqual((build_.sets[0].name, build_.sets[0].pieces_worn), ("Set A", 5))
        self.assertEqual(build_.champion_points["total"], 793)

    def test_redundant_topics_are_dropped_and_unknown_ones_kept(self) -> None:
        self.assertEqual(set(self.export.extra), {"somethingNew"})

    def test_missing_topics_are_none_or_empty(self) -> None:
        bare = CharacterExport.from_document({"character": {"name": "Solo"}})
        self.assertIsNone(bare.antiquities)
        self.assertIsNone(bare.crafting)
        self.assertEqual(bare.guilds, [])
        self.assertEqual(bare.armory_builds, [])
        self.assertEqual(bare.buffs, [])


class LeanTopicsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.export = build()

    def lean(self, *sections: str) -> str:
        return to_lean_markdown(self.export, list(sections))

    def test_default_output_is_still_only_the_build(self) -> None:
        text = to_lean_markdown(self.export)
        self.assertNotIn("## Antiquities", text)
        self.assertNotIn("## Crafting", text)

    def test_identity_header_shows_mundus_and_curse(self) -> None:
        self.assertIn("Mundus: The Thief | Vampire stage 1", self.lean())

    def test_antiquities_section(self) -> None:
        text = self.lean("antiquities")
        self.assertIn("1/5 discovered | 0/2 sets complete | 5 active leads", text)
        self.assertIn("Leads expiring within 7 days:", text)
        self.assertIn("- Soon (2d 0h)", text)
        self.assertIn("- Exactly a week (7d 0h)", text)
        self.assertIn("Next to expire after that: Just over a week (7d 0h), Later (20d 0h)", text)

    def test_antiquities_with_nothing_expiring(self) -> None:
        raw = {"sets": [{"id": 1, "antiquities": [lead(1, "Far", 30 * DAY)]}]}
        export = CharacterExport.from_document({"character": {"name": "X"}, "antiquities": raw})
        text = to_lean_markdown(export, ["antiquities"])
        self.assertIn("No leads expire within 7 days.", text)
        self.assertIn("Far (30d 0h)", text)

    def test_other_sections(self) -> None:
        text = self.lean(*ALL_SECTIONS)
        for expected in (
            "Unspent points: skill 2 | Vampire: active (stage 1)",
            "1 maxed | 1 in progress | 50% complete",
            "- Bow (rank 34, 3%)",
            "Morph choice waiting: Wait",
            "Motifs 1/2 complete | 2 recipes in 2 lists | 2 crafting styles known",
            "- clothing: Robe (1/3 traits)",
            "closest first): High 90%, Low 10%",
            "Backpack 2/100 | Bank 1/50 | Crafting bag 1 stacks",
            "Mounts 1/10",
            "Skyshards 5/10 | Lorebooks 1/2 | Delves 3/4 | Public dungeons 1/2 | Cadwell: Gold",
            "- Quest (Zone)",
            "10/100 points | 10% complete",
            "Recently completed: Done",
            "Gold 500 | Transmute 10/100 | Alliance Points 7",
            "Location: Shadowfen (Hamlet) | Riding maxed",
            "Mount: Mammoth | Pet: Bird | Outfit: Default",
            "Guilds: Guild",
            "PvP rank: Tyro | Companion: Bastian",
            "- Build 1: Set A x5 | Mundus The Thief | Vampire",
        ):
            self.assertIn(expected, text)

    def test_ai_text_has_no_ids_or_markup(self) -> None:
        text = self.lean(*ALL_SECTIONS)
        self.assertNotIn("|c", text)
        self.assertNotRegex(text, r"(?i)\b(?:resultId|craftType|abilityId|zoneId|skillId|trait id)\b")
        self.assertNotIn("missing_trait_ids", text)

    def test_unknown_section_is_an_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown section"):
            self.lean("nonsense")

    def test_every_default_section_exists(self) -> None:
        self.assertTrue(set(DEFAULT_SECTIONS) <= set(ALL_SECTIONS))


class CliTopicsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.file = Path(self._tmp.name) / "x_data.json"
        self.file.write_text(json.dumps({"data": TOPICS, "exported": 1}), encoding="utf-8")

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_topics_option(self) -> None:
        code, out, _ = self.run_cli(str(self.file), "--topics", "antiquities")
        self.assertEqual(code, 0)
        self.assertIn("## Antiquities", out)
        self.assertNotIn("## Gear", out)

    def test_all_topics(self) -> None:
        _, out, _ = self.run_cli(str(self.file), "--topics", "all")
        for heading in ("## Antiquities", "## Crafting", "## Inventory", "## Profile"):
            self.assertIn(heading, out)

    def test_unknown_topic_is_an_error_message(self) -> None:
        code, _, err = self.run_cli(str(self.file), "--topics", "antiquities,bogus")
        self.assertEqual(code, 1)
        self.assertIn("unknown section(s): bogus", err)

    def test_json_is_the_full_typed_export(self) -> None:
        document = json.loads(to_json(build()))
        self.assertEqual(document["antiquities"]["total"], 5)
        self.assertEqual(document["crafting"]["recipes"][0]["recipe_list"], "Dining")
        self.assertEqual(document["extra"], {"somethingNew": {"x": 1}})


@unittest.skipUnless(os.environ.get("CM_DUMP"), "set CM_DUMP to a real *_data_*.json to run")
class RealDumpTopicsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = os.environ["CM_DUMP"]
        self.raw = json.loads(Path(self.path).read_text(encoding="utf-8"))["data"]
        self.export = load_export(self.path)

    def test_every_topic_has_a_model(self) -> None:
        self.assertEqual(self.export.extra, {})

    def test_antiquities_agree_with_the_export_summary(self) -> None:
        summary = self.raw["antiquities"]["summary"]
        a = self.export.antiquities
        self.assertEqual(len(a.antiquities), summary["totalAntiquities"])
        self.assertEqual(len(a.leads()), summary["activeLeads"])

    def test_recipes_and_motifs_agree_with_the_export_summary(self) -> None:
        summary = self.raw["crafting"]["summary"]
        c = self.export.crafting
        self.assertEqual(len(c.recipes), summary["totalRecipes"])
        self.assertEqual(len(c.motifs), summary["totalMotifs"])

    def test_typed_json_is_smaller_than_the_raw_data(self) -> None:
        self.assertLess(len(to_json(self.export, indent=None)), len(json.dumps(self.raw)))

    def test_all_sections_render_without_ids(self) -> None:
        text = to_lean_markdown(self.export, list(ALL_SECTIONS))
        self.assertNotIn("|c", text)


if __name__ == "__main__":
    unittest.main()
