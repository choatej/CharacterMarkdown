# tools/cmdata - typed model for `/cm save data` exports

Reads the JSON that `tools.sv_export` writes for a structured export and gives you Python objects
and other output formats. Standard library only, Python 3.10+.

```
python3 -m tools.cmdata Name_data_2026-11-14.json                     # the build, as compact Markdown
python3 -m tools.cmdata FILE --topics antiquities                      # one slice
python3 -m tools.cmdata FILE --topics antiquities,crafting,inventory   # several
python3 -m tools.cmdata FILE --topics all                              # everything, still compact
python3 -m tools.cmdata FILE --format json                             # typed, de-duplicated JSON
python3 -m tools.cmdata FILE --format md --out build.md
```

```python
from tools.cmdata import load_export, to_json, to_lean_markdown

export = load_export("Name_data_2026-11-14.json")
export.character.class_name  # "Templar"
[i.name for i in export.equipment.items]
export.equipment.sets[0].bonuses[0].text  # colour codes already removed
for lead in export.antiquities.leads_expiring_within():  # default: one week
    print(lead.name, lead.lead_seconds_remaining)
print(to_lean_markdown(export, ["antiquities", "crafting"]))
```

## What is modelled

Every topic the add-on collects has a typed class. A topic that was not collected (the user's
settings left it out) is `None`.

| Topic | Attribute | Notes |
|-------|-----------|-------|
| `character` | `character` | identity, level, champion points, attributes, class skill lines |
| `customNotes`, `playStyle` | `build_notes`, `play_style` | the player's own text for the AI |
| `stats` | `stats` | resources, power, crit, penetration, resistance; detail kept in `advanced` |
| `equipment` | `equipment` | worn items (empty slots dropped), active sets with bonus text, traits |
| `skillBar` | `skill_bars` | both bars with abilities and ultimates |
| `cp` | `champion_points` | disciplines and invested stars with their maximum |
| `antiquities` | `antiquities` | every antiquity once, with lead timers; `leads()`, `leads_expiring_within()` |
| `skill`, `skillMorphs` | `skill_lines`, `skill_morphs` | skill line progress, chosen morph per skill |
| `progression` | `progression` | unspent points, vampire / werewolf status |
| `currency` | `currency` | amounts and caps by name |
| `inventory` | `inventory` | capacity and the three item lists, with quality names |
| `collectibles`, `styles` | `collectibles`, `outfit_styles` | owned by kind with totals, outfit style names |
| `titles`, `housing` | `titles`, `housing` | titles owned, houses and the primary home |
| `crafting` | `crafting` | motifs (missing chapters), recipes, trait research, item set progress |
| `quests`, `armoryBuilds` | `quests`, `armory_builds` | active quests, saved loadouts |
| `worldProgress`, `achievements` | `world_progress`, `achievements` | skyshards, lorebooks, delves; achievement totals |
| `companion`, `pvp`, `guilds` | `companion`, `pvp`, `guilds` | |
| `appearance`, `location`, `riding`, `mundus`, `dlc`, `mail`, `undauntedPledges`, `buffs`, `role` | one attribute each | small topics |

A topic this version has no class for is kept untouched under `CharacterExport.extra`, so nothing is
lost when the add-on gains a topic.

### Repeated data is stored once

The export repeats some information; the model keeps one copy:

- **Antiquities**: each antiquity is listed in its set and again in the active-leads list. Here it
  appears once, and `leads()` derives the leads.
- **Recipes**: listed flat and again grouped by list. Each recipe appears once, with the name of its
  list.
- **`titlesHousing` and `characterAttributes`** are built by the add-on from other topics (titles,
  housing and collectibles; character, mundus, location, riding and buffs). They add no information
  and are not kept.

Together this makes the typed JSON about 20% smaller than the raw data.

## What is cleaned

- ESO colour codes in text (`|cffffff657|r`) are removed, and multi-paragraph bonus text is joined into
  one line.
- Emoji and other decoration the Markdown output adds (`emoji`, `qualityEmoji`, the emoji in bar names)
  are dropped.
- "Nothing here" markers (`""`, `"-"`, `"None"`, `false`) become `None`, and `None` / empty values are
  left out of `to_dict` / `to_json` (`0` and `false` are kept).
- An empty list arrives from the game as `{}`; every class accepts that.
- Game enums come with a readable name next to the number, so nothing relies on knowing the game's
  constants. Armor weight (`armorType` 1-3) is `light` / `medium` / `heavy`, weapon type is
  `weapon_name`, and item quality (inventory) is `quality_name`. Only values checked against a real
  export are named (weapon: dagger and lightning staff; quality 2-5 are confirmed, 0 and 1 follow the
  game's enumeration). Any other value keeps its number in the JSON and is left out of the Markdown.
- Numbers that are only game ids or unnamed enums (ability, skill and craft-type ids, trait ids,
  `bind_type`, `style`) stay in the JSON for tools and never appear in the Markdown. A language model
  cannot tell what `style 3` means, and the names already carry the meaning.

## Markdown sections

`to_lean_markdown(export, sections)` always prints an identity header (class, level, mundus, curse).
By default it prints only the build (`notes`, `stats`, `gear`, `skill_bars`, `champion_points`, about
4 KB). Ask for others by name, or for all of them (about 7 KB for a whole account):

`progression`, `skill_lines`, `antiquities`, `crafting`, `inventory`, `collectibles`, `world`,
`quests`, `achievements`, `currency`, `profile`, `armory`

Handing an AI only the sections a question needs keeps the text small. For example `antiquities`
alone is a few hundred bytes and lists the leads that expire within a week.

## Adding an output format

Write a function that takes a `CharacterExport` and returns text, and add it to `FORMATS` in
`render.py`. To add a Markdown section, add a function to `lean_topics.py` and register it in
`EXTRA_SECTIONS`.

## Tests

```
python3 -m unittest tools.cmdata.test_model tools.cmdata.test_topics
CM_DUMP=path/to/Name_data_2026-11-14.json python3 -m unittest tools.cmdata.test_model tools.cmdata.test_topics
```

The second form also checks a real export (every topic modelled, antiquity and recipe counts agree with
the export's own summary, the typed JSON is smaller than the raw data).
