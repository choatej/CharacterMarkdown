-- CharacterMarkdown - Antiquities Markdown Generator
-- Generates markdown for antiquities, leads, and scrying progress

local CM = CharacterMarkdown

-- =====================================================
-- UTILITIES
-- =====================================================

local function InitializeUtilities()
    if not CM.utils then
        CM.utils = {}
    end

    -- FormatNumber is already exported by Formatters.lua
    if not CM.utils.FormatNumber then
        CM.utils.FormatNumber = function(num)
            if not num then
                return "0"
            end
            local formatted = tostring(num)
            return formatted:reverse():gsub("(%d%d%d)", "%1,"):reverse():gsub("^,", "")
        end
    end

    -- GenerateProgressBar is exported by helpers/Utilities.lua
    if not CM.utils.GenerateProgressBar and CM.generators and CM.generators.helpers then
        CM.utils.GenerateProgressBar = CM.generators.helpers.GenerateProgressBar
    end

    -- Fallback progress bar if helpers not loaded
    if not CM.utils.GenerateProgressBar then
        CM.utils.GenerateProgressBar = function(percent, width)
            width = width or 10
            local filled = math.floor((percent / 100) * width)
            local empty = width - filled
            return string.rep("█", filled) .. string.rep("░", empty)
        end
    end

    -- Load GenerateAnchor from markdown utils
    if not CM.utils.GenerateAnchor and CM.utils.markdown and CM.utils.markdown.GenerateAnchor then
        CM.utils.GenerateAnchor = CM.utils.markdown.GenerateAnchor
    end
end

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Antiquity quality uses the same numeric scale as item quality. The game has no
-- ANTIQUITY_QUALITY_* constants: using them as table keys raised "table index is nil" and
-- the whole section was dropped, so key by the item-quality constants (with numeric
-- fallbacks so a key can never be nil).
local QUALITY_TRASH = ITEM_QUALITY_TRASH or 0
local QUALITY_NORMAL = ITEM_QUALITY_NORMAL or 1
local QUALITY_MAGIC = ITEM_QUALITY_MAGIC or 2
local QUALITY_ARCANE = ITEM_QUALITY_ARCANE or 3
local QUALITY_ARTIFACT = ITEM_QUALITY_ARTIFACT or 4
local QUALITY_LEGENDARY = ITEM_QUALITY_LEGENDARY or 5
local QUALITY_MYTHIC = ITEM_QUALITY_MYTHIC or 6

local QUALITY_COLORS = {
    [QUALITY_TRASH] = "⚪", -- White/Trash
    [QUALITY_NORMAL] = "⚪", -- White/Normal
    [QUALITY_MAGIC] = "🟢", -- Green/Magic
    [QUALITY_ARCANE] = "🔵", -- Blue/Arcane
    [QUALITY_ARTIFACT] = "🟣", -- Purple/Artifact
    [QUALITY_LEGENDARY] = "🟡", -- Gold/Legendary
    [QUALITY_MYTHIC] = "🟠", -- Orange/Mythic
}

local QUALITY_NAMES = {
    [QUALITY_TRASH] = "Common",
    [QUALITY_NORMAL] = "Common",
    [QUALITY_MAGIC] = "Fine",
    [QUALITY_ARCANE] = "Superior",
    [QUALITY_ARTIFACT] = "Epic",
    [QUALITY_LEGENDARY] = "Legendary",
    [QUALITY_MYTHIC] = "Mythic",
}

local function GetQualityColor(quality)
    return QUALITY_COLORS[quality] or "⚪"
end

local function GetQualityName(quality)
    return QUALITY_NAMES[quality] or "Unknown"
end

-- =====================================================
-- ANTIQUITIES SUMMARY GENERATOR
-- =====================================================

local function GenerateAntiquitiesSummary(antiquityData)
    InitializeUtilities()

    local markdown = ""
    local summary = antiquityData.summary

    local anchorId = CM.utils.GenerateAnchor and CM.utils.GenerateAnchor("🏺 Antiquities") or "antiquities"
    markdown = markdown .. string.format('<a id="%s"></a>\n\n', anchorId)
    markdown = markdown .. "## 🏺 Antiquities\n\n"

    -- Calculate completion percentage
    local discoveryPercent = summary.totalAntiquities > 0
            and math.floor((summary.discoveredAntiquities / summary.totalAntiquities) * 100)
        or 0
    local setsPercent = summary.totalSets > 0 and math.floor((summary.completedSets / summary.totalSets) * 100) or 0

    markdown = markdown .. "| Metric | Value |\n"
    markdown = markdown .. "|:-------|------:|\n"
    markdown = markdown .. "| **Total Antiquities** | " .. CM.utils.FormatNumber(summary.totalAntiquities) .. " |\n"
    markdown = markdown
        .. "| **Discovered** | "
        .. CM.utils.FormatNumber(summary.discoveredAntiquities)
        .. " ("
        .. discoveryPercent
        .. "%) |\n"
    markdown = markdown .. "| **Active Leads** | " .. summary.activeLeads .. " |\n"
    markdown = markdown
        .. "| **Completed Sets** | "
        .. summary.completedSets
        .. "/"
        .. summary.totalSets
        .. " ("
        .. setsPercent
        .. "%) |\n"
    markdown = markdown .. "\n"

    return markdown
end

-- =====================================================
-- ACTIVE LEADS GENERATOR
-- =====================================================

local function GenerateActiveLeads(antiquityData)
    InitializeUtilities()

    local markdown = ""

    if #antiquityData.activeLeads == 0 then
        return markdown
    end

    markdown = markdown .. "### 🔎 Active Leads\n\n"
    markdown = markdown .. "| Antiquity | Quality | Lead Timer | Repeatable |\n"
    markdown = markdown .. "|:----------|:--------|:-----------|:----------:|\n"

    for _, lead in ipairs(antiquityData.activeLeads) do
        local qualityIcon = GetQualityColor(lead.quality)
        local qualityName = GetQualityName(lead.quality)
        local repeatableText = lead.isRepeatable and "✓" or "✗"
        local timerText = "-"
        if lead.leadSecondsRemaining and lead.leadSecondsRemaining > 0 then
            local hours = math.floor(lead.leadSecondsRemaining / 3600)
            local mins = math.floor((lead.leadSecondsRemaining % 3600) / 60)
            timerText = string.format("%dh %dm", hours, mins)
        end

        markdown = markdown
            .. "| "
            .. qualityIcon
            .. " **"
            .. lead.name
            .. "** | "
            .. qualityName
            .. " | "
            .. timerText
            .. " | "
            .. repeatableText
            .. " |\n"
    end
    markdown = markdown .. "\n"

    if antiquityData.activeScry and antiquityData.activeScry.name then
        markdown = markdown .. "*Active scry target: **" .. antiquityData.activeScry.name .. "***\n\n"
    end

    return markdown
end

-- =====================================================
-- ANTIQUITY SETS GENERATOR
-- =====================================================

local function GenerateAntiquitySets(antiquityData)
    InitializeUtilities()

    local markdown = ""
    local settings = CM.GetSettings()

    -- Check if detailed view is enabled
    if not settings.showAntiquitiesDetailed then
        return markdown
    end

    markdown = markdown .. "### 📦 Antiquity Sets\n\n"
    markdown = markdown .. "| Set Name | Progress | Discovered | Total |\n"
    markdown = markdown .. "|:---------|:---------|----------:|------:|\n"

    for _, setData in ipairs(antiquityData.sets) do
        -- The collector gives each set numAntiquities (its size) plus discovered/completed counts
        local totalAntiquities = setData.numAntiquities or #(setData.antiquities or {})
        local percent = totalAntiquities > 0
                and math.floor(((setData.completedAntiquities or 0) / totalAntiquities) * 100)
            or 0
        local progressBar = CM.utils.GenerateProgressBar(percent, 10)
        local completeIcon = percent == 100 and "✅" or "🔄"

        markdown = markdown
            .. "| "
            .. completeIcon
            .. " **"
            .. setData.name
            .. "** | "
            .. progressBar
            .. " "
            .. percent
            .. "% | "
            .. (setData.discoveredAntiquities or 0)
            .. " | "
            .. totalAntiquities
            .. " |\n"
    end
    markdown = markdown .. "\n"

    return markdown
end

-- =====================================================
-- MAIN ANTIQUITIES GENERATOR
-- =====================================================

local function GenerateAntiquities(antiquityData)
    InitializeUtilities()

    -- Return empty if no antiquity data
    if not antiquityData or not antiquityData.summary then
        return ""
    end

    -- Return empty if player hasn't discovered any antiquities
    if antiquityData.summary.totalAntiquities == 0 then
        return ""
    end

    local markdown = ""
    local settings = CM.GetSettings()

    -- Generate antiquities summary (always shown)
    markdown = markdown .. GenerateAntiquitiesSummary(antiquityData)

    -- Show active leads if any exist
    if #antiquityData.activeLeads > 0 then
        markdown = markdown .. GenerateActiveLeads(antiquityData)
    end

    -- Generate detailed sets section if enabled
    if settings.showAntiquitiesDetailed and #antiquityData.sets > 0 then
        markdown = markdown .. GenerateAntiquitySets(antiquityData)
    end

    -- Add section separator
    -- Use CreateSeparator for consistent separator styling
    local CreateSeparator = CM.utils.markdown and CM.utils.markdown.CreateSeparator
    if CreateSeparator then
        markdown = markdown .. CreateSeparator("hr")
    else
        markdown = markdown .. "---\n\n"
    end

    return markdown
end

-- =====================================================
-- EXPORTS
-- =====================================================

CM.generators.sections = CM.generators.sections or {}
CM.generators.sections.GenerateAntiquities = GenerateAntiquities

return {
    GenerateAntiquities = GenerateAntiquities,
}
