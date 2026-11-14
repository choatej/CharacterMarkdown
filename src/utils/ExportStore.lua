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
-- Structured exports store a table instead of textParts (see STRUCTURED DATA below).

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

--- Find or create the exports table for one character inside `container`.
-- @return table container (created if nil)
-- @return table the character's exports table
local function EnsureExports(container, name, meta)
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
    return container, character.exports
end

--- Store one text export in `container` (created if nil) and return it.
-- Other characters and other formats already in the container are kept; an export with the
-- same `name` and `format` is replaced.
-- @param container table|nil existing saved table
-- @param name string character name
-- @param entry table { text = string, format = string, timestamp = number|nil }
-- @param meta table|nil replaces container.meta when given
-- @return table container
-- @return number number of parts written
function ExportStore.Put(container, name, entry, meta)
    local exports
    container, exports = EnsureExports(container, name, meta)

    local text = entry.text
    local parts = ExportStore.SplitText(text)
    exports[entry.format or "text"] = {
        timestamp = entry.timestamp,
        charCount = #text,
        textParts = parts,
    }
    return container, #parts
end

-- =====================================================
-- STRUCTURED DATA
-- =====================================================
-- Text exports are stored as textParts. A structured export stores a table instead:
--   exports["data"] = { timestamp, kind = "data", data = { ... }, report = { ... } }
-- SavedVariables can hold nested tables of strings, numbers and booleans directly, but not
-- functions or userdata, and it drops any string of 2000+ characters. Sanitize copies a table
-- into a form that is safe to store and reports what it had to change:
--   * a string longer than the limit becomes { ["$parts"] = { "...", "..." } } (join the parts)
--   * functions, userdata, threads, NaN/infinite numbers and non-string/number keys are dropped
--   * cycles and tables nested deeper than MAX_DEPTH are dropped
-- Numeric keys are kept as they are (a table with holes stays a table with those keys).

ExportStore.PARTS_KEY = "$parts"
ExportStore.MAX_DEPTH = 16
ExportStore.MAX_NODES = 200000
ExportStore.MAX_DROPPED_LISTED = 50

local function PathString(path, depth)
    if depth == 0 then
        return "<root>"
    end
    local pieces = {}
    for i = 1, depth do
        pieces[i] = tostring(path[i])
    end
    return table_concat(pieces, ".")
end

--- Copy `value` into a form SavedVariables can store.
-- @param value any usually a table
-- @param options table|nil { maxString, maxDepth, maxNodes }
-- @return any the sanitized copy (nil if the value itself had to be dropped)
-- @return table report { tables, strings, longStrings, numbers, booleans, dropped, droppedList, truncated }
function ExportStore.Sanitize(value, options)
    options = options or {}
    local maxString = options.maxString or ExportStore.MAX_STRING
    local maxDepth = options.maxDepth or ExportStore.MAX_DEPTH
    local maxNodes = options.maxNodes or ExportStore.MAX_NODES

    local report = {
        tables = 0,
        strings = 0,
        longStrings = 0,
        numbers = 0,
        booleans = 0,
        dropped = 0,
        droppedList = {},
        truncated = false,
    }
    local nodes = 0
    local ancestors = {} -- tables currently being copied; seeing one again means a cycle
    local path, depth = {}, 0

    local function drop(reason)
        report.dropped = report.dropped + 1
        if #report.droppedList < ExportStore.MAX_DROPPED_LISTED then
            report.droppedList[#report.droppedList + 1] = PathString(path, depth) .. " (" .. reason .. ")"
        end
    end

    local copy
    copy = function(v)
        nodes = nodes + 1
        if nodes > maxNodes then
            report.truncated = true
            return nil
        end

        local kind = type(v)
        if kind == "boolean" then
            report.booleans = report.booleans + 1
            return v
        elseif kind == "number" then
            if v ~= v or v == math.huge or v == -math.huge then
                drop("number is NaN or infinite")
                return nil
            end
            report.numbers = report.numbers + 1
            return v
        elseif kind == "string" then
            if #v > maxString then
                report.longStrings = report.longStrings + 1
                return { [ExportStore.PARTS_KEY] = ExportStore.SplitText(v, maxString) }
            end
            report.strings = report.strings + 1
            return v
        elseif kind == "table" then
            if depth >= maxDepth then
                drop("nested deeper than " .. maxDepth)
                return nil
            end
            if ancestors[v] then
                drop("cycle")
                return nil
            end
            ancestors[v] = true
            local out = {}
            for key, item in pairs(v) do
                local keyType = type(key)
                local keyOk = keyType == "string"
                    or (keyType == "number" and key == key and key ~= math.huge and key ~= -math.huge)
                if keyOk then
                    depth = depth + 1
                    path[depth] = key
                    local copied = copy(item)
                    depth = depth - 1
                    if copied ~= nil then
                        out[key] = copied
                    end
                else
                    drop("key of type " .. keyType)
                end
            end
            ancestors[v] = nil
            report.tables = report.tables + 1
            return out
        end

        -- function, userdata, thread
        drop(kind)
        return nil
    end

    local clean = copy(value)
    return clean, report
end

--- Store one structured export in `container` (created if nil) and return it.
-- @param container table|nil existing saved table
-- @param name string character name
-- @param entry table { data = table, format = string, timestamp = number|nil, report = table|nil }
-- @param meta table|nil replaces container.meta when given
-- @return table container
function ExportStore.PutData(container, name, entry, meta)
    local exports
    container, exports = EnsureExports(container, name, meta)

    exports[entry.format or "data"] = {
        timestamp = entry.timestamp,
        kind = "data",
        data = entry.data,
        report = entry.report,
    }
    return container
end

-- The only CharacterMarkdown-specific line in this file.
CharacterMarkdown.utils = CharacterMarkdown.utils or {}
CharacterMarkdown.utils.ExportStore = ExportStore
