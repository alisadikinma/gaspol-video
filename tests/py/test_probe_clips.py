import json
import tempfile
import unittest
from pathlib import Path

from tests.py.media import make_clip, make_silent_clip, requires_ffmpeg
from tools import probe_clips


class ProbeClipsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "clips").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    # ---------- the failure this tool exists to catch ----------

    @requires_ffmpeg
    def test_reports_av_mismatch(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=2.0, audio_seconds=1.6)
        manifest = probe_clips.build_manifest(self.project)
        self.assertTrue(
            any("scene-01.mp4" in p for p in manifest["problems"]),
            f"A/V mismatch not reported; problems={manifest['problems']}",
        )

    @requires_ffmpeg
    def test_matched_clip_has_no_problem(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=2.0)
        manifest = probe_clips.build_manifest(self.project)
        self.assertEqual(manifest["problems"], [])
        self.assertAlmostEqual(manifest["clips"][0]["duration_s"], 2.0, delta=0.1)
        self.assertTrue(manifest["clips"][0]["has_audio"])

    # ---------- the input space ----------

    def test_no_clips_folder_is_not_a_crash(self):
        empty = Path(self.tmp.name) / "nothing"
        empty.mkdir()
        manifest = probe_clips.build_manifest(empty)
        self.assertEqual(manifest["clips"], [])
        self.assertTrue(any("no clips" in p.lower() for p in manifest["problems"]))

    def test_empty_clips_folder_reports_it(self):
        manifest = probe_clips.build_manifest(self.project)
        self.assertEqual(manifest["clips"], [])
        self.assertTrue(any("no clips" in p.lower() for p in manifest["problems"]))

    @requires_ffmpeg
    def test_clip_without_audio_stream_is_flagged_not_crashed(self):
        make_silent_clip(self.project / "clips" / "scene-02.mp4", seconds=1.0)
        manifest = probe_clips.build_manifest(self.project)
        self.assertFalse(manifest["clips"][0]["has_audio"])
        self.assertTrue(any("no audio" in p.lower() for p in manifest["problems"]))

    @requires_ffmpeg
    def test_scene_number_parsed_from_filename(self):
        make_clip(self.project / "clips" / "scene-07.mp4", seconds=1.0)
        make_clip(self.project / "clips" / "scene-07-ext1.mp4", seconds=1.0)
        manifest = probe_clips.build_manifest(self.project)
        scenes = sorted(c["scene"] for c in manifest["clips"])
        self.assertEqual(scenes, [7, 7])
        exts = sorted(c["ext"] for c in manifest["clips"])
        self.assertEqual(exts, [0, 1])

    @requires_ffmpeg
    def test_unparseable_filename_is_reported_not_dropped(self):
        make_clip(self.project / "clips" / "final_render_v3.mp4", seconds=1.0)
        manifest = probe_clips.build_manifest(self.project)
        self.assertEqual(len(manifest["clips"]), 1)
        self.assertIsNone(manifest["clips"][0]["scene"])
        self.assertTrue(any("final_render_v3" in p for p in manifest["problems"]))

    @requires_ffmpeg
    def test_writes_manifest_json(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=1.0)
        out = probe_clips.write_manifest(self.project)
        self.assertTrue(out.exists())
        data = json.loads(out.read_text())
        self.assertIn("generated_at", data)
        self.assertEqual(out.name, "clip-manifest.json")

    # ---------- degradation ----------

    def test_missing_ffprobe_degrades_and_does_not_raise(self):
        original = probe_clips.FFPROBE
        try:
            probe_clips.FFPROBE = None
            manifest = probe_clips.build_manifest(self.project)
            self.assertTrue(
                any("ffprobe" in p.lower() for p in manifest["problems"]),
                "a missing ffprobe must be reported, not silently ignored",
            )
        finally:
            probe_clips.FFPROBE = original


if __name__ == "__main__":
    unittest.main()
