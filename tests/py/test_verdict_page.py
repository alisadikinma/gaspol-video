import contextlib
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.py import media
from tools import verdict_page


def make_png(path, color="red", size="64x48"):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([media.FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c={color}:s={size}", "-frames:v", "1", str(path)], check=True)


def make_project(root, ids):
    for i in ids:
        make_png(Path(root) / "keyframes" / f"scene-{i}.png")


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = verdict_page.main(argv)
    return code, out.getvalue() + err.getvalue()


@media.requires_ffmpeg
class PageTest(unittest.TestCase):
    def test_page_builds_self_contained_html(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d, ["01", "02a", "10"])
            code, _ = run(["page", d])
            self.assertEqual(code, 0)
            html = (Path(d) / "output" / "verdict.html").read_text(encoding="utf-8")
            for i in ("01", "02a", "10"):
                self.assertIn(i, html)
            self.assertIn("data:image/jpeg;base64,", html)
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)
            self.assertLessEqual(len(html.encode()), 16 * 1024 * 1024)
            self.assertLess(html.index('data-scene="01"'), html.index('data-scene="02a"'))
            self.assertLess(html.index('data-scene="02a"'), html.index('data-scene="10"'))

    def test_script_in_scene_id_is_escaped(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d, ["x<script>alert(1)<b"])
            code, _ = run(["page", d])
            self.assertEqual(code, 0)
            html = (Path(d) / "output" / "verdict.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)", html)
            self.assertIn("&lt;script&gt;", html)

    def test_no_keyframes_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            code, _ = run(["page", d])
            self.assertEqual(code, 2)

    def test_sixty_scenes_under_cap_and_prints_size(self):
        with tempfile.TemporaryDirectory() as d:
            make_png(Path(d) / "keyframes" / "scene-01.png", size="1600x1200")
            for n in range(2, 61):
                (Path(d) / "keyframes" / f"scene-{n:02d}.png").write_bytes(
                    (Path(d) / "keyframes" / "scene-01.png").read_bytes())
            code, out = run(["page", d])
            self.assertEqual(code, 0)
            self.assertRegex(out, r"MB")
            self.assertRegex(out, r"level")
            size = (Path(d) / "output" / "verdict.html").stat().st_size
            self.assertLessEqual(size, 16 * 1024 * 1024)

    def test_oversize_steps_down_and_reports(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d, ["01", "02"])
            code, out = run(["page", d, "--max-mb", "0.0001"])
            self.assertEqual(code, 1)  # cannot fit: warns, still writes at the lowest level
            self.assertIn("level 6", out)


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        for i in ("01", "02a"):
            p = Path(self.d) / "keyframes" / f"scene-{i}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")
        (Path(self.d) / "work").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, scenes):
        (Path(self.d) / "work" / "verdict.json").write_text(
            json.dumps({"scenes": {k: {"verdict": v, "note": ""} for k, v in scenes.items()}}))

    def test_all_pass_exit_0(self):
        self.write({"01": "PASS", "02a": "PASS"})
        self.assertEqual(run(["check", self.d])[0], 0)

    def test_no_exit_1_names_scene(self):
        self.write({"01": "PASS", "02a": "NO"})
        code, out = run(["check", self.d])
        self.assertEqual(code, 1)
        self.assertIn("02a", out)

    def test_missing_scene_exit_1(self):
        self.write({"01": "PASS"})
        code, out = run(["check", self.d])
        self.assertEqual(code, 1)
        self.assertIn("02a", out)

    def test_maybe_needs_allow_flag(self):
        self.write({"01": "PASS", "02a": "MAYBE"})
        self.assertEqual(run(["check", self.d])[0], 1)
        self.assertEqual(run(["check", self.d, "--allow-maybe"])[0], 0)

    def test_absent_file_exit_2(self):
        self.assertEqual(run(["check", self.d])[0], 2)

    def test_malformed_json_exit_2(self):
        (Path(self.d) / "work" / "verdict.json").write_text("{nope")
        self.assertEqual(run(["check", self.d])[0], 2)

    def test_bad_verdict_value_exit_2(self):
        self.write({"01": "PASS", "02a": "GREAT"})
        self.assertEqual(run(["check", self.d])[0], 2)

    def test_wrong_shape_exit_2(self):
        (Path(self.d) / "work" / "verdict.json").write_text("[]")
        self.assertEqual(run(["check", self.d])[0], 2)


if __name__ == "__main__":
    unittest.main()
