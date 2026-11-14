-- CharacterMarkdown - Antiquities Data Collector
-- Composition logic moved from API layer

local CM = CharacterMarkdown

-- A lead with less than this much time left is flagged as expiring soon.
local EXPIRING_SOON_SECONDS = 7 * 24 * 60 * 60

local function CollectAntiquitiesData()
    local sets = CM.api.antiquities.GetSets()

    local data = {
        sets = sets or {},
        summary = {
            totalAntiquities = 0,
            discoveredAntiquities = 0,
            activeLeads = 0,
            completedAntiquities = 0,
            totalSets = 0,
            completedSets = 0,
            leadsExpiringSoon = 0,
        },
        activeLeads = {},
    }

    local activeLeadsMap = {}

    for _, set in ipairs(data.sets) do
        set.discoveredAntiquities = 0
        set.completedAntiquities = 0

        for _, antiquity in ipairs(set.antiquities or {}) do
            data.summary.totalAntiquities = data.summary.totalAntiquities + 1

            if antiquity.isDiscovered then
                data.summary.discoveredAntiquities = data.summary.discoveredAntiquities + 1
                set.discoveredAntiquities = set.discoveredAntiquities + 1
            end

            if antiquity.isCompleted then
                data.summary.completedAntiquities = data.summary.completedAntiquities + 1
                set.completedAntiquities = set.completedAntiquities + 1
            end

            if antiquity.isInProgress or antiquity.hasLead then
                activeLeadsMap[antiquity.id] = antiquity
            end
        end

        if set.completedAntiquities == set.numAntiquities and set.numAntiquities > 0 then
            data.summary.completedSets = data.summary.completedSets + 1
        end
    end

    local inProgress = CM.api.antiquities.GetInProgressAntiquities()
    for _, antiquity in ipairs(inProgress) do
        activeLeadsMap[antiquity.id] = antiquity
    end

    local activeLeads = {}
    for _, antiquity in pairs(activeLeadsMap) do
        table.insert(activeLeads, antiquity)
    end

    data.summary.activeLeads = #activeLeads
    data.summary.totalSets = #data.sets

    data.summary.discoveryPercent = data.summary.totalAntiquities > 0
            and math.floor((data.summary.discoveredAntiquities / data.summary.totalAntiquities) * 100)
        or 0
    data.summary.completionPercent = data.summary.totalAntiquities > 0
            and math.floor((data.summary.completedAntiquities / data.summary.totalAntiquities) * 100)
        or 0
    data.summary.setCompletionPercent = data.summary.totalSets > 0
            and math.floor((data.summary.completedSets / data.summary.totalSets) * 100)
        or 0

    -- Flag leads that run out within a week
    for _, lead in ipairs(activeLeads) do
        local seconds = lead.leadSecondsRemaining
        lead.expiresSoon = type(seconds) == "number" and seconds > 0 and seconds <= EXPIRING_SOON_SECONDS
        if lead.expiresSoon then
            data.summary.leadsExpiringSoon = data.summary.leadsExpiringSoon + 1
        end
    end

    -- Leads with a timer first, soonest to expire on top; then by quality, then name
    table.sort(activeLeads, function(a, b)
        local aTimed = type(a.leadSecondsRemaining) == "number" and a.leadSecondsRemaining > 0
        local bTimed = type(b.leadSecondsRemaining) == "number" and b.leadSecondsRemaining > 0
        if aTimed ~= bTimed then
            return aTimed
        end
        if aTimed and a.leadSecondsRemaining ~= b.leadSecondsRemaining then
            return a.leadSecondsRemaining < b.leadSecondsRemaining
        end
        if (a.quality or 0) ~= (b.quality or 0) then
            return (a.quality or 0) > (b.quality or 0)
        end
        return (a.name or "") < (b.name or "")
    end)

    data.activeLeads = activeLeads
    data.activeScry = CM.api.antiquities.GetActiveScryTarget and CM.api.antiquities.GetActiveScryTarget() or nil

    return data
end

CM.collectors.CollectAntiquitiesData = CollectAntiquitiesData

CM.DebugPrint("COLLECTOR", "Antiquities collector module loaded")
