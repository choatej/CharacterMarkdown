-- Stand-ins for the parts of the ESO environment the add-on touches at load time, plus helpers to
-- load real add-on source files into a test. Add a stub here when a module needs one, and keep
-- each stub as small as the module's use of it.

local Stubs = {}

-- Directory of the repository root, set by the runner.
Stubs.root = "."

-- Create a fresh add-on namespace the way src/Core.lua does, with logging captured.
-- Returns the namespace and a log of what the add-on tried to print.
function Stubs.NewAddon()
    local log = {}
    local function record(level)
        return function(...)
            local parts = {}
            for i = 1, select("#", ...) do
                parts[#parts + 1] = tostring((select(i, ...)))
            end
            log[#log + 1] = level .. " " .. table.concat(parts, " ")
        end
    end

    local CM = {
        name = "CharacterMarkdown",
        version = "test",
        isInitialized = true,
        DebugPrint = function() end,
        Info = record("INFO"),
        Warn = record("WARN"),
        Error = record("ERROR"),
    }
    _G.CharacterMarkdown = CM
    _G.CM = CM
    return CM, log
end

-- Load one add-on source file (path relative to the repository root) into the current globals.
function Stubs.Load(relativePath)
    local chunk, err = loadfile(Stubs.root .. "/" .. relativePath)
    if not chunk then
        error("cannot load " .. relativePath .. ": " .. tostring(err), 2)
    end
    return chunk()
end

-- The ordered list of Lua files in the add-on manifest (CharacterMarkdown.txt).
function Stubs.ManifestFiles()
    local files = {}
    local handle = assert(io.open(Stubs.root .. "/CharacterMarkdown.txt", "r"))
    for line in handle:lines() do
        line = line:gsub("%s+$", "")
        if line:match("^[^#]") and line:match("%.lua$") then
            files[#files + 1] = line
        end
    end
    handle:close()
    return files
end

return Stubs
