import json
import math
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from tools import asset_home, mix_music


def write_wav(path, samples, rate=48000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))
    return str(path)


def tone(seconds, freq=220.0, amp=0.3, rate=48000):
    return [amp * math.sin(2 * math.pi * freq * i / rate) for i in range(int(seconds * rate))]


class MixMusicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        (self.project / "output").mkdir()
        self.tracks = self.project / "tracks"
        self.tracks.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, segments):
        path = self.project / "work" / "music-plan.json"
        path.write_text(json.dumps({"out": "output/master-mixed.mp4", "segments": segments}))
        return path

    def test_music_never_peaks_above_voice(self):
        voice = write_wav(self.project / "voice.wav", tone(3.0, amp=0.30))
        loud = write_wav(self.tracks / "loud.wav", tone(3.0, freq=110, amp=0.95))
        gain = mix_music.gain_to_sit_under(voice, loud, headroom_db=mix_music.MIN_HEADROOM_DB)
        self.assertLess(gain, 0, "a track louder than the voice must be pulled down")
        after = mix_music.level_dbfs(loud) + gain
        self.assertLessEqual(after, mix_music.level_dbfs(voice) - mix_music.MIN_HEADROOM_DB + 0.01)

    def test_fail_soft_on_bad_track(self):
        (self.tracks / "broken.wav").write_bytes(b"not audio at all")
        plan = self._plan([{"from_s": 0.0, "to_s": 2.0, "track": "tracks/broken.wav",
                            "gain_db": -22}])
        result = mix_music.apply(plan, self.project, master=self.project / "output" / "master.mp4",
                                 log=lambda *_: None)
        self.assertTrue(result["degraded"])
        self.assertTrue(any("broken" in w for w in result["warnings"]))
        self.assertEqual(result["exit_code"], 0, "a music failure must not fail the phase")

    def test_no_music_direction_does_nothing_and_says_so(self):
        plan = self._plan([])
        result = mix_music.apply(plan, self.project, master=self.project / "output" / "master.mp4",
                                 log=lambda *_: None)
        self.assertEqual(result["segments"], 0)
        self.assertTrue(any("no music" in w.lower() for w in result["warnings"]))

    def test_segment_past_the_master_is_trimmed_not_rejected(self):
        segs = mix_music.resolve_segments(
            [{"from_s": 0.0, "to_s": 90.0, "track": "tracks/a.wav", "gain_db": -22}],
            master_duration_s=30.0)
        self.assertEqual(segs[0]["to_s"], 30.0)

    def test_short_track_reports_which_strategy_it_used(self):
        seg = mix_music.fit_track({"from_s": 0.0, "to_s": 20.0, "track": "tracks/a.wav"},
                                  track_duration_s=8.0)
        self.assertIn(seg["fit"], ("loop", "shorten"))
        self.assertIn("8.0", seg["fit_note"])

    def test_overlapping_segments_are_rejected(self):
        with self.assertRaises(mix_music.MusicError):
            mix_music.resolve_segments([
                {"from_s": 0.0, "to_s": 10.0, "track": "tracks/a.wav"},
                {"from_s": 8.0, "to_s": 20.0, "track": "tracks/b.wav"},
            ], master_duration_s=30.0)

    def test_touching_segments_are_allowed(self):
        segs = mix_music.resolve_segments([
            {"from_s": 0.0, "to_s": 10.0, "track": "tracks/a.wav"},
            {"from_s": 10.0, "to_s": 20.0, "track": "tracks/b.wav"},
        ], master_duration_s=30.0)
        self.assertEqual(len(segs), 2)

    def test_moods_map_to_the_tone_system(self):
        for tone_name in ("Serious", "Inspirational", "Professional", "Humorous", "Casual", "Edgy"):
            self.assertIsNotNone(mix_music.mood_for_tone(tone_name),
                                 f"tone {tone_name} has no mood mapping")


class ResolveTrackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"GASPOL_VIDEO_HOME": str(self.root / "home")})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_library_form_resolves_into_the_home_music_library(self):
        path = mix_music.resolve_track(self.root / "project", "library:warm-uplift")
        self.assertEqual(path, asset_home.library("music") / "tracks" / "warm-uplift.mp3")

    def test_project_relative_and_absolute_paths_are_unchanged(self):
        project = self.root / "project"
        self.assertEqual(mix_music.resolve_track(project, "tracks/a.mp3"), project / "tracks" / "a.mp3")
        absolute = self.root / "elsewhere" / "b.mp3"
        self.assertEqual(mix_music.resolve_track(project, str(absolute)), absolute)

    def test_apply_reads_a_library_track_from_home(self):
        project = self.root / "project"
        (project / "work").mkdir(parents=True)
        tracks = asset_home.library("music") / "tracks"
        tracks.mkdir()
        (tracks / "broken.mp3").write_bytes(b"not audio at all")
        plan = project / "work" / "music-plan.json"
        plan.write_text(json.dumps({"segments": [
            {"from_s": 0.0, "to_s": 2.0, "track": "library:broken"}]}))
        result = mix_music.apply(plan, project, master=project / "master.mp4", log=lambda *_: None)
        self.assertTrue(result["degraded"])
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(any("library:broken" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
