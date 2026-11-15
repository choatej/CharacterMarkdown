"""Tests for the configuration tree: semantics on a small tree, coverage on the real one."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.cmconfig import ConfigCollection, ConfigData, read_lua_defaults
from tools.cmconfig.model import DEFAULT_TREE
from tools.cmdata.export import DERIVED_TOPICS, OTHER_MODELLED, TOPICS

SMALL = {
    "schema": 1,
    "sections": [
        {
            "id": "a",
            "label": "A",
            "children": [
                {
                    "id": "b",
                    "label": "B",
                    "settings": ["includeB"],
                    "topics": ["bee"],
                    "children": [
                        {"id": "c", "label": "C", "kind": "detail", "settings": ["showC"]},
                        {"id": "d", "label": "D", "topics": ["dee.sub"]},
                    ],
                },
                {"id": "e", "label": "E", "settings": ["includeE"], "topics": ["eee"]},
            ],
        },
        {"id": "f", "label": "F", "domain": "format", "children": [{"id": "g", "label": "G", "settings": ["x"]}]},
    ],
}


def small() -> ConfigCollection:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "tree.json"
        path.write_text(json.dumps(SMALL), encoding="utf-8")
        return ConfigCollection.load(path)


class StructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = small()

    def test_paths_and_lookup(self) -> None:
        self.assertEqual([i.path for i in self.tree.items()], ["a", "a.b", "a.b.c", "a.b.d", "a.e", "f", "f.g"])
        self.assertEqual(self.tree["a.b.c"].label, "C")
        self.assertIn("a.e", self.tree)
        self.assertEqual(len(self.tree), 7)
        with self.assertRaises(KeyError):
            self.tree["a.zzz"]

    def test_parent_children_siblings(self) -> None:
        b = self.tree["a.b"]
        self.assertEqual(b.get_parent().path, "a")  # type: ignore[union-attr]
        self.assertIsNone(self.tree["a"].get_parent())
        self.assertEqual([c.id for c in b.get_children()], ["c", "d"])
        self.assertEqual([s.id for s in b.siblings()], ["e"])
        self.assertTrue(self.tree["a.e"].is_leaf)
        self.assertFalse(b.is_leaf)

    def test_ancestors_descendants_depth(self) -> None:
        c = self.tree["a.b.c"]
        self.assertEqual([a.path for a in c.ancestors()], ["a.b", "a"])
        self.assertEqual([d.path for d in self.tree["a"].descendants()], ["a.b", "a.b.c", "a.b.d", "a.e"])
        self.assertEqual((self.tree["a"].depth, c.depth), (0, 2))

    def test_domain_is_inherited_and_kind_defaults_to_item(self) -> None:
        self.assertEqual(self.tree["a.b"].domain, "content")
        self.assertEqual(self.tree["f.g"].domain, "format")
        self.assertEqual(self.tree["a.b"].kind, "item")
        self.assertEqual(self.tree["a.b.c"].kind, "detail")

    def test_lookups_by_setting_and_topic(self) -> None:
        self.assertEqual(self.tree.by_setting("showC").path, "a.b.c")  # type: ignore[union-attr]
        self.assertIsNone(self.tree.by_setting("nope"))
        self.assertEqual(self.tree.topics(), {"bee", "dee", "eee"})
        self.assertEqual([i.path for i in self.tree.items_for_topic("dee")], ["a.b.d"])

    def test_duplicate_setting_is_rejected(self) -> None:
        bad = json.loads(json.dumps(SMALL))
        bad["sections"][0]["children"][1]["settings"] = ["includeB"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tree.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "includeB"):
                ConfigCollection.load(path)

    def test_bad_ids_are_rejected(self) -> None:
        for bad_id in ("", "a.b"):
            doc = {"schema": 1, "sections": [{"id": bad_id, "label": "x"}]}
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "tree.json"
                path.write_text(json.dumps(doc), encoding="utf-8")
                with self.assertRaises(ValueError):
                    ConfigCollection.load(path)


class ValueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = small()
        self.data = ConfigData(self.tree)

    def test_everything_is_on_without_defaults(self) -> None:
        self.assertTrue(all(i.is_effective(self.data) for i in self.tree.items()))
        self.assertEqual(self.tree["a"].state(self.data), "on")

    def test_off_parent_switches_off_descendants(self) -> None:
        self.data.set("a.b", False)
        self.assertFalse(self.tree["a.b"].is_effective(self.data))
        self.assertTrue(self.tree["a.b.c"].is_enabled(self.data))  # stored value is untouched
        self.assertFalse(self.tree["a.b.c"].is_effective(self.data))  # but it cannot take effect
        self.assertEqual(self.tree["a.b.c"].state(self.data), "off")

    def test_state_is_mixed_when_something_below_is_off(self) -> None:
        self.data.set("a.b.c", False)
        self.assertEqual(self.tree["a.b"].state(self.data), "mixed")
        self.assertEqual(self.tree["a"].state(self.data), "mixed")
        self.assertEqual(self.tree["a.e"].state(self.data), "on")

    def test_cascade_applies_to_the_whole_subtree(self) -> None:
        self.tree["a.b"].cascade(self.data, False)
        self.assertEqual([i.path for i in self.tree.items() if not self.data.get(i)], ["a.b", "a.b.c", "a.b.d"])
        self.tree["a"].cascade(self.data, True)
        self.assertTrue(all(self.data.get(i) for i in self.tree["a"].walk()))

    def test_select_turns_on_the_item_its_subtree_and_its_ancestors(self) -> None:
        data = ConfigData(self.tree, {i.path: False for i in self.tree.items()})
        self.tree["a.b"].select(data)
        self.assertEqual(sorted(p for p, v in data.values.items() if v), ["a", "a.b", "a.b.c", "a.b.d"])

    def test_saved_form_holds_only_changes_and_survives_old_paths(self) -> None:
        self.data.set("a.e", False)
        self.data.set("a.b", True)  # same as the default
        self.assertEqual(self.data.to_dict(), {"a.e": False})
        rebuilt = ConfigData.from_dict(self.tree, {"a.e": False, "gone.path": False, "a.b": "yes"})
        self.assertEqual(rebuilt.to_dict(), {"a.e": False})

    def test_copy_is_independent(self) -> None:
        copy = self.data.copy()
        copy.set("a", False)
        self.assertTrue(self.data.get("a"))


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = small()

    def test_legacy_values_land_on_their_items(self) -> None:
        data = self.tree.data_from_legacy({"includeB": True, "showC": False, "includeE": False, "x": True})
        self.assertEqual(
            {p: v for p, v in data.values.items()},
            {"a": True, "a.b": True, "a.b.c": False, "a.b.d": True, "a.e": False, "f": True, "f.g": True},
        )

    def test_group_without_setting_is_on_when_any_child_is(self) -> None:
        data = self.tree.data_from_legacy({"includeB": False, "showC": False, "includeE": False, "x": False})
        self.assertFalse(data.get("a"))
        data = self.tree.data_from_legacy({"includeB": False, "showC": False, "includeE": True, "x": False})
        self.assertTrue(data.get("a"))

    def test_leaf_without_setting_follows_its_parent(self) -> None:
        off = self.tree.data_from_legacy({"includeB": False})
        self.assertFalse(off.get("a.b.d"))
        on = self.tree.data_from_legacy({"includeB": True})
        self.assertTrue(on.get("a.b.d"))

    def test_back_to_legacy_flags_uses_effective_values(self) -> None:
        data = self.tree.data_from_legacy({"includeB": False, "showC": True, "includeE": True, "x": True})
        self.assertEqual(
            self.tree.legacy_settings(data),
            {"includeB": False, "showC": False, "includeE": True, "x": True},
        )

    def test_defaults_come_from_legacy_defaults(self) -> None:
        self.tree.with_defaults({"includeB": True, "showC": False, "includeE": True, "x": True})
        data = ConfigData(self.tree)
        self.assertFalse(data.get("a.b.c"))
        self.assertEqual(data.to_dict(), {})
        data.set("a.b.c", True)
        self.assertEqual(data.to_dict(), {"a.b.c": True})


class SelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = small()

    def test_from_paths_selects_subtrees_only(self) -> None:
        data = self.tree.from_paths(["a.b"])
        self.assertEqual(self.tree.topics_for(data), {"bee", "dee"})
        self.assertFalse(self.tree["a.e"].is_effective(data))
        self.assertEqual(self.tree["a"].state(data), "mixed")

    def test_selected_paths_is_the_shortest_cover(self) -> None:
        self.assertEqual(self.tree.selected_paths(self.tree.from_paths(["a.b", "a.e"])), ["a"])
        self.assertEqual(self.tree.selected_paths(self.tree.from_paths(["a.b.c", "a.e"])), ["a.b.c", "a.e"])
        self.assertEqual(self.tree.selected_paths(self.tree.from_paths([])), [])

    def test_paths_round_trip(self) -> None:
        for paths in (["a.b"], ["a.b.c", "a.e"], ["a", "f"], ["f.g"]):
            data = self.tree.from_paths(paths)
            again = self.tree.from_paths(self.tree.selected_paths(data))
            self.assertEqual(again.values, data.values, paths)

    def test_topics_follow_the_domain(self) -> None:
        data = ConfigData(self.tree)
        self.assertEqual(self.tree.topics_for(data), {"bee", "dee", "eee"})
        self.assertEqual(self.tree.topics_for(data, domain="format"), set())

    def test_unknown_path_is_an_error(self) -> None:
        with self.assertRaises(KeyError):
            self.tree.from_paths(["nope"])

    def test_render_marks_state(self) -> None:
        data = self.tree.from_paths(["a.b.c"])
        text = self.tree.render(data)
        self.assertIn("[-] a: A", text)
        self.assertIn("    [x] c: C  (detail)", text)
        self.assertIn("    [ ] d: D", text)


class RealTreeTests(unittest.TestCase):
    """The shipped tree against the add-on's actual settings and the export's actual topics."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = ConfigCollection.load(DEFAULT_TREE)
        cls.defaults = read_lua_defaults()

    def test_every_boolean_setting_has_one_item(self) -> None:
        booleans = {k for k, v in self.defaults.items() if isinstance(v, bool)}
        self.assertEqual(booleans - self.tree.settings(), set(), "settings with no place in the tree")
        self.assertEqual(self.tree.settings() - set(self.defaults), set(), "tree names an unknown setting")

    def test_settings_left_out_are_explained(self) -> None:
        left_out = {k for k in self.defaults if k not in self.tree.settings()}
        self.assertEqual(left_out, set(self.tree.not_in_tree))

    def test_every_export_topic_is_claimed(self) -> None:
        known = {*TOPICS, *OTHER_MODELLED, *DERIVED_TOPICS}
        self.assertEqual(known - self.tree.topics(), set(), "topics no item feeds")
        self.assertEqual(self.tree.topics() - known, set(), "items name a topic the export does not have")

    def test_top_level_topics_are_fed_by_content_or_profile_items(self) -> None:
        for topic in self.tree.topics():
            domains = {i.domain for i in self.tree.items_for_topic(topic)}
            self.assertFalse(domains == {"format"}, f"{topic} is only fed by format items")

    def test_every_item_has_a_label_and_ids_are_plain(self) -> None:
        for item in self.tree.items():
            self.assertTrue(item.label.strip(), item.path)
            self.assertRegex(item.id, r"^[a-z][a-z0-9_]*$", item.path)

    def test_defaults_round_trip_to_the_legacy_flags(self) -> None:
        """Migrating the add-on's defaults and converting back must lose nothing that can take effect."""
        data = self.tree.data_from_legacy(self.defaults)
        flags = self.tree.legacy_settings(data)
        for key, value in flags.items():
            if value != self.defaults[key]:
                # the only allowed difference: a detail flag that is on while its parent is off
                item = self.tree.by_setting(key)
                self.assertIsNotNone(item)
                self.assertTrue(self.defaults[key] and not value, key)
                self.assertTrue(any(not a.is_enabled(data) for a in item.ancestors()), key)  # type: ignore[union-attr]

    def test_defaults_match_the_panel_semantics_for_a_few_known_items(self) -> None:
        data = self.tree.data_from_legacy(self.defaults)
        self.assertTrue(data.get("build.equipment"))
        self.assertFalse(data.get("activities.antiquities"))
        self.assertFalse(data.get("build.champion_points.diagram"))

    def test_legacy_flags_round_trip_through_the_tree_for_every_single_toggle(self) -> None:
        """Flip each setting in isolation; the tree must reproduce the effect the old flags had."""
        for key, value in self.defaults.items():
            if not isinstance(value, bool):
                continue
            changed = {**self.defaults, key: not value}
            data = self.tree.data_from_legacy(changed)
            item = self.tree.by_setting(key)
            self.assertEqual(item.is_enabled(data), not value, key)  # type: ignore[union-attr]

    def test_selecting_a_topic_path_gives_that_topic(self) -> None:
        data = self.tree.from_paths(["activities.antiquities"])
        self.assertEqual(self.tree.topics_for(data), {"antiquities"})
        data = self.tree.from_paths(["crafting"])
        self.assertEqual(self.tree.topics_for(data), {"crafting", "styles"})

    def test_the_readme_table_is_current(self) -> None:
        from tools.cmconfig.__main__ import README, readme_with_table

        text = README.read_text(encoding="utf-8")
        tree = ConfigCollection.load(DEFAULT_TREE).with_defaults(self.defaults)
        self.assertEqual(
            text,
            readme_with_table(text, tree.mapping_table()),
            "data/config/README.md is stale: run python3 -m tools.cmconfig --update-readme",
        )

    def test_a_selected_path_list_is_stable(self) -> None:
        paths = ["activities.antiquities", "crafting.knowledge.recipes", "inventory.currency"]
        data = self.tree.from_paths(paths)
        self.assertEqual(sorted(self.tree.selected_paths(data)), sorted(paths))


if __name__ == "__main__":
    unittest.main()
