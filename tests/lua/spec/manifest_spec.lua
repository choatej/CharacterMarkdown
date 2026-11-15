-- Every Lua file the manifest lists must exist and compile under LuaJIT (Lua 5.1 syntax; no goto).

describe("manifest", function()
    local files = ESO.ManifestFiles()

    it("lists Lua files", function()
        truthy(#files > 50, "expected the manifest to list the add-on's Lua files")
    end)

    it("lists each file once", function()
        local seen = {}
        for _, path in ipairs(files) do
            falsy(seen[path], path .. " is listed twice")
            seen[path] = true
        end
    end)

    it("lists only files that exist and compile", function()
        local problems = {}
        for _, path in ipairs(files) do
            local chunk, err = loadfile(ESO.root .. "/" .. path)
            if not chunk then
                problems[#problems + 1] = tostring(err)
            end
        end
        eq(problems, {})
    end)
end)
