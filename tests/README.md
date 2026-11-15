# Offline tests

Tests that run without the game. Nothing here is packaged into the add-on (the build skips `tests/`).

```
task dev:test:lua                    # all Lua specs (needs LuaJIT), then Luacheck on tests/lua
task dev:test:lua -- defaults        # only specs whose file name contains "defaults"
luajit tests/lua/run.lua             # the same without Task
task dev:test:python                 # Python tool tests (tools/*/test_*.py)
```

## Lua specs

A spec is `tests/lua/spec/<name>_spec.lua`. The runner provides these globals while the spec loads:

| Global | Use |
|--------|-----|
| `describe(name, fn)`, `it(name, fn)` | group and define tests; names are joined with `>` in failures |
| `before_each(fn)` | runs before every `it` in the enclosing `describe` |
| `eq(actual, expected)` | deep comparison of tables and values |
| `truthy(v)`, `falsy(v)` | truthiness checks |
| `raises(fn [, text])` | `fn` must error; the message must contain `text` if given |
| `ESO` | helpers from `tests/lua/eso_stubs.lua` |

`ESO` helpers:

- `ESO.NewAddon()` creates a fresh `CharacterMarkdown` namespace with captured logging (returns the namespace and the log).
- `ESO.Load("src/path/File.lua")` loads a real add-on source file, so tests exercise the shipped code.
- `ESO.ManifestFiles()` lists the Lua files in `CharacterMarkdown.txt`.

The global table is restored after every spec file, so a spec may set globals (game functions,
`CharacterMarkdown`) freely. Define a stub for a game function inside the spec that needs it; move it
to `eso_stubs.lua` once a second spec wants the same one.

```lua
describe("Defaults", function()
    before_each(function()
        ESO.NewAddon()
        ESO.Load("src/settings/Defaults.lua")
    end)

    it("turns the header on", function()
        eq(CharacterMarkdown.Settings.Defaults:GetAll().includeHeader, true)
    end)
end)
```

The runner exits non-zero when any test fails, a spec does not load, or no spec matches the filter.
Plain Lua 5.1 only (the game's version): no `goto`, no `//`, no `continue`.
