-- CharacterMarkdown - ExportFormats
-- A small registry of export formats for /cm save.
--
-- What goes into an export (sections, links, detail) is chosen by the settings and presets.
-- The format decides how that content is written out. Registering a format here makes it
-- available as `/cm save <name>` without touching the command code.
--
-- A format is a table:
--   {
--       aliases = { "ai" },                       -- optional extra names
--       description = "Compact AI export",        -- optional, shown in help
--       Generate = function(onDone, onError) end, -- required; calls onDone(result) with a
--                                                 -- string or an array of { content = "..." }
--   }
--
-- Plain Lua 5.1, no dependency on the rest of the add-on apart from the registration line
-- at the bottom.

local ExportFormats = {}

local formats = {} -- canonical name -> definition
local lookup = {} -- lowercase name or alias -> canonical name

--- Register a format. A second registration of the same name replaces the first.
-- @param name string canonical name (stored in SavedVariables, so keep it stable)
-- @param definition table see the header comment
function ExportFormats.Register(name, definition)
    assert(type(name) == "string" and name ~= "", "format name must be a non-empty string")
    assert(type(definition) == "table", "format definition must be a table")
    assert(type(definition.Generate) == "function", "format needs a Generate function")

    local canonical = name:lower()
    -- Drop names left over from a previous registration of this format.
    for key, target in pairs(lookup) do
        if target == canonical then
            lookup[key] = nil
        end
    end

    formats[canonical] = definition
    lookup[canonical] = canonical
    for _, alias in ipairs(definition.aliases or {}) do
        lookup[alias:lower()] = canonical
    end
end

--- Find a format by name or alias (case-insensitive).
-- @param nameOrAlias string
-- @return table|nil definition
-- @return string|nil canonical name
function ExportFormats.Resolve(nameOrAlias)
    local canonical = lookup[(nameOrAlias or ""):lower()]
    if not canonical then
        return nil, nil
    end
    return formats[canonical], canonical
end

--- Canonical names of all registered formats, sorted.
-- @return table array of strings
function ExportFormats.Names()
    local names = {}
    for name in pairs(formats) do
        names[#names + 1] = name
    end
    table.sort(names)
    return names
end

-- The only CharacterMarkdown-specific line in this file.
CharacterMarkdown.utils = CharacterMarkdown.utils or {}
CharacterMarkdown.utils.ExportFormats = ExportFormats
