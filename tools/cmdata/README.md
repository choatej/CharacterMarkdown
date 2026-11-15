# tools/cmdata - typed model for `/cm save data` exports

Reads the JSON that `tools.sv_export` writes for a structured export and gives you Python objects and
other output formats. Standard library only, Python 3.10+.

```
python3 -m tools.cmdata Name_data_2026-11-14.json                # compact Markdown on stdout
python3 -m tools.cmdata Name_data_2026-11-14.json --format json   # typed, de-decorated JSON
python3 -m tools.cmdata FILE --format md --out build.md
```

```python
from tools.cmdata import load_export, to_json, to_lean_markdown

export = load_export("Name_data_2026-11-14.json")
export.character.class_name            # "Templar"
[i.name for i in export.equipment.items]
export.equipment.sets[0].bonuses[0].text   # colour codes already removed
export.extra["antiquities"]            # topics without a typed model, untouched
print(to_lean_markdown(export))
```

## What is modelled

| Topic | Class | Notes |
|-------|-------|-------|
| `character` | `Character` | identity, level, champion points, attributes, class skill lines |
| `customNotes`, `playStyle` | `build_notes`, `play_style` | the player's own notes for the AI; shown first in the Markdown |
| `stats` | `Stats` | resources, power, crit, penetration, resistance; the detailed block stays in `advanced` |
| `equipment` | `Equipment` | worn items (empty slots dropped), active sets with bonus text, trait counts |
| `skillBar` | `SkillBars` | both bars with ability ids, slots and ultimates |
| `cp` | `ChampionPoints` | disciplines and invested stars with their maximum |

Every other topic (`crafting`, `antiquities`, `styles`, ...) is kept as it came in, under
`CharacterExport.extra`, so nothing in the export is lost.

## What is cleaned

- ESO colour codes in text (`|cffffff657|r`) are removed.
- Emoji and other decoration the Markdown output adds (`emoji`, `qualityEmoji`, the emoji in bar names)
  are dropped.
- "Nothing here" markers (`""`, `"-"`, `"None"`, `false`) become `None`, and `None` / empty values are
  left out of `to_dict` / `to_json` (`0` and `false` are kept).
- Game enums come with a readable name next to the number, so nothing relies on knowing the game's
  constants: armor weight (`armorType` 1-3) as `light` / `medium` / `heavy`, and weapon type as
  `weapon_name`. Only values that have been checked against a real export are named (so far dagger
  and lightning staff); any other weapon type keeps its number in the JSON and is simply left out
  of the Markdown, because the item name already says what it is.
- Two kinds of number are for tools only and appear in the JSON, never in the Markdown: enum numbers
  with no name (`bind_type`, `style`) and game ids (ability and skill ids). A language model cannot
  tell what `style 3` means, and the names already carry the meaning.

## Adding an output format

Write a function that takes a `CharacterExport` and returns text, and add it to `FORMATS` in
`render.py`.

## Tests

```
python3 -m unittest tools.cmdata.test_model
CM_DUMP=path/to/Name_data_2026-11-14.json python3 -m unittest tools.cmdata.test_model   # also check a real export
```
