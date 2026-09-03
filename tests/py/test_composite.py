import tempfile
import unittest
from pathlib import Path

from tests.py.media import duration_of, make_clip, make_silent_clip, requires_ffmpeg
from tools import composite


class CompositeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @requires_ffmpeg
    def test_overlay_preserves_master_audio(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0)
        shot = make_silent_clip(self.dir / "shot.mp4", seconds=1.5)
        out = composite.overlay(master, shot, at_s=1.0, out=self.dir / "out.mp4")
        self.assertIsNotNone(duration_of(out, "a:0"), "the master's audio must survive an overlay")
        self.assertAlmostEqual(duration_of(out, "v:0"), 4.0, delta=0.2)

    @requires_ffmpeg
    def test_cutaway_replaces_video_but_keeps_master_audio(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0)
        shot = make_silent_clip(self.dir / "shot.mp4", seconds=1.0)
        out = composite.cutaway(master, shot, at_s=1.0, out_s=2.0, out=self.dir / "out.mp4")
        self.assertAlmostEqual(duration_of(out, "v:0"), 4.0, delta=0.2)
        self.assertIsNotNone(duration_of(out, "a:0"))

    @requires_ffmpeg
    def test_shot_longer_than_its_span_is_trimmed(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0)
        shot = make_silent_clip(self.dir / "shot.mp4", seconds=3.0)
        out = composite.cutaway(master, shot, at_s=1.0, out_s=2.0, out=self.dir / "out.mp4")
        self.assertAlmostEqual(duration_of(out, "v:0"), 4.0, delta=0.2)

    def test_span_outside_the_master_is_rejected(self):
        with self.assertRaises(composite.CompositeError):
            composite.validate_span(at_s=9.0, out_s=10.0, master_duration_s=4.0)
        with self.assertRaises(composite.CompositeError):
            composite.validate_span(at_s=-1.0, out_s=2.0, master_duration_s=4.0)

    def test_span_at_the_very_start_is_allowed(self):
        composite.validate_span(at_s=0.0, out_s=1.0, master_duration_s=4.0)

    @requires_ffmpeg
    def test_mov_without_alpha_is_rejected_with_a_clear_message(self):
        opaque = make_silent_clip(self.dir / "opaque.mov", seconds=1.0)
        with self.assertRaises(composite.CompositeError) as ctx:
            composite.require_alpha(opaque)
        self.assertIn("alpha", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
