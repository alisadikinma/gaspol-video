import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tests.py import media
from tools import thumb_verify

ROWS = thumb_verify.QUESTIONS


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = thumb_verify.main(list(argv))
    return code, out.getvalue() + err.getvalue()


@media.requires_ffmpeg
class ThumbVerifyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)
        (self.project / "packaging").mkdir()
        self.sheet = self.project / "packaging" / "thumb-verify.md"

    def png(self, name, colour="red"):
        path = self.project / "packaging" / name
        media._run([media.FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=%s:s=32x18:d=1" % colour, "-frames:v", "1", str(path)])
        return path

    def fill(self, section, cells):
        """Set the verdict cells of one section (matched by file name) in the sheet."""
        out, current, k = [], None, 0
        for line in self.sheet.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                current, k = line[3:].strip(), 0
            if current == section and line.startswith("| ") and line[2:3].isdigit():
                cell = cells[k] if isinstance(cells, list) else cells
                line = "| %d | %s | %s |" % (k + 1, ROWS[k], cell)
                k += 1
            out.append(line)
        self.sheet.write_text("\n".join(out) + "\n", encoding="utf-8")

    def init_two(self):
        self.png("thumb-A.png", "red")
        self.png("thumb-b2.png", "blue")
        self.assertEqual(run("init", str(self.project))[0], 0)

    def test_jpg_and_jpeg_thumbnails_are_covered(self):
        self.png("thumb-C.jpg", "green")
        self.png("thumb-D.jpeg", "yellow")
        self.assertEqual(run("init", str(self.project))[0], 0)
        text = self.sheet.read_text(encoding="utf-8")
        self.assertIn("## thumb-C.jpg", text)
        self.assertIn("## thumb-D.jpeg", text)
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("thumb-C.jpg", out)
        # a jpg dropped in after init has no section: check must say so
        self.png("thumb-E.jpg", "white")
        self.assertIn("thumb-E.jpg: no section", run("check", str(self.project))[1])

    def test_init_does_not_follow_planted_symlink_temp_name(self):
        victim = self.project / "victim.txt"
        victim.write_text("keep")
        (self.project / "packaging" / "thumb-verify.md.tmp").symlink_to(victim)
        self.png("thumb-A.png")
        self.assertEqual(run("init", str(self.project))[0], 0)
        self.assertEqual(victim.read_text(), "keep")
        self.assertIn("## thumb-A.png", self.sheet.read_text(encoding="utf-8"))

    def test_init_writes_one_section_per_thumbnail_with_fixed_rows(self):
        self.init_two()
        text = self.sheet.read_text(encoding="utf-8")
        self.assertIn("## thumb-A.png", text)
        self.assertIn("## thumb-b2.png", text)
        self.assertEqual(text.count("## thumb-"), 2)
        for row in ("text spelled correctly", "text legible at phone size",
                    "face recognisable (if cast shown)", "one dominant element",
                    "matches the video's promise"):
            self.assertEqual(text.count(row), 2, row)

    def test_zero_thumbnails_prints_nothing_to_do_exit_0(self):
        code, out = run("init", str(self.project))
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertFalse(self.sheet.exists())

    def test_check_exits_2_when_sheet_missing(self):
        self.png("thumb-A.png")
        self.assertEqual(run("check", str(self.project))[0], 2)

    def test_check_exits_1_on_empty_cells_and_lists_each(self):
        self.init_two()
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("thumb-A.png q1", out)
        self.assertIn("thumb-b2.png q5", out)

    def test_check_exits_0_when_all_pass(self):
        self.init_two()
        self.fill("thumb-A.png", "PASS")
        self.fill("thumb-b2.png", "PASS")
        self.assertEqual(run("check", str(self.project))[0], 0)

    def test_fail_cell_fails_only_that_thumbnail(self):
        self.init_two()
        self.fill("thumb-A.png", "PASS")
        self.fill("thumb-b2.png", ["PASS", "FAIL: the word is spelled TIME", "PASS", "PASS", "PASS"])
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("thumb-b2.png q2", out)
        self.assertIn("spelled TIME", out)
        self.assertNotIn("thumb-A.png", out)

    def test_malformed_cell_fails(self):
        self.init_two()
        self.fill("thumb-A.png", "looks fine")
        self.fill("thumb-b2.png", "PASS")
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("must start with PASS", out)

    def test_unsure_is_a_note_not_a_failure(self):
        self.init_two()
        self.fill("thumb-A.png", ["UNSURE: face is tiny", "PASS", "PASS", "PASS", "PASS"])
        self.fill("thumb-b2.png", "PASS")
        code, out = run("check", str(self.project))
        self.assertEqual(code, 0)
        self.assertIn("NOTE", out)

    def test_changed_image_after_judged_fails(self):
        self.init_two()
        self.fill("thumb-A.png", "PASS")
        self.fill("thumb-b2.png", "PASS")
        self.png("thumb-A.png", "green")
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("different image", out)
        self.assertIn("thumb-A.png", out)

    def test_image_removed_after_judged_fails(self):
        self.init_two()
        self.fill("thumb-A.png", "PASS")
        self.fill("thumb-b2.png", "PASS")
        (self.project / "packaging" / "thumb-A.png").unlink()
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("missing", out)

    def test_thumbnail_without_section_fails(self):
        self.init_two()
        self.fill("thumb-A.png", "PASS")
        self.fill("thumb-b2.png", "PASS")
        self.png("thumb-C.png", "green")
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("thumb-C.png: no section", out)

    def test_rerun_init_keeps_verdicts_of_unchanged_and_clears_changed(self):
        self.init_two()
        self.fill("thumb-A.png", "PASS")
        self.fill("thumb-b2.png", "PASS")
        self.png("thumb-b2.png", "green")
        self.assertEqual(run("init", str(self.project))[0], 0)
        text = self.sheet.read_text(encoding="utf-8")
        a, b = text.split("## thumb-b2.png")
        self.assertEqual(a.count("| PASS |"), 5)
        self.assertEqual(b.count("| PASS |"), 0)
        self.assertIn("changed since last judged", b)

    def test_edited_cell_hiding_a_fail_is_still_read_as_written(self):
        self.init_two()
        self.fill("thumb-A.png", "PASS")
        self.fill("thumb-b2.png", ["PASS", "PASS", "PASS", "PASS", "FAIL: promise not in video"])
        # prose above the table claims everything passed; only the cells count
        text = self.sheet.read_text(encoding="utf-8").replace(
            "# Thumbnail verify", "# Thumbnail verify\n\nALL PASS, verified.", 1)
        self.sheet.write_text(text, encoding="utf-8")
        code, out = run("check", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("thumb-b2.png q5", out)


if __name__ == "__main__":
    unittest.main()
