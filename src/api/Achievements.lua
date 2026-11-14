-- CharacterMarkdown - API Layer - Achievements
-- Abstraction for achievement points and categories

local CM = CharacterMarkdown
CM.api = CM.api or {}
CM.api.achievements = {}

local api = CM.api.achievements

-- =====================================================
-- GRANULAR GETTERS
-- =====================================================

function api.GetPoints()
    local earned = CM.SafeCall(GetEarnedAchievementPoints) or 0
    local total = CM.SafeCall(GetTotalAchievementPoints) or 0
    return {
        earned = earned,
        total = total,
    }
end

function api.GetNumCategories()
    return CM.SafeCall(GetNumAchievementCategories) or 0
end

function api.GetCategoryInfo(catIndex)
    local _, name, numSubCats, numAch, earned, total, _ = CM.SafeCallMulti(GetAchievementCategoryInfo, catIndex)

    return {
        name = name,
        earned = earned,
        total = total,
        numSubCategories = numSubCats,
        numAchievements = numAch,
    }
end

function api.GetSubCategoryInfo(catIndex, subCatIndex)
    local _, name, numAch, earned, total = CM.SafeCallMulti(GetAchievementSubCategoryInfo, catIndex, subCatIndex)
    return {
        name = name,
        earned = earned,
        total = total,
        numAchievements = numAch,
    }
end

function api.GetRecent()
    local success, id1, id2, id3, id4, id5 = CM.SafeCallMulti(GetRecentlyCompletedAchievements, 5)
    local ids = {}
    if success then
        for _, id in ipairs({ id1, id2, id3, id4, id5 }) do
            if id and type(id) == "number" then
                table.insert(ids, id)
            end
        end
    end
    local recent = {}
    for _, id in ipairs(ids) do
        if type(id) == "number" then
            local _, name, _, _, _, _, date, time = CM.SafeCallMulti(GetAchievementInfo, id)
            if name then
                table.insert(recent, {
                    id = id,
                    name = name,
                    date = date,
                    time = time,
                })
            end
        end
    end
    return recent
end

---Optional criterion detail for a single achievement (P50 GetAchievementCriterion / Progress).
function api.GetAchievementDetail(achievementId)
    if not achievementId then
        return nil
    end
    local ok, name, description, points, _, completed = CM.SafeCallMulti(GetAchievementInfo, achievementId)
    if not ok or not name then
        return nil
    end

    local progress = nil
    if GetAchievementProgress then
        progress = CM.SafeCall(GetAchievementProgress, achievementId)
    end

    local criteria = {}
    local numCriteria = CM.SafeCall(GetAchievementNumCriteria, achievementId) or 0
    for i = 1, numCriteria do
        local cok, descriptionText, numCompleted, numRequired =
            CM.SafeCallMulti(GetAchievementCriterion, achievementId, i)
        if cok and descriptionText then
            table.insert(criteria, {
                description = descriptionText,
                completed = numCompleted or 0,
                required = numRequired or 0,
            })
        end
    end

    local timestamp = nil
    if GetAchievementTimestamp then
        timestamp = CM.SafeCall(GetAchievementTimestamp, achievementId)
    end

    return {
        id = achievementId,
        name = name,
        description = description,
        points = points,
        completed = completed,
        progress = progress,
        criteria = criteria,
        timestamp = timestamp,
    }
end

-- =====================================================
-- UNCOMPLETED ACHIEVEMENT PROGRESS
-- =====================================================

---Achievement id at a position in the achievements tree.
---@param catIndex number top-level category index
---@param subCatIndex number|nil nil for achievements listed directly under the category
---@param achIndex number position within that list
---@return number|nil
function api.GetAchievementIdAt(catIndex, subCatIndex, achIndex)
    local id = CM.SafeCall(GetAchievementId, catIndex, subCatIndex, achIndex)
    if type(id) == "number" and id ~= 0 then
        return id
    end
    return nil
end

---First step of an achievement that is not complete yet.
-- Some achievements are chains ("Slay 10 / 100 / 1000"); the list shows the first step,
-- and the game links the later ones. Returns nil when the whole chain is complete.
---@param achievementId number
---@return number|nil achievementId of the first incomplete step
---@return string|nil name
---@return number|nil points
function api.GetFirstIncompleteStep(achievementId)
    local id = achievementId
    -- The guard stops a malformed (looping) chain from running forever
    for _ = 1, 50 do
        if not id or id == 0 then
            return nil
        end
        local ok, name, _, points, _, completed = CM.SafeCallMulti(GetAchievementInfo, id)
        if not ok or not name then
            return nil
        end
        if not completed then
            return id, name, points
        end
        id = CM.SafeCall(GetNextAchievementInLine, id)
    end
    return nil
end

---Progress of one achievement, summed over its criteria.
---@param achievementId number
---@param maxListed number|nil cap on named unfinished criteria (default 25)
---@return table { done, required, remaining = { names }, moreRemaining }
function api.GetProgressSummary(achievementId, maxListed)
    maxListed = maxListed or 25
    local numCriteria = CM.SafeCall(GetAchievementNumCriteria, achievementId) or 0
    local done, required = 0, 0
    local remaining, more = {}, 0

    for i = 1, numCriteria do
        local ok, description, numCompleted, numRequired = CM.SafeCallMulti(GetAchievementCriterion, achievementId, i)
        if ok then
            numCompleted = tonumber(numCompleted) or 0
            numRequired = tonumber(numRequired) or 0
            done = done + math.min(numCompleted, numRequired)
            required = required + numRequired
            -- Name the unfinished items of checklist achievements; a single counter has nothing to list
            if numCriteria > 1 and numCompleted < numRequired and description and description ~= "" then
                if #remaining < maxListed then
                    table.insert(remaining, description)
                else
                    more = more + 1
                end
            end
        end
    end

    return { done = done, required = required, remaining = remaining, moreRemaining = more }
end
