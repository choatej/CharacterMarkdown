# Fork integration branch (`integration/all`)

**Local use only. Never submit this branch upstream.** It is `upstream/main` plus every branch we have
prepared, merged together so the whole set can be run, tested and installed in the game at once. Each
change also exists as its own small branch for a future PR (see [Submitting upstream](#submitting-upstream)).

- Upstream: `solaegis/CharacterMarkdown` (`upstream` remote). Fork: `choatej/CharacterMarkdown` (`origin`).
- Base: `upstream/main` at `ff6908e` (2026-11-14). Re-check it before submitting anything.
- This file is `README_FORK.md` so it does not touch upstream's `README.md`, which the validators read.
- Status: the one open upstream PR is #3 (docs fix). **Nothing else is to be sent until #3 gets a maintainer
  response**, so the maintainer is not flooded. Drafts are in `~/src/pr-drafts/` (start with
  `00-submission-plan.md`).

## Contents

1. [Why these changes exist](#why-these-changes-exist)
2. [The branches](#the-branches)
3. [Merge order and rebuilding this branch](#merge-order-and-rebuilding-this-branch)
4. [Tools](#tools)
5. [Quality checks](#quality-checks)
6. [Building and installing in the game](#building-and-installing-in-the-game)
7. [Data and files outside the repo](#data-and-files-outside-the-repo)
8. [Submitting upstream](#submitting-upstream)
9. [Gotchas and known issues](#gotchas-and-known-issues)
10. [To do and ideas](#to-do-and-ideas)

## Why these changes exist

The goal is to get a character's data **out of the game and into other tools** (build review, an AI
coach, planning), and to do it reliably.

1. **Copying from the window is the bottleneck.** ESO add-ons cannot write files, so the only way to get an
   export out is to select and copy it chunk by chunk from the window. That is awkward on a keyboard and
   worse on Steam Deck (upstream issue #2). SavedVariables is the one channel the game does write to disk,
   so `/cm save` stores the export there and a Python script turns it into files.
2. **Markdown is not the only format anyone wants.** Once the collected data can be saved as data instead
   of rendered text (`/cm save data`), formatting can move out of the game into Python (`tools/cmdata`),
   where it is easy to test and change, and the add-on only has to collect.
3. **Some sections silently never appeared.** A section generator that raises an error is dropped without
   a message, and settings read through the migration fallback were being lost. Three small fixes address
   that; they are independent of everything else and are the likeliest to be welcome upstream.
4. **Selecting what to export should be a tree, not 73 switches.** The settings are being redesigned as a
   tree of what an export can contain (see `data/config/`). So far this is a tested design and a Python
   model; the add-on does not use it yet.
5. **The repo had no way to test Lua without the game.** `tests/lua/` adds a small offline runner.

## The branches

All 12 are on the fork. "Base" is what the branch needs underneath it.

| Branch | What it does | Why | Base |
|--------|--------------|-----|------|
| `docs/fix-claude-project-setup` | Fixes stale `/cm github` instructions in the Claude project guide; drops "(GitHub format only)" from the External Links header | `/cm github` no longer exists; the header implied links were missing from normal output | main |
| `fix/settings-merge-fallback` | `CM.GetSettings()` reads each known setting by key instead of `pairs()` | `pairs()` misses values `ZO_SavedVars` serves through its metatable fallback, so Antiquities and Achievements stayed off while the panel showed them on | main |
| `fix/antiquities-section-render-errors` | Fixes two render errors in the Antiquities section (undefined `ANTIQUITY_QUALITY_*` globals; a field the collector never sets) | The section generator raised and the export silently dropped the whole section | main |
| `fix/antiquity-lead-timers` | Reads lead timers fresh each call; adds an approximate expiry; sorts soonest first; marks leads expiring within 7 days | The timer was cached, so a second export in a session repeated the first value | main (visible only with the render fix) |
| `feat/save-to-savedvariables` | `/cm save`, `/cm save coach`; `ExportStore` splits text into parts under the 2000-character SavedVariables limit | Get exports out of the game without copying chunks | main |
| `feat/sv-export-converter` | `python3 -m tools.sv_export` turns the saved table into `<Character>_<date>.md` | The other half of `/cm save` | save-to-savedvariables |
| `feat/export-format-registry` | Formats come from a registry (`src/utils/ExportFormats.lua`); an unknown name lists the available ones | New formats without editing the command; a typo no longer looks like a successful save | save-to-savedvariables |
| `feat/achievement-progress-dump` | `/cm save achievements`: every uncompleted achievement with progress, scanned in steps so the game stays responsive | The normal export only has category totals; the full list is large so it is a separate export | export-format-registry |
| `feat/structured-data-export` | `/cm save data`: saves the collected data table instead of rendered text; splits `GenerateMarkdown` into `CollectData()` and assembly; includes Custom Title and Play Style | Lets tools outside the game build their own formats | export-format-registry |
| `feat/save-clear` | `/cm save clear [format]` removes saved exports | The structured and achievement exports can make the SavedVariables file several megabytes, loaded at every login | export-format-registry |
| `feat/cmdata-model` | `tools/cmdata`: typed Python objects for every export topic, cleaned JSON and compact Markdown | Reads `/cm save data` output; stores repeated data once (about 20% smaller); `--topics` picks sections | main (pure Python) |
| `feat/config-tree` | `tests/lua/` offline Lua test framework; `data/config/tree.json` and `tools/cmconfig` (the settings tree, `resolve()`) | See reasons 4 and 5 above | cmdata-model |

Two of them are not independent: `feat/structured-data-export` and `feat/save-clear` are siblings (both sit on the
registry). `feat/config-tree` currently also carries the Lua test framework, which should be split off before any
PR (see [To do](#to-do-and-ideas)).

## Merge order and rebuilding this branch

Merged in this order, each with `--no-ff` so the history shows what came from where:

```
upstream/main
 1  docs/fix-claude-project-setup
 2  fix/settings-merge-fallback
 3  fix/antiquities-section-render-errors
 4  fix/antiquity-lead-timers
 5  feat/save-to-savedvariables
 6  feat/sv-export-converter
 7  feat/export-format-registry
 8  feat/achievement-progress-dump
 9  feat/structured-data-export
10  feat/save-clear
11  feat/cmdata-model
12  feat/config-tree
```

Independent branches first, then the Lua `/cm save` stack in dependency order, then the Python stack.

**Known conflicts when merging**

- `CHANGELOG.md` conflicts in almost every merge (each branch adds an `[Unreleased]` line). Keep both sides.
- `src/commands/Save.lua`: `structured-data-export` and `achievement-progress-dump` both register a format after
  `coach`; keep both registrations. `save-clear` then conflicts in the file header and just before `HandleSave`
  (keep the combined header, the format registrations, and `HandleClear`).
- `src/utils/ExportStore.lua`: `structured-data-export` and `save-clear` both add functions at the end; keep both.
  `ExportStore.Clear` removes by format key, so it also clears a `data` export.

**Rebuilding from scratch** (for example after upstream moves):

```bash
git fetch upstream
git switch -c integration/all-new upstream/main
git branch --unset-upstream            # never leave this tracking upstream: a stray push would target it
git merge --no-ff <branch> ...         # in the order above; resolve as described
```

Then run everything in [Quality checks](#quality-checks). To refresh after a single branch changes, merge that
branch again; to drop one, rebuild without it.

## Tools

All Python is standard library only (3.10+); run from the repo root.

| Command | What it does |
|---------|--------------|
| `python3 -m tools.sv_export` | Reads `SavedVariables/CharacterMarkdown.lua`, writes one file per saved character and format. Options `--character`, `--format`, `--server`, `--out`; finds the file in the usual Windows/OneDrive/WSL places or takes a path or `ESO_SV` |
| `python3 -m tools.cmdata FILE_data.json` | Typed model of a `/cm save data` export. `--topics antiquities,crafting` or `--topics all` for Markdown, `--format json` for typed JSON |
| `python3 -m tools.cmconfig [--defaults] [--table]` | Prints the configuration tree; `--update-readme` refreshes the mapping table in `data/config/README.md` |
| `python3 -m tools.setdb ...` | The set database pipeline that was already in upstream (needs the `setdb` dependency group) |

In-game commands added here: `/cm save [markdown|coach|data|achievements]`, `/cm save clear [format]`. After any
`/cm save`, `/reloadui` makes the game write the file.

## Quality checks

Tools used: LuaJIT, Luacheck, StyLua, Task, Python 3. (`ruff` is configured in `pyproject.toml` but not
installed on this machine, so Python style is checked by hand: 100-character lines, type hints, no `print` outside CLIs.)

| Check | Command | Expected now |
|-------|---------|--------------|
| Lint (Luacheck) | `task dev:lint` | 0 warnings, 0 errors |
| Lua specs | `task dev:test:lua` (one spec: `task dev:test:lua -- defaults`) | 13 passed |
| Python tests | `task dev:test:python` | 198 tests OK (6 skipped: the set DB tests that need extras) |
| All of the above plus validators | `task test` | passes |
| Validators | `task dev:validate:esoui`, `dev:validate:changelog`, `dev:validate:readme` | ESOUI 9/9 |
| Format check | `stylua --config-path .stylua.toml --check <files>` | see note |
| Tree docs current | `python3 -m tools.cmconfig --update-readme` | no diff |

**Format note.** `stylua --check src` reports 10 files, and **all of that is formatting drift already in
`upstream/main`** (checked on `Markdown.lua`'s upstream copy). So do not run `task format` over the whole of `src`:
it would reformat code nobody here touched. Check only the files you changed, and format only those.

Before sending any branch upstream, run the checks **on that branch's own tip**, not on this merged branch.

## Building and installing in the game

- Use the `deploy-eso-addon` skill, not `task install:live`. The skill backs up what it replaces to
  `~/eso-addon-backups/CharacterMarkdown/` (outside the ESO folders) and handles the WSL path.
- `task install:live` and `install:pts` are broken on Linux (GNU `cp` nests `src/src`); a small upstream PR is planned.
- Build a release-shaped tree first with `task build:fast` (output `build/CharacterMarkdown`), then deploy it
  (dry-run first), then `/reloadui` in the game.
- WSL target: `/mnt/c/Users/choat/OneDrive/Documents/Elder Scrolls Online/live/AddOns`.
- Behaviour that only shows in the game: the Markdown `/cm save` freezes the UI for about 5 seconds (it
  collects in one go); the data and achievement exports use frame-yielding collection and do not freeze.

## Data and files outside the repo

| Path | What |
|------|------|
| `~/src/pr-drafts/` | Nine upstream PR/issue drafts and `00-submission-plan.md`. Nothing in it is posted |
| `~/src/cm-dump-2026-11-14/` | A full real dump (all 73 settings on) for offline work: raw SavedVariables, the data JSON, the typed model JSON, and lean, coach, all-topics, antiquities and achievements Markdown. Also the reduced test state (`settings-reduced-test-state.json`) |
| `F:\claude\outputs\eso\` | Copies of the generated outputs |
| `~/eso-addon-backups/` | Deploy backups |
| `prep-backup/*` (git branches) | Pre-squash history of every rewritten branch. Delete when happy |
| `wip/*` (git branches) | Throwaway merges installed in the game. **Never submit** |

## Submitting upstream

Held until PR #3 has a response. When it does:

1. `git fetch upstream`; check whether `upstream/main` moved from `ff6908e`. Rebase each branch you send onto it.
2. Post the proposal issue first (`~/src/pr-drafts/08-issue-save-to-savedvariables.md`).
3. Order: `fix/settings-merge-fallback`, `fix/antiquities-section-render-errors`, `fix/antiquity-lead-timers`,
   then `feat/save-to-savedvariables`, `feat/sv-export-converter`, `feat/export-format-registry`,
   `feat/achievement-progress-dump`. After that: `feat/structured-data-export`, `feat/save-clear`,
   `feat/cmdata-model`. Stacked branches cannot target an unmerged branch from a fork cleanly, so open each one
   after its base merges and rebase it onto `upstream/main`.
4. Each change is one squashed commit with a `Co-Authored-By` trailer (stacked branches also contain their
   bases' commits underneath). Every PR after the first needs a trivial CHANGELOG rebase (keep both lines).
5. `feat/save-clear`, `feat/structured-data-export`, `feat/cmdata-model` and `feat/config-tree` have **no drafts yet**.
6. Only push to `origin`. The branches do not track `upstream/main`, so a stray `git push` cannot reach it.

```bash
git push origin <branch>
gh pr create --repo solaegis/CharacterMarkdown --base main --head choatej:<branch> \
  --title "<title from the draft>" --body-file ~/src/pr-drafts/<draft>.md   # delete the "Draft" heading first
```

## Gotchas and known issues

- **ESO Lua is 5.1: no `goto`.** `src/ui/Window.lua` is a protected file; ask before changing it.
- **SavedVariables strings are limited to about 2000 characters**, so long text is stored in parts.
  A function, a metatable or a cycle in a saved table is dropped (the data export sanitizer counts what it drops).
- **A section generator that raises is silently left out** of the export. When a section is missing, run its generator
  directly before suspecting the settings. (Two of our three fixes were this.)
- **Settings panel greys out a child when its parent is off but keeps its stored value.** The tree design keeps
  that behaviour on purpose (`data/config/README.md`).
- **Upstream observation, not fixed:** `SavedVariables/CharacterMarkdown.lua` holds nested copies of the settings
  table under the server namespace (`~/src/pr-drafts/09-note-nested-settings-copies.md`). The size is stable across
  reloads; the cause is not known.
- The "morph choice waiting" list shows 9 skills while the export's own summary says 11. Not investigated.
- Craft types (the recipe `craft_type`) and antiquity quality stay numeric in `tools/cmdata` because their names were
  not confirmed. Antiquity quality values are assumed to use the item-quality scale.
- The 7-day expiry marker for antiquity leads was checked offline only (no lead was within 7 days when tested in game).

## To do and ideas

**Verification**
- [ ] Run the merged branch in the game: `/cm save`, `save coach`, `save data`, `save achievements`, `save clear`. The
      two registration conflicts in `Save.lua` have only been checked by compiling and by tests
- [ ] Confirm the 7-day antiquity marker in the game
- [ ] Investigate the morph discrepancy (9 shown, 11 in the summary)
- [ ] Confirm craft-type and antiquity-quality names so `tools/cmdata` can stop printing numbers

**Settings tree** (`data/config/`)
- [ ] Port `ConfigCollection` / `ConfigItem` / `ConfigData` / `resolve()` to Lua; the game has no JSON reader, so
      generate a Lua table from `tree.json`
- [ ] Add Lua specs for it (the framework exists) and a cross-check against the Python model
- [ ] Decide what clicking a *mixed* parent does in the UI (all on, then all off is the usual convention) and put it
      in the model as a `toggle(path)` helper so both sides agree
- [ ] Prototype the settings panel as nested LibAddonMenu submenus; try a custom `ZO_Tree` UI only if that feels bad
- [ ] Let generators read the resolved table; keep `legacy_settings()` as the bridge until they do
- [ ] `/cm save --topics a,b` using tree paths, matching `tools.cmdata --topics`
- [ ] Settings migration: map the 73 old flags onto the tree on first load (`data_from_legacy`)

**Format and architecture**
- [ ] Decide whether formatting moves fully into the Python post-processor, leaving the add-on with one data dump
      (the settings tree then shrinks to content selection; the `format` domain nodes leave the add-on)
- [ ] Decide whether this becomes its own add-on (name mismatch: it is no longer only Markdown). Wait for PR #3's
      response; see the shared-collectors question (two add-ons would either collect twice or one becomes a library)
- [ ] Check whether an ESOUI library already covers exporting add-on data before building a shared one
- [ ] JSON and other output formats from `tools.cmdata` (JSON exists; others do not)

**Housekeeping**
- [ ] Split the Lua test framework out of `feat/config-tree` into its own branch off `upstream/main`
- [ ] Write PR drafts for `save-clear`, `structured-data-export`, `cmdata-model` and the test framework
- [ ] Open the small upstream PR for the `install:live` / `install:pts` Linux bug
- [ ] Consider reporting the nested settings copies as an upstream issue
- [ ] Install `ruff` and run it over `tools/`
- [ ] Offline Lua tests for `ExportStore` (splitting, sanitizing, `Clear`); the old ad-hoc harnesses were not committed
- [ ] Delete `prep-backup/*` and `wip/*` branches once nothing needs them
