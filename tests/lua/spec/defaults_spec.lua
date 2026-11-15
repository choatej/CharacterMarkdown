-- Settings defaults: the table every other settings feature builds on.

describe("Settings.Defaults", function()
    local defaults

    before_each(function()
        ESO.NewAddon()
        ESO.Load("src/settings/Defaults.lua")
        defaults = CharacterMarkdown.Settings.Defaults:GetAll()
    end)

    it("returns a table of plain values", function()
        local bad = {}
        for key, value in pairs(defaults) do
            local kind = type(value)
            if kind ~= "boolean" and kind ~= "string" and kind ~= "number" then
                bad[#bad + 1] = key .. " is a " .. kind
            end
        end
        eq(bad, {})
    end)

    it("returns a fresh table on every call", function()
        local a = CharacterMarkdown.Settings.Defaults:GetAll()
        a.includeHeader = "changed"
        eq(CharacterMarkdown.Settings.Defaults:GetAll().includeHeader, true)
    end)

    it("keeps the opt-in sections off by default", function()
        for _, key in ipairs({ "includeAntiquities", "includeAchievements", "includeQuests", "includeMail" }) do
            eq(defaults[key], false, key)
        end
    end)

    it("keeps the core sections on by default", function()
        for _, key in ipairs({ "includeHeader", "includeEquipment", "includeSkillBars", "includeChampionPoints" }) do
            eq(defaults[key], true, key)
        end
    end)
end)
