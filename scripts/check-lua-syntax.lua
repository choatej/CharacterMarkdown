-- Syntax-check Lua files without running them: luajit scripts/check-lua-syntax.lua file1.lua file2.lua ...
-- Uses loadfile, which needs nothing beyond the interpreter (luajit -bl needs the jit.* modules, which
-- some builds, including the one the CI workflow installs, do not ship). Exits 1 if any file fails.

local failed = 0
for _, path in ipairs(arg) do
    local chunk, err = loadfile(path)
    if not chunk then
        io.stderr:write("  ✗ ", tostring(err), "\n")
        failed = failed + 1
    end
end

if failed > 0 then
    io.stderr:write(string.format("  ✗ %d file(s) with Lua syntax errors\n", failed))
    os.exit(1)
end
