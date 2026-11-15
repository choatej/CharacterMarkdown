-- CharacterMarkdown - Achievements Data Collector
-- Composition logic moved from API layer

local CM = CharacterMarkdown

local function CollectAchievementsData()
    -- Use API layer granular functions (composition at collector level)
    local points = CM.api.achievements.GetPoints()
    local recent = CM.api.achievements.GetRecent()

    -- Collect category data
    local categories = {}
    local numCategories = CM.api.achievements.GetNumCategories()

    for i = 1, numCategories do
        local info = CM.api.achievements.GetCategoryInfo(i)
        if info and info.name then
            local subcategories = {}
            if info.numSubCategories and info.numSubCategories > 0 then
                for j = 1, info.numSubCategories do
                    local subInfo = CM.api.achievements.GetSubCategoryInfo(i, j)
                    if subInfo and subInfo.name then
                        table.insert(subcategories, {
                            name = subInfo.name,
                            earned = subInfo.earned or 0,
                            total = subInfo.total or 0,
                            percent = (subInfo.total and subInfo.total > 0)
                                    and math.floor((subInfo.earned / subInfo.total) * 100)
                                or 0,
                        })
                    end
                end
            end

            table.insert(categories, {
                name = info.name,
                earned = info.earned or 0,
                total = info.total or 0,
                percent = (info.total and info.total > 0) and math.floor((info.earned / info.total) * 100) or 0,
                numAchievements = info.numAchievements or 0,
                subcategories = subcategories,
            })
        end
    end

    local achievements = {}

    -- Transform API data to expected format (backward compatibility)
    achievements.points = points.earned or 0
    achievements.total = points.total or 0
    achievements.recent = recent or {}
    achievements.categories = categories

    -- Add computed fields
    local totalAchievements = 0

    for _, cat in ipairs(categories) do
        totalAchievements = totalAchievements + (cat.numAchievements or 0)
    end

    achievements.summary = {
        completionPercent = achievements.total > 0 and math.floor((achievements.points / achievements.total) * 100)
            or 0,
        recentCount = recent and #recent or 0,
        categoryCount = #categories,
        totalAchievements = totalAchievements,
        earnedPoints = achievements.points,
        totalPoints = achievements.total,
    }

    local settings = CM.GetSettings()
    if settings and settings.includeAchievementDetail and recent then
        local details = {}
        for _, entry in ipairs(recent) do
            if entry.id and CM.api.achievements.GetAchievementDetail then
                local detail = CM.api.achievements.GetAchievementDetail(entry.id)
                if detail then
                    table.insert(details, detail)
                end
            end
        end
        achievements.details = details
    end

    return achievements
end

-- =====================================================
-- UNCOMPLETED ACHIEVEMENT PROGRESS (separate, opt-in dump)
-- =====================================================

-- The full list is large (thousands of achievements), so it is not part of the normal export.
-- It is collected on demand by `/cm save achievements` and scanned in steps so the game
-- stays responsive.
local STEP_DELAY_MS = 1

--- Collect progress on every uncompleted achievement.
-- @param onDone function(data) data = { summary, achievements = { ... } }
-- @param onError function(message) optional
local function CollectUncompletedAchievements(onDone, onError)
    local api = CM.api.achievements

    -- Work list: one entry per category / subcategory to scan
    local steps = {}
    for cat = 1, api.GetNumCategories() do
        local info = api.GetCategoryInfo(cat)
        if info and info.name then
            if (info.numAchievements or 0) > 0 then
                steps[#steps + 1] = {
                    cat = cat,
                    sub = nil,
                    category = info.name,
                    subcategory = "General",
                    count = info.numAchievements,
                }
            end
            for sub = 1, info.numSubCategories or 0 do
                local subInfo = api.GetSubCategoryInfo(cat, sub)
                if subInfo and subInfo.name and (subInfo.numAchievements or 0) > 0 then
                    steps[#steps + 1] = {
                        cat = cat,
                        sub = sub,
                        category = info.name,
                        subcategory = subInfo.name,
                        count = subInfo.numAchievements,
                    }
                end
            end
        end
    end

    local data = {
        characterName = GetUnitName and GetUnitName("player") or nil,
        timestamp = CM.api.time.GetNow(),
        achievements = {},
        summary = { uncompleted = 0, pointsRemaining = 0, listsScanned = #steps },
    }
    local seen = {} -- a step shared by several lists must not be counted twice
    local nextStep = 1

    local function ScanList(step)
        for index = 1, step.count do
            local listedId = api.GetAchievementIdAt(step.cat, step.sub, index)
            if listedId then
                local id, name, points = api.GetFirstIncompleteStep(listedId)
                if id and not seen[id] then
                    seen[id] = true
                    local progress = api.GetProgressSummary(id)
                    local percent = progress.required > 0 and math.floor((progress.done / progress.required) * 100) or 0
                    data.achievements[#data.achievements + 1] = {
                        id = id,
                        name = name,
                        category = step.category,
                        subcategory = step.subcategory,
                        points = points or 0,
                        done = progress.done,
                        required = progress.required,
                        percent = percent,
                        remaining = progress.remaining,
                        moreRemaining = progress.moreRemaining,
                    }
                    data.summary.uncompleted = data.summary.uncompleted + 1
                    data.summary.pointsRemaining = data.summary.pointsRemaining + (points or 0)
                end
            end
        end
    end

    local function Step()
        local step = steps[nextStep]
        if not step then
            onDone(data)
            return
        end
        local ok, err = pcall(ScanList, step)
        if not ok then
            -- One bad list should not lose the rest
            CM.DebugPrint(
                "ACHIEVEMENTS",
                string.format("scan of %s / %s failed: %s", step.category, step.subcategory, tostring(err))
            )
        end
        nextStep = nextStep + 1
        zo_callLater(Step, STEP_DELAY_MS)
    end

    if #steps == 0 then
        if onError then
            onError("No achievement categories found")
        end
        return
    end
    Step()
end

CM.collectors.CollectUncompletedAchievements = CollectUncompletedAchievements
CM.collectors.CollectAchievementsData = CollectAchievementsData

CM.DebugPrint("COLLECTOR", "Achievements collector module loaded")
