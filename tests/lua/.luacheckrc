-- Luacheck configuration for the offline Lua tests (picked up for files under tests/lua).
std = "lua51"

-- Globals the runner provides to every spec (see tests/lua/run.lua).
read_globals = {
    "describe",
    "it",
    "before_each",
    "eq",
    "truthy",
    "falsy",
    "raises",
    "ESO",
}

-- Specs load add-on source into the global environment, as the game does.
globals = {
    "CharacterMarkdown",
    "CM",
}

ignore = {
    "212", -- unused argument
}
