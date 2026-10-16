import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_silent_music_exits_3_and_writes_nothing(self):
        silent = click_wav(self.project / "silent.wav", [], noise=0.0)
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        rc, text = self._run(music=silent)
        self.assertEqual(rc, 3)
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
        self.assertEqual(rc, 2)
        self.assertEqual(self.plan.read_bytes(), before)

    def test_missing_plan_fails(self):
        rc, text = self._run()
        self.assertEqual(rc, 2)
        self.assertIn("sfx-plan.json", text)

    def test_empty_plan_fails_without_output(self):
        self._write([])
        rc, _ = self._run()
        self.assertEqual(rc, 2)
        self.assertFalse(self.out.exists())

    def test_missing_music_fails(self):
        self._write([{"sfx_id": "hit", "at_s": 1.55}])
        rc, _ = self._run(music=str(self.project / "gone.wav"))
        self.assertEqual(rc, 2)
        self.assertFalse(self.out.exists())

    def test_malformed_stack_exits_2_with_message(self):
        self._write([{"stack": "bad", "at_s": 1.55}])
        rc, text = self._run()
        self.assertEqual(rc, 2)
        self.assertIn("stack", text)
        self.assertNotIn("Traceback", text)
        self.assertFalse(self.out.exists())

    def test_stack_entry_not_an_object_exits_2(self):
        self._write([{"stack": ["x"], "at_s": 1.55}])
        rc, text = self._run()
        self.assertEqual(rc, 2)
        self.assertIn("stack", text)


@requires_ffmpeg
class SfxSnapMusicPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "proj"
        (self.project / "work").mkdir(parents=True)
        (self.project / "tracks").mkdir()
        self.home = Path(self.tmp.name) / "home"
        patcher = mock.patch.dict(os.environ, {"GASPOL_VIDEO_HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plan = self.project / "work" / "sfx-plan.json"
        self.out = self.project / "work" / "sfx-plan.snapped.json"
        self.music_plan = self.project / "work" / "music-plan.json"

    def _library_track(self, name, clicks, seconds):
        d = self.home / "library" / "music" / "tracks"
        d.mkdir(parents=True, exist_ok=True)
        return click_wav(d / f"{name}.mp3", clicks, seconds=seconds)

    def _run(self, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = sfx_snap.main([str(self.project), *extra])
        return rc, buf.getvalue()

    def _events(self, times):
        self.plan.write_text(json.dumps({"events": [{"sfx_id": f"e{i}", "at_s": t}
                                                    for i, t in enumerate(times)]}))

    def _got(self):
        return [e["at_s"] for e in json.loads(self.out.read_text())["events"]]

    def test_two_segments_offset_and_cut_at_segment_length(self):
        self._library_track("a", [0.5, 1.5, 4.5], 6.0)     # 4.5 is past the 3 s segment
        self._library_track("b", [0.2, 1.0, 2.0], 4.0)
        self.music_plan.write_text(json.dumps({"segments": [
            {"from_s": 0, "to_s": 3, "track": "library:a"},
            {"from_s": 10, "to_s": 13, "track": "library:b"}]}))
        # 10.25 -> 10.2, 12.03 -> 12.0, 4.5 would only snap if a beat leaked past the cut, 1.55 -> 1.5
        self._events([1.55, 4.5, 10.25, 12.03])
        rc, text = self._run("--music-plan")
        self.assertEqual(rc, 0, text)
        got = self._got()
        self.assertAlmostEqual(got[0], 1.5, delta=0.03)
        self.assertEqual(got[1], 4.5)
        self.assertAlmostEqual(got[2], 10.2, delta=0.03)
        self.assertAlmostEqual(got[3], 12.0, delta=0.03)

    def test_short_track_repeats_its_beats_for_a_looped_segment(self):
        self._library_track("short", [0.5, 1.5], 2.0)
        self.music_plan.write_text(json.dumps({"segments": [
            {"from_s": 1, "to_s": 6, "track": "library:short"}]}))
        # looped beats land at 1.5, 2.5, 3.5, 4.5, 5.5
        self._events([3.55, 5.45])
        rc, text = self._run("--music-plan")
        self.assertEqual(rc, 0, text)
        got = self._got()
        self.assertAlmostEqual(got[0], 3.5, delta=0.03)
        self.assertAlmostEqual(got[1], 5.5, delta=0.03)

    def test_path_track_is_relative_to_project(self):
        click_wav(self.project / "tracks" / "t.wav", [0.5, 1.5], seconds=3.0)
        self.music_plan.write_text(json.dumps({"segments": [
            {"from_s": 2, "to_s": 5, "track": "tracks/t.wav"}]}))
        self._events([2.55])
        rc, text = self._run("--music-plan", "work/music-plan.json")
        self.assertEqual(rc, 0, text)
        self.assertAlmostEqual(self._got()[0], 2.5, delta=0.03)

    def test_missing_track_exits_2_naming_segment_and_track(self):
        self.music_plan.write_text(json.dumps({"segments": [
            {"from_s": 0, "to_s": 3, "track": "library:ghost"}]}))
        self._events([1.0])
        rc, text = self._run("--music-plan")
        self.assertEqual(rc, 2)
        self.assertIn("segment 1", text)
        self.assertIn("library:ghost", text)
        self.assertFalse(self.out.exists())

    def test_no_beats_in_any_track_exits_3(self):
        self._library_track("quiet", [], 4.0)
        self.music_plan.write_text(json.dumps({"segments": [
            {"from_s": 0, "to_s": 3, "track": "library:quiet"}]}))
        self._events([1.0])
        rc, _ = self._run("--music-plan")
        self.assertEqual(rc, 3)
        self.assertFalse(self.out.exists())

    def test_music_and_music_plan_are_exclusive_and_one_is_required(self):
        self._events([1.0])
        rc, text = self._run()
        self.assertEqual(rc, 2)
        self.assertIn("--music", text)
        rc, _ = self._run("--music", "x.wav", "--music-plan")
        self.assertEqual(rc, 2)

    def test_missing_music_plan_file_exits_2(self):
        self._events([1.0])
        rc, text = self._run("--music-plan")
        self.assertEqual(rc, 2)
        self.assertIn("music-plan.json", text)


if __name__ == "__main__":
    unittest.main()
