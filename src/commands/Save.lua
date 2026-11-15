-- CharacterMarkdown - Save Command Handlers
-- /cm save       - write the full Markdown export to SavedVariables
-- /cm save coach - write the compact AI / build-coach export to SavedVariables
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

local function Store(formatter, result)
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
    }, {
        schema = SCHEMA_VERSION,
        addonVersion = CM.version,
        apiVersion = GetAPIVersion and GetAPIVersion() or nil,
        gameVersion = GetESOVersionString and GetESOVersionString() or nil,
        server = GetWorldName and GetWorldName() or nil,
    })

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

--- /cm save [coach]
-- @param args string|nil "" or "coach" (aliases: ai, build-coach)
local function HandleSave(args)
    if not CM.isInitialized then
        CM.Error("Addon not fully initialized. Try again in a moment or /reloadui")
        return
    end

    local arg = (args or ""):lower():match("^%s*(%S*)")
    local isCoach = arg == "coach" or arg == "ai" or arg == "build-coach"

    if isCoach then
        if not (CM.generators and CM.generators.GenerateBuildCoach) then
            CM.Error("Build coach generator not loaded! Try /reloadui")
            return
        end
        local ok, result = pcall(CM.generators.GenerateBuildCoach)
        if not ok then
            CM.Error("Failed to generate build coach export:")
            CM.Error(tostring(result))
            return
        end
        Store("coach", result)
        return
    end

    if arg ~= "" then
        CM.Warn(string_format("Unknown save option '%s'. Saving the full export.", arg))
    end

    if not (CM.generators and CM.generators.Run) then
        CM.Error("Markdown generator not loaded! Try /reloadui")
        return
    end
    CM.Info("Generating export to save...")
    CM.generators.Run(function(result)
        Store("markdown", result)
    end, function(err)
        CM.Error("Failed to generate markdown:")
        CM.Error(tostring(err))
    end)
end

CM.commands.save.HandleSave = HandleSave

CM.DebugPrint("COMMANDS", "Save command module loaded")
