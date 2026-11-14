-- CharacterMarkdown - Save Command Handlers
-- /cm save [format] - write an export to SavedVariables. Formats come from the registry in
--                     src/utils/ExportFormats.lua: markdown (default), coach (alias: ai),
--                     data (structured tables instead of text)
--
-- ESO add-ons cannot write files. SavedVariables is the one channel out of the game:
-- the client writes the CharacterMarkdownExport table to
--   Documents/Elder Scrolls Online/live/SavedVariables/CharacterMarkdown.lua
-- on /reloadui, logout or quit. An external script can then turn it into a .md file,
-- so nothing has to be selected and copied out of the in-game window.
--
-- The splitting and storage live in src/utils/ExportStore.lua, which does not depend on the
-- rest of this add-on. This file only gathers the CharacterMarkdown-specific inputs.
-- Saved layout: CharacterMarkdownExport = { meta = {...}, characters = { ["Name"] = {
-- exports = { ["markdown"] = { timestamp, charCount, textParts } } } } }; join textParts
-- (no separator) for the text. Each format is kept separately, per character.

local CM = CharacterMarkdown
CM.commands = CM.commands or {}
CM.commands.save = {}

local string_format = string.format

local SCHEMA_VERSION = 1

local function CharacterName()
    local name = GetUnitName and GetUnitName("player") or nil
    if name and name ~= "" then
        -- Strip ESO gender/name markup such as "Name^Fx"
        return zo_strformat and zo_strformat("<<1>>", name) or name
    end
    return "Unknown"
end

local function ExportMeta()
    return {
        schema = SCHEMA_VERSION,
        addonVersion = CM.version,
        apiVersion = GetAPIVersion and GetAPIVersion() or nil,
        gameVersion = GetESOVersionString and GetESOVersionString() or nil,
        server = GetWorldName and GetWorldName() or nil,
    }
end

--- Save a structured (table) export: sanitize it so SavedVariables can hold it, then store it.
local function StoreData(formatter, data)
    local store = CM.utils.ExportStore
    local clean, report = store.Sanitize(data)
    if type(clean) ~= "table" then
        CM.Error("Nothing to save: collected data was empty")
        return
    end

    local name = CharacterName()
    CharacterMarkdownExport = store.PutData(CharacterMarkdownExport, name, {
        data = clean,
        format = formatter,
        timestamp = GetTimeStamp and GetTimeStamp() or nil,
        report = report,
    }, ExportMeta())

    CM.Info(
        string_format(
            "Saved %s export for %s (%d tables, %d values dropped). Type /reloadui to write it to SavedVariables.",
            formatter,
            name,
            report.tables,
            report.dropped
        )
    )
    if report.dropped > 0 then
        CM.Warn(
            string_format(
                "%d value(s) could not be saved (functions, NaN, cycles...); the list is in the saved report.",
                report.dropped
            )
        )
    end
    if report.truncated then
        CM.Warn("The data was larger than the safety limit and was cut short.")
    end
end

local function Store(formatter, result, structured)
    if structured then
        StoreData(formatter, result)
        return
    end

    -- Generators return a string or window chunks; strip the window's "<!-- Chunk N -->"
    -- markers and padding the same way the window's copy buttons do.
    local chunking = CM.utils.Chunking
    local text = CM.utils.ExportStore.Flatten(result, chunking and chunking.StripPadding)
    if not text or text == "" then
        CM.Error("Nothing to save: generated output was empty")
        return
    end

    local name = CharacterName()
    local count
    CharacterMarkdownExport, count = CM.utils.ExportStore.Put(CharacterMarkdownExport, name, {
        text = text,
        format = formatter,
        timestamp = GetTimeStamp and GetTimeStamp() or nil,
    }, ExportMeta())

    CM.Info(
        string_format(
            "Saved %s export for %s (%d chars, %d parts). Type /reloadui to write it to SavedVariables.",
            formatter,
            name,
            #text,
            count
        )
    )
end

-- =====================================================
-- BUILT-IN FORMATS
-- =====================================================

local Formats = CM.utils.ExportFormats

Formats.Register("markdown", {
    description = "Full Markdown profile (default)",
    Generate = function(onDone, onError)
        if not (CM.generators and CM.generators.Run) then
            onError("Markdown generator not loaded! Try /reloadui")
            return
        end
        CM.generators.Run(onDone, onError)
    end,
})

Formats.Register("coach", {
    aliases = { "ai", "build-coach" },
    description = "Compact AI / build-coach export",
    Generate = function(onDone, onError)
        if not (CM.generators and CM.generators.GenerateBuildCoach) then
            onError("Build coach generator not loaded! Try /reloadui")
            return
        end
        local ok, result = pcall(CM.generators.GenerateBuildCoach)
        if ok then
            onDone(result)
        else
            onError(result)
        end
    end,
})

Formats.Register("data", {
    structured = true,
    description = "Everything the collectors gathered, as data (for tools, not for reading)",
    Generate = function(onDone, onError)
        if not (CM.generators and CM.generators.CollectData) then
            onError("Data collection is not loaded! Try /reloadui")
            return
        end
        local ok, data, settingsOrError = pcall(CM.generators.CollectData)
        if not ok then
            onError(data)
        elseif not data then
            onError(settingsOrError)
        else
            onDone(data)
        end
    end,
})

--- /cm save [format]
-- @param args string|nil a registered format name or alias; empty means "markdown"
local function HandleSave(args)
    if not CM.isInitialized then
        CM.Error("Addon not fully initialized. Try again in a moment or /reloadui")
        return
    end

    local arg = (args or ""):match("^%s*(%S*)")
    local format, name = Formats.Resolve(arg ~= "" and arg or "markdown")
    if not format then
        CM.Error(string_format("Unknown format '%s'.", arg))
        CM.Info("Available formats: " .. table.concat(Formats.Names(), ", "))
        return
    end

    CM.Info(string_format("Generating %s export to save...", name))
    format.Generate(function(result)
        Store(name, result, format.structured)
    end, function(err)
        CM.Error(string_format("Failed to generate %s export:", name))
        CM.Error(tostring(err))
    end)
end

CM.commands.save.HandleSave = HandleSave

CM.DebugPrint("COMMANDS", "Save command module loaded")
