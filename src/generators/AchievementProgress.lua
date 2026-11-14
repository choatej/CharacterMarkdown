-- CharacterMarkdown - Uncompleted Achievement Progress (text renderer)
-- Turns the data from CM.collectors.CollectUncompletedAchievements into compact Markdown for
-- `/cm save achievements`. Plain text on purpose: no links, tables or emoji, because the list
-- is long and is meant to be read by a person or an AI, not shown in the in-game window.

local CM = CharacterMarkdown
CM.generators = CM.generators or {}

local string_format = string.format
local table_concat = table.concat

--- "Name (10 pts) - 35/100 (35%)", or "Name (10 pts) - not started" when nothing is done.
local function Line(achievement)
    local progress = "not started"
    if achievement.required and achievement.required > 0 and achievement.done > 0 then
        progress = string_format("%d/%d (%d%%)", achievement.done, achievement.required, achievement.percent or 0)
    end
    return string_format("- %s (%d pts) - %s", achievement.name or "?", achievement.points or 0, progress)
end

--- Render the collected data as Markdown.
-- @param data table from CollectUncompletedAchievements
-- @return string
local function RenderAchievementProgress(data)
    local out = {}
    local date = data.timestamp and CM.api.time.FormatDate(data.timestamp) or ""
    out[#out + 1] = "# Uncompleted Achievements" .. (data.characterName and (" - " .. data.characterName) or "")
    if date ~= "" then
        out[#out + 1] = "Exported " .. date
    end
    out[#out + 1] = ""
    out[#out + 1] =
        string_format("%d uncompleted, %d points remaining.", data.summary.uncompleted, data.summary.pointsRemaining)

    -- Group by category then subcategory, keeping the order the game lists them in.
    local order, byCategory = {}, {}
    for _, achievement in ipairs(data.achievements) do
        local category = byCategory[achievement.category]
        if not category then
            category = { name = achievement.category, subOrder = {}, subs = {}, count = 0, points = 0 }
            byCategory[achievement.category] = category
            order[#order + 1] = category
        end
        local sub = category.subs[achievement.subcategory]
        if not sub then
            sub = { name = achievement.subcategory, items = {} }
            category.subs[achievement.subcategory] = sub
            category.subOrder[#category.subOrder + 1] = sub
        end
        sub.items[#sub.items + 1] = achievement
        category.count = category.count + 1
        category.points = category.points + (achievement.points or 0)
    end

    for _, category in ipairs(order) do
        out[#out + 1] = ""
        out[#out + 1] = string_format("## %s (%d uncompleted, %d pts)", category.name, category.count, category.points)
        for _, sub in ipairs(category.subOrder) do
            out[#out + 1] = ""
            out[#out + 1] = "### " .. sub.name
            -- Closest to done first, then by name
            table.sort(sub.items, function(a, b)
                if (a.percent or 0) ~= (b.percent or 0) then
                    return (a.percent or 0) > (b.percent or 0)
                end
                return (a.name or "") < (b.name or "")
            end)
            for _, achievement in ipairs(sub.items) do
                out[#out + 1] = Line(achievement)
                if achievement.remaining and #achievement.remaining > 0 then
                    local more = (achievement.moreRemaining or 0) > 0
                            and string_format(" (+%d more)", achievement.moreRemaining)
                        or ""
                    out[#out + 1] = "  - Remaining: " .. table_concat(achievement.remaining, "; ") .. more
                end
            end
        end
    end

    return table_concat(out, "\n") .. "\n"
end

CM.generators.RenderAchievementProgress = RenderAchievementProgress

CM.DebugPrint("GENERATOR", "Achievement progress renderer loaded")
