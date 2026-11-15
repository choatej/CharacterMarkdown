"""Tests for tools.cmdata. Run: python3 -m unittest tools.cmdata.test_model

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
from tools.cmdata.clean import none_if_blank, single_line, strip_decoration, strip_markup

DATA = {
    "character": {
        "name": "Test Character",
        "account": "@tester",
        "server": "NA Megaserver",
        "class": "Templar",
        "race": "Orc",
        "gender": "Female",
        "alliance": "Daggerfall Covenant",
        "level": 50,
        "cp": 1000,
        "title": "Tester",
        "esoPlus": True,
        "attributes": {"health": 10, "magicka": 54, "stamina": 0},
        "ageMetrics": {"seconds": 90000},
        "subclass": {"native": [{"name": "Aedric Spear", "rank": 50}]},
    },
    "stats": {
        "health": 30000,
        "magicka": 25000,
        "stamina": 18000,
        "weaponPower": 4000,
        "spellPower": 4100,
        "weaponCritChance": 45.7,
        "spellCritChance": 46.2,
        "physicalPenetration": 1600,
        "spellPenetration": 1650,
        "advanced": {"damage": {"criticalDamage": 86}},
        "effectiveHealth": {"average": 250000},
        "dpsEstimates": {"average": 5400},
    },
    "equipment": {
        "gearScore": "258",
        "traitDistribution": {"Divines": 2},
        "items": [
            {
                "slotIndex": 0,
                "slotName": "Head",
                "name": "Test Helm",
                "emoji": "X",
                "qualityEmoji": "Y",
                "quality": "Epic",
                "qualityNumeric": 4,
                "setName": "Test Set",
                "trait": "Divines",
                "enchantment": "Maximum Magicka Enchantment",
                "armorType": 2,
                "weaponType": 0,
                "isCrafted": True,
                "isEmpty": False,
                "requiredLevel": 50,
                "requiredCP": 160,
            },
            {"slotIndex": 1, "slotName": "Neck", "name": "[Empty]", "isEmpty": True},
            {
                "slotIndex": 2,
                "slotName": "Ring 1",
                "name": "Plain Ring",
                "setName": "-",
                "enchantment": False,
                "trait": "None",
                "armorType": 0,
                "isEmpty": False,
            },
            {
                "slotIndex": 4,
                "slotName": "Main Hand",
                "name": "Odd Blade",
                "weaponType": 11,
                "bindType": 2,
                "style": 3,
                "isEmpty": False,
            },
            {
                "slotIndex": 5,
                "slotName": "Off Hand",
                "name": "Test Dagger",
                "weaponType": 11,
                "isEmpty": False,
            },
            {
                "slotIndex": 20,
                "slotName": "Backup Main Hand",
                "name": "Mystery Weapon",
                "weaponType": 99,
                "isEmpty": False,
            },
        ],
        "sets": [
            {
                "name": "Test Set",
                "count": 1,
                "bonuses": [
                    {
                        "numRequired": 2,
                        "isActive": False,
                        "description": "(2 items) Adds |cffffff657|r Critical Chance",
                    }
                ],
            }
        ],
    },
    "skillBar": {
        "activeWeaponPair": {"label": "Main"},
        "points": {"unspent": 3},
        "bars": [
            {
                "name": "⚔️ Front Bar (Main Hand)",
                "ultimate": "Big Ult",
                "ultimateId": 99,
                "abilities": [
                    {"id": 2, "name": "Second", "slot": 4},
                    {"id": 1, "name": "First", "slot": 3, "isCrafted": True},
                ],
            }
        ],
    },
    "cp": {
        "total": 1000,
        "spent": 990,
        "available": 10,
        "disciplines": [
            {
                "name": "Warfare",
                "spent": 100,
                "available": 0,
                "allStars": [{"skillId": 7, "name": "Star", "maxPoints": 50, "points": 20}],
                "skills": [
                    {
                        "skillId": 7,
                        "name": "Star",
                        "points": 20,
                        "isSlottable": True,
                        "type": "slottable",
                    },
                    {"skillId": 8, "name": "Idle", "points": 0, "isSlottable": False},
                ],
            }
        ],
    },
    "customNotes": "Solo trials. Wants more sustain.",
    "playStyle": "solo_self_sufficient",
    # topics without a typed model
    "antiquities": {"summary": {"activeLeads": 2}},
    "currency": {"gold": 5},
}

DOCUMENT = {
    "character": "Test Character",
    "exported": 1760000000,
    "meta": {"addonVersion": "test"},
    "report": {"dropped": 0},
    "data": DATA,
}


class CleanTest(unittest.TestCase):
    def test_strip_markup(self) -> None:
        self.assertEqual(
            strip_markup("Adds |cffffff657|r Critical Chance"), "Adds 657 Critical Chance"
        )
        self.assertEqual(strip_markup("|cFF00FFcoloured|r and |cabcdefmore|r"), "coloured and more")
        self.assertEqual(strip_markup("stray |r reset"), "stray reset")
        self.assertEqual(strip_markup("plain"), "plain")

    def test_single_line(self) -> None:
        self.assertEqual(single_line("one\n\ntwo\n  three "), "one two three")

    def test_strip_decoration(self) -> None:
        self.assertEqual(strip_decoration("⚔️ Front Bar (Main Hand)"), "Front Bar (Main Hand)")
        self.assertEqual(strip_decoration("(Bracketed)"), "(Bracketed)")

    def test_none_if_blank(self) -> None:
        for blank in (None, False, "", "  ", "-", "None"):
            self.assertIsNone(none_if_blank(blank), blank)
        self.assertEqual(none_if_blank("Epic"), "Epic")


class ModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.export = CharacterExport.from_document(DOCUMENT)

    def test_character(self) -> None:
        c = self.export.character
        self.assertEqual(
            (c.name, c.class_name, c.level, c.champion_points),
            ("Test Character", "Templar", 50, 1000),
        )
        self.assertEqual(c.played_seconds, 90000)
        self.assertEqual(c.class_skill_lines[0].name, "Aedric Spear")
        self.assertEqual(c.attributes["magicka"], 54)

    def test_stats(self) -> None:
        s = self.export.stats
        self.assertEqual((s.health, s.weapon_power, s.critical_damage), (30000, 4000, 86))
        self.assertEqual(s.effective_health["average"], 250000)

    def test_items_drop_empty_slots_and_decoration(self) -> None:
        items = self.export.equipment.items
        self.assertEqual(
            [i.slot for i in items],
            ["Head", "Ring 1", "Main Hand", "Off Hand", "Backup Main Hand"],
        )
        helm, ring = items[0], items[1]
        self.assertEqual(
            (helm.set_name, helm.armor_weight, helm.armor_type), ("Test Set", "medium", 2)
        )
        self.assertEqual((helm.required_level, helm.required_champion_points), (50, 160))
        self.assertIsNone(helm.weapon_type)
        # "no set", "no enchantment", "no trait" markers become None
        blanks = (ring.set_name, ring.enchantment, ring.trait, ring.armor_weight)
        self.assertEqual(blanks, (None, None, None, None))
        self.assertNotIn("emoji", to_dict(self.export)["equipment"]["items"][0])

    def test_weapon_names_only_for_confirmed_values(self) -> None:
        blade, dagger, mystery = self.export.equipment.items[2:]
        self.assertEqual((blade.weapon_name, blade.weapon_type), ("dagger", 11))
        self.assertEqual((dagger.weapon_name, dagger.weapon_type), ("dagger", 11))
        # an unconfirmed value keeps its number for tools and gets no invented name
        self.assertEqual((mystery.weapon_name, mystery.weapon_type), (None, 99))

    def test_numbers_for_tools_are_kept_in_json_but_zero_style_is_not(self) -> None:
        items = to_dict(self.export)["equipment"]["items"]
        blade = items[2]
        self.assertEqual(
            (blade["bind_type"], blade["style"], blade["weapon_name"]), (2, 3, "dagger")
        )
        self.assertNotIn("style", items[0])

    def test_build_notes_and_play_style(self) -> None:
        self.assertEqual(self.export.build_notes, "Solo trials. Wants more sustain.")
        self.assertEqual(self.export.play_style, "solo_self_sufficient")
        # modelled, so they are not repeated in `extra`
        self.assertNotIn("customNotes", self.export.extra)
        self.assertNotIn("playStyle", self.export.extra)

    def test_blank_notes_are_none(self) -> None:
        export = CharacterExport.from_document(
            {"character": {"name": "X"}, "customNotes": "  ", "playStyle": ""}
        )
        self.assertIsNone(export.build_notes)
        self.assertIsNone(export.play_style)

    def test_gear_score_and_sets(self) -> None:
        eq = self.export.equipment
        self.assertEqual(eq.gear_score, 258)
        bonus = eq.sets[0].bonuses[0]
        self.assertEqual(bonus.text, "(2 items) Adds 657 Critical Chance")
        self.assertIs(bonus.active, False)

    def test_skill_bars(self) -> None:
        bars = self.export.skill_bars
        self.assertEqual((bars.active_bar, bars.unspent_skill_points), ("Main", 3))
        bar = bars.bars[0]
        self.assertEqual(bar.name, "Front Bar (Main Hand)")
        self.assertEqual((bar.ultimate.name, bar.ultimate.ability_id), ("Big Ult", 99))
        self.assertTrue(bar.abilities[1].is_crafted)

    def test_champion_points_merge_max_points(self) -> None:
        cp = self.export.champion_points
        self.assertEqual((cp.total, cp.spent, cp.unspent), (1000, 990, 10))
        star = cp.disciplines[0].stars[0]
        self.assertEqual(
            (star.name, star.points, star.max_points, star.kind), ("Star", 20, 50, "slottable")
        )

    def test_other_topics_pass_through(self) -> None:
        self.assertEqual(set(self.export.extra), {"antiquities", "currency"})
        self.assertEqual(self.export.extra["currency"], {"gold": 5})
        self.assertEqual(self.export.exported_at, 1760000000)
        self.assertEqual(self.export.meta["addonVersion"], "test")

    def test_missing_topics_are_none_not_errors(self) -> None:
        bare = CharacterExport.from_document({"character": {"name": "Only Name"}})
        self.assertEqual(bare.character.name, "Only Name")
        self.assertIsNone(bare.stats)
        self.assertIsNone(bare.equipment)
        self.assertIsNone(bare.skill_bars)
        self.assertIsNone(bare.champion_points)
        self.assertEqual(bare.extra, {})

    def test_bare_data_table_is_accepted(self) -> None:
        export = CharacterExport.from_document(DATA)
        self.assertEqual(export.character.name, "Test Character")
        self.assertIsNone(export.exported_at)

    def test_not_a_data_export(self) -> None:
        with self.assertRaisesRegex(ValueError, "no 'character' topic"):
            CharacterExport.from_document({"data": {"stats": {}}})


class RenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.export = CharacterExport.from_document(DOCUMENT)

    def test_to_dict_prunes_empties_but_keeps_zero_and_false(self) -> None:
        result = to_dict(self.export)
        self.assertNotIn("stats_missing", result)
        self.assertNotIn("account_missing", result["character"])
        ring = result["equipment"]["items"][1]
        self.assertNotIn("set_name", ring)
        self.assertEqual(ring["armor_type"], 0)
        self.assertIs(result["equipment"]["sets"][0]["bonuses"][0]["active"], False)

    def test_to_dict_can_leave_out_extra(self) -> None:
        self.assertIn("extra", to_dict(self.export))
        self.assertNotIn("extra", to_dict(self.export, include_extra=False))

    def test_json_round_trips(self) -> None:
        loaded = json.loads(to_json(self.export))
        self.assertEqual(loaded["character"]["name"], "Test Character")
        self.assertEqual(loaded["extra"]["currency"], {"gold": 5})

    def test_lean_markdown(self) -> None:
        text = to_lean_markdown(self.export)
        for expected in (
            "# Test Character",
            "Templar | Orc | Female | Level 50 | CP 1,000",
            "Played: 1d 1h",
            "Health 30,000 | Magicka 25,000 | Stamina 18,000",
            "Crit damage 86%",
            "- Head: Test Helm (Test Set, Epic, Divines, medium armor, "
            "Maximum Magicka Enchantment)",
            "- Test Set (1 piece)",
            "## Build notes\nSolo trials. Wants more sustain.",
            "Play style: solo self sufficient",
            "- Main Hand: Odd Blade (dagger)",
            "- Off Hand: Test Dagger\n",
            "- Backup Main Hand: Mystery Weapon\n",
            "(2 items) Adds 657 Critical Chance (inactive)",
            "- Front Bar (Main Hand): First | Second | Ultimate: Big Ult",
            "- Warfare (100): Star 20*",
        ):
            self.assertIn(expected, text)
        self.assertNotIn("|c", text)
        self.assertNotIn("Empty", text)

    def test_lean_markdown_never_shows_ids_or_unnamed_enums(self) -> None:
        text = to_lean_markdown(self.export)
        # game ids (the ultimate's id is 99), unnamed enums (weapon type 99, bind type, style)
        self.assertNotRegex(text, r"\b99\b")
        unnamed = (r"bind[_ ]?type", r"weapon_type", r"armor_type", r"skill_?id", r"ability_?id")
        for field in unnamed:
            self.assertNotRegex(text, "(?i)" + field)
        self.assertNotRegex(text, r"(?i)\bstyle[_ ]?\d")
        # the same numbers are still available to tools in the JSON
        document = json.loads(to_json(self.export))
        bar = document["skill_bars"]["bars"][0]
        self.assertEqual(bar["ultimate"]["ability_id"], 99)
        self.assertEqual(document["equipment"]["items"][4]["weapon_type"], 99)

    def test_lean_markdown_without_optional_topics(self) -> None:
        text = to_lean_markdown(CharacterExport.from_document({"character": {"name": "Solo"}}))
        self.assertTrue(text.startswith("# Solo"))
        self.assertNotIn("## Gear", text)


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.file = self.dir / "x_data.json"
        self.file.write_text(json.dumps(DOCUMENT), encoding="utf-8")

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_markdown_to_stdout(self) -> None:
        code, out, _ = self.run_cli(str(self.file))
        self.assertEqual(code, 0)
        self.assertIn("# Test Character", out)

    def test_json_to_file(self) -> None:
        target = self.dir / "out.json"
        code, _, err = self.run_cli(str(self.file), "--format", "json", "--out", str(target))
        self.assertEqual(code, 0)
        self.assertIn("Wrote", err)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["character"]["level"], 50)

    def test_missing_file_is_an_error_message(self) -> None:
        code, _, err = self.run_cli(str(self.dir / "nope.json"))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_wrong_kind_of_export(self) -> None:
        self.file.write_text(json.dumps({"data": {"stats": {}}}), encoding="utf-8")
        code, _, err = self.run_cli(str(self.file))
        self.assertEqual(code, 1)
        self.assertIn("no 'character' topic", err)


@unittest.skipUnless(os.environ.get("CM_DUMP"), "set CM_DUMP to a real *_data_*.json to run")
class RealDumpTest(unittest.TestCase):
    def test_real_export_loads_and_renders(self) -> None:
        export = load_export(os.environ["CM_DUMP"])
        self.assertTrue(export.character.name)
        self.assertGreater(len(export.equipment.items), 0)
        self.assertGreater(len(export.skill_bars.bars), 0)
        self.assertGreater(len(export.champion_points.disciplines), 0)
        text = to_lean_markdown(export)
        self.assertNotIn("|c", text)
        self.assertGreater(len(to_json(export)), len(text))


if __name__ == "__main__":
    unittest.main()
