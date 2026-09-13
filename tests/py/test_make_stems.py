import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.py.media import make_clip, requires_ffmpeg
from tools import make_stems


def _probe_audio(path):
    """(sample_rate, channels, duration) of a file's first audio stream."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels,duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    rate, channels, duration = proc.stdout.strip().split(",")
    return int(rate), int(channels), float(duration)


class SfxBatchesTest(unittest.TestCase):
    def test_batches_of_30_and_a_skipped_count(self):
        events = [{"at_s": i * 0.1, "sfx_id": "pop"} for i in range(64)]
        events.append({"at_s": 999.0, "sfx_id": "pop"})  # past the duration
        batches, skipped = make_stems.sfx_batches(events, duration=100.0, batch=30)
        self.assertEqual([len(b) for b in batches], [30, 30, 4])
        self.assertEqual(skipped, 1)

    def test_empty_events_is_zero_batches_zero_skipped(self):
        batches, skipped = make_stems.sfx_batches([], duration=10.0)
        self.assertEqual(batches, [])
        self.assertEqual(skipped, 0)

    def test_every_event_past_duration_is_all_skipped(self):
        events = [{"at_s": 50.0, "sfx_id": "pop"}, {"at_s": 60.0, "sfx_id": "pop"}]
        batches, skipped = make_stems.sfx_batches(events, duration=10.0)
        self.assertEqual(batches, [])
        self.assertEqual(skipped, 2)


class MusicFilterTest(unittest.TestCase):
    def test_two_segment_plan_contains_fade_and_delay_values(self):
        segments = [
            {"from_s": 0.0, "to_s": 10.0, "track": "a.mp3", "gain_db": -22,
             "fade_in_s": 1.2, "fade_out_s": 2.0},
            {"from_s": 10.0, "to_s": 25.0, "track": "b.mp3", "gain_db": -18,
             "fade_in_s": 0.5, "fade_out_s": 3.0},
        ]
        filt, n = make_stems.music_filter(segments, duration=25.0)
        self.assertEqual(n, 2)
        self.assertIn("[1:a]", filt)
        self.assertIn("[2:a]", filt)
        self.assertIn("afade=t=in:d=1.2", filt)
        self.assertIn("afade=t=out:st=8.000:d=2.0", filt)
        self.assertIn("afade=t=in:d=0.5", filt)
        self.assertIn("afade=t=out:st=12.000:d=3.0", filt)
        self.assertIn("adelay=0:all=1", filt)
        self.assertIn("adelay=10000:all=1", filt)
        self.assertIn("volume=-22dB", filt)
        self.assertIn("volume=-18dB", filt)
        self.assertIn("[aout]", filt)

    def test_empty_segments_returns_no_filter(self):
        filt, n = make_stems.music_filter([], duration=10.0)
        self.assertIsNone(filt)
        self.assertEqual(n, 0)


class RealStemsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "output").mkdir()
        (self.project / "work").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _master(self, seconds=4.0):
        return make_clip(self.project / "output" / "master.mp4", seconds=seconds)

    def _sfx_catalog_and_plan(self):
        lib = self.project / "sfxlib"
        lib.mkdir()
        (lib / "clips").mkdir()
        clip = lib / "clips" / "pop.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", "sine=frequency=880:duration=0.5", str(clip)],
            check=True,
        )
        (lib / "catalog.json").write_text(json.dumps({"clips": [
            {"id": "pop-reveal", "file": "clips/pop.wav", "duration_s": 0.5},
        ]}))
        plan = {
            "master": "output/master.mp4",
            "catalog": str(lib / "catalog.json"),
            "events": [
                {"at_s": 1.0, "sfx_id": "pop-reveal", "gain_db": -6},
                {"at_s": 2.0, "sfx_id": "pop-reveal", "gain_db": -3},
            ],
        }
        plan_path = self.project / "work" / "sfx-plan.json"
        plan_path.write_text(json.dumps(plan))
        return plan_path

    def _music_plan(self):
        track = self.project / "track.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", "sine=frequency=220:duration=3.0", str(track)],
            check=True,
        )
        plan = {"out": "output/master-mixed.mp4", "segments": [
            {"from_s": 0.0, "to_s": 4.0, "track": "track.mp3", "gain_db": -20,
             "fade_in_s": 0.5, "fade_out_s": 0.5},
        ]}
        plan_path = self.project / "work" / "music-plan.json"
        plan_path.write_text(json.dumps(plan))
        return plan_path

    @requires_ffmpeg
    def test_three_stems_match_master_duration_and_format(self):
        self._master(seconds=4.0)
        sfx_plan = self._sfx_catalog_and_plan()
        music_plan = self._music_plan()

        voice_out = make_stems.build_voice(
            self.project / "output" / "master.mp4", self.project / "output" / "stems" / "voice.wav", 4.0)
        sfx_out = make_stems.build_sfx(
            self.project, sfx_plan, self.project / "output" / "stems" / "sfx.wav", 4.0)
        music_out = make_stems.build_music(
            self.project, music_plan, self.project / "output" / "stems" / "music.wav", 4.0)

        for out in (voice_out, sfx_out, music_out):
            rate, channels, duration = _probe_audio(out)
            self.assertEqual(rate, 48000)
            self.assertEqual(channels, 2)
            self.assertAlmostEqual(duration, 4.0, delta=0.02)

    @requires_ffmpeg
    def test_missing_catalog_id_raises(self):
        self._master(seconds=2.0)
        lib = self.project / "sfxlib"
        lib.mkdir()
        (lib / "catalog.json").write_text(json.dumps({"clips": []}))
        plan = {"master": "output/master.mp4", "catalog": str(lib / "catalog.json"),
                "events": [{"at_s": 0.5, "sfx_id": "does-not-exist", "gain_db": 0}]}
        plan_path = self.project / "work" / "sfx-plan.json"
        plan_path.write_text(json.dumps(plan))
        with self.assertRaises(make_stems.StemError) as ctx:
            make_stems.build_sfx(self.project, plan_path,
                                 self.project / "output" / "stems" / "sfx.wav", 2.0)
        self.assertIn("does-not-exist", str(ctx.exception))

    @requires_ffmpeg
    def test_missing_music_track_is_skipped_with_a_warning(self):
        self._master(seconds=2.0)
        plan = {"out": "output/master-mixed.mp4", "segments": [
            {"from_s": 0.0, "to_s": 2.0, "track": "no-such-track.mp3", "gain_db": -20},
        ]}
        plan_path = self.project / "work" / "music-plan.json"
        plan_path.write_text(json.dumps(plan))
        result = make_stems.build_music(self.project, plan_path,
                                        self.project / "output" / "stems" / "music.wav", 2.0)
        self.assertIsNone(result, "no usable segment must produce no music stem")


if __name__ == "__main__":
    unittest.main()
