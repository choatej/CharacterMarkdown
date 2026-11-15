-- CharacterMarkdown - ExportStore
-- Helpers for getting text out of the game through SavedVariables.
--
-- ESO add-ons cannot write files. The game writes an add-on's SavedVariables global to
-- SavedVariables/<AddOn>.lua on /reloadui, logout or quit, and an outside script can read
-- it from there. Two things make long text awkward to store:
--   * String values of 2000+ characters are silently dropped when saved.
--   * Generators may hand back window chunks ({ content = "..." }) with markers and padding.
--
-- This module is deliberately independent of the rest of CharacterMarkdown: it uses no CM
-- functions, settings or generators, only plain Lua 5.1. The one CM reference is the
-- registration line at the bottom. That keeps it easy to move into a shared library later.
--
-- Stored layout (see Put):
--   container = {
--       meta = { ... caller supplied ... },
--       characters = {
--           ["Name"] = {
--               exports = {
--                   -- one entry per format, so saving a second format keeps the first
--                   ["markdown"] = { timestamp, charCount, textParts = { "...", ... } },
--                   ["coach"] = { ... },
--               },
--           },
--       },
--   }
-- Concatenate textParts with no separator to rebuild the text. charCount is its length in bytes.

local ExportStore = {}

-- SavedVariables drop any single string of 2000+ characters; stay well below.
ExportStore.MAX_STRING = 1900

local table_concat = table.concat

--- Number of bytes in the UTF-8 character that starts at byte `pos`.
-- Lua 5.1 strings are bytes, so we read the lead byte ourselves.
local function Utf8CharLen(s, pos)
    local b = s:byte(pos)
    if not b or b < 0xC0 then
        return 1
    elseif b < 0xE0 then
        return 2
    elseif b < 0xF0 then
        return 3
    end
    return 4
end

--- Cut `text` into pieces of at most `maxLen` bytes, preferring line boundaries.
-- A piece ends where a line ends ("\n") unless one line is longer than `maxLen`; that line
-- is cut between UTF-8 characters, never inside one. Joining the pieces with no separator
-- returns the original text exactly.
-- @param text string
-- @param maxLen number|nil (default ExportStore.MAX_STRING)
-- @return table array of strings
function ExportStore.SplitText(text, maxLen)
    maxLen = maxLen or ExportStore.MAX_STRING
    local parts = {}
    local buffer = {}
    local bufferLen = 0

    local function flush()
        if bufferLen > 0 then
            parts[#parts + 1] = table_concat(buffer)
            buffer = {}
            bufferLen = 0
        end
    end

    local function add(piece)
        if bufferLen + #piece > maxLen then
            flush()
        end
        buffer[#buffer + 1] = piece
        bufferLen = bufferLen + #piece
    end

    -- Lines keep their trailing newline; the final line may not have one.
    for line in text:gmatch("[^\n]*\n?") do
        if line ~= "" then
            if #line <= maxLen then
                add(line)
            else
                flush()
                local pos = 1
                while pos <= #line do
                    local stop = pos
                    while stop <= #line do
                        local nextStop = stop + Utf8CharLen(line, stop)
                        if nextStop - pos > maxLen then
                            break
                        end
                        stop = nextStop
                    end
                    parts[#parts + 1] = line:sub(pos, stop - 1)
                    pos = stop
                end
            end
        end
    end
    flush()
    return parts
end

--- Join generator output into one string.
-- @param result string|table a string, or an array of { content = "..." } chunks
-- @param stripChunk function|nil function(content, isLast) -> content, applied to each chunk
--   (use it to remove window markers and padding)
-- @return string|nil nil when `result` is neither a string nor a table
function ExportStore.Flatten(result, stripChunk)
    if type(result) == "string" then
        return result
    end
    if type(result) ~= "table" then
        return nil
    end
    local pieces = {}
    for i, chunk in ipairs(result) do
        local content = type(chunk) == "table" and chunk.content or tostring(chunk)
        if stripChunk then
            content = stripChunk(content, i == #result)
        end
        pieces[#pieces + 1] = content
    end
    return table_concat(pieces)
end

--- Store one export in `container` (created if nil) and return it.
-- Other characters and other formats already in the container are kept; an export with the
-- same `name` and `format` is replaced.
-- @param container table|nil existing saved table
-- @param name string character name
-- @param entry table { text = string, format = string, timestamp = number|nil }
-- @param meta table|nil replaces container.meta when given
-- @return table container
-- @return number number of parts written
function ExportStore.Put(container, name, entry, meta)
    if type(container) ~= "table" then
        container = {}
    end
    if type(container.characters) ~= "table" then
        container.characters = {}
    end
    if meta then
        container.meta = meta
    end

    local character = container.characters[name]
    if type(character) ~= "table" then
        character = {}
        container.characters[name] = character
    end
    if type(character.exports) ~= "table" then
        character.exports = {}
    end

    local text = entry.text
    local parts = ExportStore.SplitText(text)
    character.exports[entry.format or "text"] = {
        timestamp = entry.timestamp,
        charCount = #text,
        textParts = parts,
    }
    return container, #parts
end

--- Remove saved exports from `container`.
-- With a format, only that format is removed (for every character); characters left with no
-- exports are removed too. Without one, everything is removed.
-- @param container table|nil the saved table
-- @param format string|nil format name, compared case-insensitively
-- @return table|nil the container, or nil when nothing is left in it
-- @return number how many exports were removed
function ExportStore.Clear(container, format)
    if type(container) ~= "table" or type(container.characters) ~= "table" then
        return nil, 0
    end

    local removed = 0
    local wanted = format and format:lower() or nil
    for name, character in pairs(container.characters) do
        local exports = type(character) == "table" and character.exports or nil
        if type(exports) == "table" then
            for key in pairs(exports) do
                if not wanted or (type(key) == "string" and key:lower() == wanted) then
                    exports[key] = nil
                    removed = removed + 1
                end
            end
            if next(exports) == nil then
                container.characters[name] = nil
            end
        elseif not wanted then
            container.characters[name] = nil
        end
    end

    if not wanted or next(container.characters) == nil then
        return nil, removed
    end
    return container, removed
end

-- The only CharacterMarkdown-specific line in this file.
CharacterMarkdown.utils = CharacterMarkdown.utils or {}
CharacterMarkdown.utils.ExportStore = ExportStore
