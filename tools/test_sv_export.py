"""Tests for tools.sv_export. Run: python3 -m unittest tools.test_sv_export"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import sv_export

# Shaped like the file ESO writes (settings global first, then ours).
SAMPLE = """CharacterMarkdownSettings =
{
    ["x"] = 1,
}
CharacterMarkdownExport =
{
    ["characters"] =
    {
        ["Little Franny Boo"] =
        {
            ["exports"] =
            {
                ["markdown"] =
                {
                    ["charCount"] = %(count)d,
                    ["textParts"] =
                    {
                        [1] = "# Title \\"quoted\\"\\n\\n",
                        [2] = "caf\u00e9 \u2705 line\\n",
                    },
                    ["timestamp"] = 1762900000,
                },
                ["coach"] =
                {
                    ["charCount"] = 5,
                    ["textParts"] =
                    {
                        [1] = "coach",
                    },
                    ["timestamp"] = 1762900000,
                },
            },
        },
    },
    ["meta"] =
    {
        ["schema"] = 1,
    },
}
"""
TEXT = '# Title "quoted"\n\ncaf\u00e9 \u2705 line\n'


def sample(count: int | None = None) -> str:
    return SAMPLE % {"count": len(TEXT.encode("utf-8")) if count is None else count}


class SvExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write_sv(self, content: str) -> Path:
        path = self.dir / "CharacterMarkdown.lua"
        path.write_text(content, encoding="utf-8")
        return path

    def written_names(self, **kwargs) -> dict[str, bytes]:
        paths = sv_export.convert(self.write_sv(sample()), self.dir / "out", **kwargs)
        return {p.name: p.read_bytes() for p in paths}

    def test_roundtrip_is_exact(self) -> None:
        files = self.written_names(fmt="markdown")
        self.assertEqual(len(files), 1)
        self.assertEqual(next(iter(files.values())), TEXT.encode("utf-8"))

    def test_formats_are_written_side_by_side(self) -> None:
        files = self.written_names()
        self.assertEqual(len(files), 2)
        self.assertTrue(any(n.startswith("Little_Franny_Boo_2") for n in files))
        coach = [n for n in files if "_coach_" in n]
        self.assertEqual(len(coach), 1)
        self.assertEqual(files[coach[0]], b"coach")

    def test_file_names(self) -> None:
        names = sorted(self.written_names())
        self.assertRegex(names[0], r"^Little_Franny_Boo_\d{4}-\d{2}-\d{2}\.md$")
        self.assertRegex(names[1], r"^Little_Franny_Boo_coach_\d{4}-\d{2}-\d{2}\.md$")

    def test_extension_follows_format(self) -> None:
        self.assertTrue(sv_export.output_name("A", "json", {}).endswith("_json_undated.json"))
        self.assertTrue(sv_export.output_name("A", "markdown", {}).endswith("_undated.md"))

    def test_unknown_format(self) -> None:
        with self.assertRaisesRegex(sv_export.ExportError, "/cm save json"):
            sv_export.convert(self.write_sv(sample()), self.dir / "o", fmt="json")

    def test_character_filter_is_case_insensitive(self) -> None:
        written = sv_export.convert(
            self.write_sv(sample()), self.dir / "o", character="little franny boo"
        )
        self.assertEqual(len(written), 2)

    def test_unknown_character(self) -> None:
        with self.assertRaisesRegex(sv_export.ExportError, "Saved characters: Little Franny Boo"):
            sv_export.convert(self.write_sv(sample()), self.dir / "o", character="Nobody")

    def test_detects_lost_text(self) -> None:
        with self.assertRaisesRegex(sv_export.ExportError, "Part of the text was lost"):
            sv_export.convert(self.write_sv(sample(count=999)), self.dir / "o")

    def test_missing_part_is_reported(self) -> None:
        broken = sample().replace('[2] = "caf', '[3] = "caf')
        with self.assertRaisesRegex(sv_export.ExportError, "incomplete"):
            sv_export.convert(self.write_sv(broken), self.dir / "o")

    def test_no_export_in_file(self) -> None:
        path = self.write_sv("CharacterMarkdownSettings =\n{\n}\n")
        with self.assertRaisesRegex(sv_export.ExportError, "/cm save"):
            sv_export.convert(path, self.dir / "o")

    def test_missing_file(self) -> None:
        with self.assertRaisesRegex(sv_export.ExportError, "File not found"):
            sv_export.find_savedvariables(str(self.dir / "nope.lua"))

    def test_safe_name(self) -> None:
        self.assertEqual(sv_export.safe_name("Little Franny Boo"), "Little_Franny_Boo")
        self.assertEqual(sv_export.safe_name("Théo d'Arc"), "Théo_d_Arc")
        self.assertEqual(sv_export.safe_name("///"), "character")


if __name__ == "__main__":
    unittest.main()
