# Configuration tree

`tree.json` describes what a CharacterMarkdown export can contain as a tree. It replaces a flat list of
73 on/off settings with something a user can select from: switch a node off and everything under it
goes off; select one node and only that subtree (and the path to it) is on.

```
python3 -m tools.cmconfig                 # the tree
python3 -m tools.cmconfig --defaults      # the tree, marked as the add-on's defaults have it
python3 -m tools.cmconfig --update-readme # refresh the table below after editing tree.json
python3 -m tools.cmconfig.test_tree       # checks (also part of `task dev:test:python`)
```

## Structure and values are separate

- **Structure** (`tree.json`) is the same for every user: ids, labels, which legacy setting each node
  replaces, which export topics it feeds. At run time it becomes `ConfigItem` objects with parent and
  child links. It is never saved.
- **Values** are one flat table, `path -> bool`, such as `{"activities.antiquities": true}`. This is the only
  part to save, and only the entries that differ from the default need saving. SavedVariables cannot
  hold functions, metatables or the cycles a parent link creates, so this split is also what makes the
  design work in Lua.

`tools/cmconfig/model.py` is the reference implementation: `ConfigCollection` (the holder and lookups),
`ConfigItem` (`get_parent`, `get_children`, `ancestors`, `descendants`, `cascade`, `select`,
`is_effective`, `state`) and `ConfigData` (the values).

## Rules

- A node is **effective** when it and every ancestor are on. A child's stored value survives its parent
  being switched off, so switching the parent back on restores it.
- Think of nodes as gates: a node's stored value opens or closes its own gate and never touches the
  gates below it. Setting a parent does not change its children; `cascade` is the explicit bulk action.
- **Store the toggle, derive the effective value.** `resolve(data)` works every node's effective value
  out top-down in one pass (`effective = toggle and parent's effective`) and returns a read-only
  snapshot. Runtime code reads `resolved[path]`. The snapshot lives in memory only, never in
  SavedVariables (a saved copy could go stale), and is rebuilt after any edit.
- A node's **state** is `on`, `off`, or `mixed` (on, with something under it not effective).
- **Domains**: `content` (what the data contains), `profile` (the player's own text) and `format` (how
  the Markdown renderer lays it out; a data export has no use for these). Child nodes inherit their
  section's domain. Formatting that is not about content stays in `format`; when formatting moves to the
  Python post-processor these items leave the add-on.
- **Kinds**: `item` is something to include; `detail` asks for more depth of its parent (the old
  `show...Detailed` settings).
- Selecting by path (`--topics`-style): `["activities.antiquities", "crafting.knowledge.recipes"]` means
  those subtrees. `selected_paths` gives the shortest list that reproduces a selection.

## Migrating the old settings

`data_from_legacy(settings)` maps the flat table onto the tree, and `legacy_settings(data)` maps back, so
the generators that still read the old flags keep working while the panel moves to the tree:

- a node with a legacy setting takes that value;
- a node without one that has children is on when any child is;
- a leaf without one follows its nearest ancestor that has a setting.

Going back uses the effective value. One difference is intended: a detail flag that was on under a parent
that was off (for example `showAllAchievements`, on by default, with achievements off) comes back off.
The old panel greyed such a flag out but left its stored value; the tree makes the effect explicit.

`detectedOS` is the only default not in the tree (set by the add-on, not chosen by the user).

## Mapping

Every legacy setting appears exactly once; every export topic is fed by at least one node. The tests enforce
both against `src/settings/Defaults.lua` and `tools/cmdata`. The table is generated.

<!-- mapping:begin -->
| Path | Label | Kind | Legacy setting | Default | Export topics |
|---|---|---|---|---|---|
| `character` | Character | item |  | on |  |
| `character.identity` | Identity | item | `includeCharacterAttributes` | on | `character`, `characterAttributes` |
| `character.identity.mundus` | Mundus stone | item |  | on | `mundus` |
| `character.location` | Current location | item | `includeLocation` | on | `location` |
| `character.role` | Role | item | `includeRole` | on | `role` |
| `character.titles` | Titles | item | `includeTitlesHousing` | off | `titles`, `titlesHousing` |
| `character.housing` | Housing | item | `includeHousing` | off | `housing` |
| `character.appearance` | Appearance | item | `includeAppearance` | off | `appearance` |
| `character.dlc` | DLC and chapter access | item | `includeDLCAccess` | off | `dlc` |
| `character.companion` | Companion | item | `includeCompanion` | on | `companion` |
| `character.progression` | Progression | item | `includeProgression` | off | `progression` |
| `character.riding` | Riding skills | item | `includeRidingSkills` | off | `riding` |
| `build` | Build | item |  | on |  |
| `build.champion_points` | Champion points | item | `includeChampionPoints` | on | `cp` |
| `build.champion_points.diagram` | Mermaid diagram | detail | `includeChampionDiagram` | off |  |
| `build.skills` | Skills | item |  | on |  |
| `build.skills.bars` | Skill bars | item | `includeSkillBars` | on | `skillBar` |
| `build.skills.progress` | Skill line progress | item | `includeSkills` | on | `skill` |
| `build.skills.progress.morphs` | Available morphs | detail | `includeSkillMorphs` | off | `skillMorphs` |
| `build.skills.alliance_war` | Alliance War skill lines | detail | `showAllianceWarSkills` | off |  |
| `build.equipment` | Equipment | item | `includeEquipment` | on | `equipment` |
| `build.equipment.enhancement` | Enhancement analysis | detail | `includeEquipmentEnhancement` | off |  |
| `build.equipment.enhancement.analysis` | Detailed analysis | detail | `showEquipmentAnalysis` | off |  |
| `build.equipment.enhancement.recommendations` | Recommendations | detail | `showEquipmentRecommendations` | off |  |
| `build.stats` | Combat stats | item |  | on |  |
| `build.stats.basic` | Basic stats | item | `includeBasicCombatStats` | on | `stats` |
| `build.stats.advanced` | Advanced stats | item | `includeAdvancedStats` | on | `stats.advanced` |
| `build.stats.attributes` | Attribute distribution | item | `includeAttributes` | on | `character.attributes` |
| `build.buffs` | Active buffs | item | `includeBuffs` | on | `buffs` |
| `build.armory` | Armory builds | item | `includeArmoryBuilds` | off | `armoryBuilds` |
| `inventory` | Inventory | item |  | on |  |
| `inventory.space` | Inventory space | item | `includeInventory` | on | `inventory` |
| `inventory.space.bag_items` | Backpack items | detail | `showBagContents` | off | `inventory.bagItems` |
| `inventory.space.bank_items` | Bank items | detail | `showBankContents` | off | `inventory.bankItems` |
| `inventory.space.crafting_bag_items` | Crafting bag items | detail | `showCraftingBagContents` | off | `inventory.craftingBagItems` |
| `inventory.currency` | Currency and resources | item | `includeCurrency` | on | `currency` |
| `crafting` | Crafting | item |  | on |  |
| `crafting.knowledge` | Crafting knowledge | item | `includeCrafting` | on | `crafting` |
| `crafting.knowledge.motifs` | Motifs | item | `includeMotifs` | on | `crafting.motifs` |
| `crafting.knowledge.motifs.detailed` | Per-chapter detail | detail | `showMotifsDetailed` | off |  |
| `crafting.knowledge.styles` | Outfit styles | item | `includeStyles` | on | `styles`, `crafting.styles` |
| `crafting.knowledge.styles.detailed` | Per-style detail | detail | `showStylesDetailed` | off |  |
| `crafting.knowledge.recipes` | Recipes | item | `includeRecipes` | on | `crafting.recipes` |
| `crafting.knowledge.recipes.detailed` | Per-recipe lists | detail | `showRecipesDetailed` | off |  |
| `crafting.knowledge.item_sets` | Item set collection | item | `includeItemSetCollection` | off | `crafting.itemSetCollection` |
| `collections` | Collections | item |  | on |  |
| `collections.collectibles` | Collectibles | item | `includeCollectibles` | on | `collectibles` |
| `collections.collectibles.detailed` | Full lists | detail | `showCollectiblesDetailed` | off |  |
| `activities` | Activities | item |  | off |  |
| `activities.achievements` | Achievements | item | `includeAchievements` | off | `achievements` |
| `activities.achievements.all` | Completed as well as in progress | detail | `showAllAchievements` | on |  |
| `activities.achievements.criteria` | Criteria detail | detail | `includeAchievementDetail` | off |  |
| `activities.antiquities` | Antiquities | item | `includeAntiquities` | off | `antiquities` |
| `activities.antiquities.sets` | Per-set detail | detail | `showAntiquitiesDetailed` | off |  |
| `activities.quests` | Quests | item | `includeQuests` | off | `quests` |
| `activities.quests.categories` | Per-category detail | detail | `showQuestsDetailed` | off |  |
| `activities.quests.all` | All quests, not only active | detail | `showAllQuests` | off |  |
| `activities.undaunted` | Undaunted pledges | item | `includeUndauntedPledges` | off | `undauntedPledges` |
| `activities.world_progress` | World progress | item | `includeWorldProgress` | off | `worldProgress` |
| `activities.endless_dungeon` | Endless Dungeon | item | `includeEndlessDungeon` | off |  |
| `activities.pvp` | PvP | item |  | off |  |
| `activities.pvp.overview` | PvP overview | item | `includePvP` | off | `pvp` |
| `activities.pvp.statistics` | PvP statistics | item | `includePvPStats` | off | `pvp.stats` |
| `activities.pvp.statistics.progression` | Rank progress | detail | `showPvPProgression` | off |  |
| `activities.pvp.statistics.campaign_rewards` | Campaign rewards | detail | `showCampaignRewards` | off |  |
| `activities.pvp.statistics.leaderboards` | Leaderboards | detail | `showLeaderboards` | off |  |
| `activities.pvp.statistics.battlegrounds` | Battlegrounds | detail | `showBattlegrounds` | off |  |
| `activities.pvp.statistics.detailed` | Everything | detail | `showDetailedPvP` | off |  |
| `activities.pvp.vengeance` | Vengeance loadout | item | `includeVengeance` | off | `pvp.vengeance` |
| `social` | Social | item |  | on |  |
| `social.guilds` | Guild membership | item | `includeGuilds` | on | `guilds` |
| `social.mail` | Mail | item | `includeMail` | off | `mail` |
| `profile` | Your own text | item |  | on |  |
| `profile.build_notes` | Build notes | item | `includeBuildNotes` | on | `customNotes` |
| `profile.play_style` | Play style | item |  | on | `playStyle` |
| `layout` | Markdown layout | item |  | on |  |
| `layout.header` | Header | item | `includeHeader` | on |  |
| `layout.footer` | Footer | item | `includeFooter` | on |  |
| `layout.table_of_contents` | Table of contents | item | `includeTableOfContents` | on |  |
| `layout.attention_needed` | Attention needed | item | `includeAttentionNeeded` | on |  |
| `layout.quick_stats` | Quick stats | item | `includeQuickStats` | on |  |
| `layout.general_overview` | General overview | item | `includeGeneral` | on |  |
| `links` | UESP links | item |  | on |  |
| `links.abilities` | Abilities | item | `enableAbilityLinks` | on |  |
| `links.sets` | Sets | item | `enableSetLinks` | on |  |
| `links.motifs` | Motifs | item | `enableMotifLinks` | on |  |
| `links.styles` | Styles | item | `enableStyleLinks` | on |  |
| `links.recipes` | Recipes | item | `enableRecipeLinks` | on |  |
<!-- mapping:end -->
