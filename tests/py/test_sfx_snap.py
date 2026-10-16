import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.py.media import requires_ffmpeg
from tests.py.test_vidkit import click_wav
from tools import sfx_snap

CLICKS = [0.5, 1.5, 2.5, 3.5, 4.5]


@requires_ffmpeg
class SfxSnapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        self.music = click_wav(self.project / "music.wav", CLICKS)
        self.plan = self.project / "work" / "sfx-plan.json"
        self.out = self.project / "work" / "sfx-plan.snapped.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, events):
        self.plan.write_text(json.dumps({"events": events}, indent=1))

    def _run(self, *extra, music=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = sfx_snap.main([str(self.project), "--music", music or self.music, *extra])
        return rc, buf.getvalue()

    def _times(self):
        return [e["at_s"] for e in json.loads(self.out.read_text())["events"]]

    def test_relative_paths_resolve_against_project_not_cwd(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        decoy = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(decoy, ignore_errors=True))
        (decoy / "work").mkdir()
        decoy_plan = decoy / "work" / "sfx-plan.json"
        decoy_plan.write_text(json.dumps({"events": [{"sfx_id": "decoy", "at_s": 3.0}]}))
        (decoy / "music.wav").write_bytes(b"not audio")
        before = os.getcwd()
        os.chdir(decoy)
        self.addCleanup(os.chdir, before)
        rc, text = self._run(music="music.wav")
        self.assertEqual(rc, 0, text)
        self.assertEqual(json.loads(decoy_plan.read_text())["events"][0]["sfx_id"], "decoy")
        self.assertFalse((decoy / "work" / "sfx-plan.snapped.json").exists())
        self.assertAlmostEqual(self._times()[0], 1.5, delta=0.03)

    def test_absolute_paths_stay_absolute(self):
        elsewhere = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(elsewhere, ignore_errors=True))
        plan = elsewhere / "p.json"
        plan.write_text(json.dumps({"events": [{"sfx_id": "hit", "at_s": 1.55}]}))
        out = elsewhere / "o.json"
        rc, text = self._run("--plan", str(plan), "--out", str(out))
        self.assertEqual(rc, 0, text)
        self.assertTrue(out.exists())

    def test_snaps_near_cue_and_leaves_far_cue(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}, {"sfx_id": "whoosh", "at_s": 3.0}])
        rc, text = self._run()
        self.assertEqual(rc, 0, text)
        got = self._times()
        self.assertAlmostEqual(got[0], 1.5, delta=0.03)
        self.assertEqual(got[1], 3.0)
        self.assertIn("hit", text)
        self.assertIn("1 moved", text)
        self.assertIn("1 unchanged", text)

    def test_original_plan_is_byte_identical(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        before = self.plan.read_bytes()
        self._run()
        self.assertEqual(self.plan.read_bytes(), before)

    def test_silent_music_exits_2_and_writes_nothing(self):
        silent = click_wav(self.project / "silent.wav", [], noise=0.0)
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        rc, text = self._run(music=silent)
        self.assertEqual(rc, 2)
        self.assertIn("no beats", text.lower())
        self.assertFalse(self.out.exists())

    def test_stack_parent_snaps_and_layers_keep_offsets(self):
        stack = [{"sfx_id": "riser", "offset_s": -0.3}, {"sfx_id": "boom", "offset_s": 0.0, "gain_db": -3}]
        self._write([{"stack": stack, "at_s": 2.56, "note": "reveal"}])
        rc, _ = self._run()
        self.assertEqual(rc, 0)
        ev = json.loads(self.out.read_text())["events"][0]
        self.assertAlmostEqual(ev["at_s"], 2.5, delta=0.03)
        self.assertEqual(ev["stack"], stack)
        self.assertEqual(ev["note"], "reveal")

    def test_cue_before_first_and_after_last_beat(self):
        self._write([{"sfx_id": "a", "at_s": 0.0}, {"sfx_id": "b", "at_s": 5.9}])
        self._run()
        self.assertEqual(self._times(), [0.0, 5.9])

    def test_window_zero_moves_nothing(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        rc, text = self._run("--window", "0")
        self.assertEqual(rc, 0)
        self.assertEqual(self._times(), [1.55])
        self.assertIn("0 moved", text)

    def test_custom_out_path(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        custom = self.project / "work" / "other.json"
        rc, _ = self._run("--out", str(custom))
        self.assertEqual(rc, 0)
        self.assertTrue(custom.exists())
        self.assertFalse(self.out.exists())

    def test_out_equal_to_plan_is_refused(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        before = self.plan.read_bytes()
        rc, _ = self._run("--out", str(self.plan))
        self.assertEqual(rc, 1)
        self.assertEqual(self.plan.read_bytes(), before)

    def test_missing_plan_fails(self):
        rc, text = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("sfx-plan.json", text)

    def test_empty_plan_fails_without_output(self):
        self._write([])
        rc, _ = self._run()
        self.assertEqual(rc, 1)
        self.assertFalse(self.out.exists())

    def test_missing_music_fails(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        rc, _ = self._run(music=str(self.project / "gone.wav"))
        self.assertEqual(rc, 1)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
