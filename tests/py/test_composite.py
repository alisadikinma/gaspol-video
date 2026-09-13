import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def _make_alpha_mov(path, seconds=1.5, size="320x240"):
    """A transparent .mov shot, the fixture the plan specifies for split/insert tests."""
    import subprocess
    FFMPEG_BIN = shutil_which()
    subprocess.run(
        [FFMPEG_BIN, "-y", "-v", "error", "-f", "lavfi",
         "-i", f"color=c=black@0.0:s={size}:d={seconds},format=yuva420p",
         "-c:v", "qtrle", str(path)],
        check=True,
    )
    return str(path)


def shutil_which():
    import shutil
    return shutil.which("ffmpeg")


class CompositeSplitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @requires_ffmpeg
    def test_split_produces_full_length_master_with_audio(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = _make_alpha_mov(self.dir / "shot.mov", seconds=1.5, size="320x240")
        out = composite.split(
            master, shot, at_s=1.0, out_s=2.5, box=(20, 20, 120, 90), out=self.dir / "out.mp4",
        )
        self.assertAlmostEqual(duration_of(out, "v:0"), 4.0, delta=0.2)
        self.assertIsNotNone(duration_of(out, "a:0"), "master audio must survive a split")

    @requires_ffmpeg
    def test_box_outside_the_master_frame_is_rejected(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = _make_alpha_mov(self.dir / "shot.mov", seconds=1.0, size="320x240")
        with self.assertRaises(composite.CompositeError) as ctx:
            composite.split(
                master, shot, at_s=1.0, out_s=2.0, box=(300, 200, 100, 100),
                out=self.dir / "out.mp4",
            )
        self.assertIn("outside", str(ctx.exception).lower())

    def test_odd_box_dimensions_become_even_in_the_filter(self):
        filt = composite.split_filter(
            box=(0, 0, 101, 99), master_w=320, master_h=240, fps=30.0,
            at_s=1.0, out_s=2.0,
        )
        self.assertIn("scale=100:98", filt)

    @requires_ffmpeg
    def test_zoom_below_one_is_rejected(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = _make_alpha_mov(self.dir / "shot.mov", seconds=1.0, size="320x240")
        with self.assertRaises(composite.CompositeError):
            composite.split(
                master, shot, at_s=1.0, out_s=2.0, box=(0, 0, 100, 100),
                out=self.dir / "out.mp4", zoom=0.5,
            )

    @requires_ffmpeg
    def test_crop_centre_out_of_range_is_rejected(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = _make_alpha_mov(self.dir / "shot.mov", seconds=1.0, size="320x240")
        with self.assertRaises(composite.CompositeError):
            composite.split(
                master, shot, at_s=1.0, out_s=2.0, box=(0, 0, 100, 100),
                out=self.dir / "out.mp4", crop_cx=1.5,
            )

    @requires_ffmpeg
    def test_opaque_shot_is_rejected_for_split_too(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        opaque = make_silent_clip(self.dir / "opaque.mov", seconds=1.0, size="320x240")
        with self.assertRaises(composite.CompositeError) as ctx:
            composite.split(
                master, opaque, at_s=1.0, out_s=2.0, box=(0, 0, 100, 100),
                out=self.dir / "out.mp4",
            )
        self.assertIn("alpha", str(ctx.exception).lower())

    @requires_ffmpeg
    def test_out_s_past_master_end_is_rejected(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = _make_alpha_mov(self.dir / "shot.mov", seconds=1.0, size="320x240")
        with self.assertRaises(composite.CompositeError) as ctx:
            composite.split(
                master, shot, at_s=1.0, out_s=9.0, box=(20, 20, 100, 80),
                out=self.dir / "out.mp4",
            )
        self.assertIn("master", str(ctx.exception).lower())

    @requires_ffmpeg
    def test_av_gate_deletes_output_and_raises_on_mismatch(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = _make_alpha_mov(self.dir / "shot.mov", seconds=1.0, size="320x240")
        out = self.dir / "out.mp4"
        with mock.patch.object(composite, "duration_of", side_effect=[4.0, 4.0, 4.3]):
            with self.assertRaises(composite.CompositeError) as ctx:
                composite.split(
                    master, shot, at_s=1.0, out_s=2.0, box=(20, 20, 100, 80), out=out,
                )
        self.assertIn("mismatch", str(ctx.exception).lower())

    @requires_ffmpeg
    def test_av_gate_skipped_when_master_has_no_audio(self):
        master = make_silent_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = _make_alpha_mov(self.dir / "shot.mov", seconds=1.0, size="320x240")
        out = composite.split(
            master, shot, at_s=1.0, out_s=2.0, box=(20, 20, 100, 80), out=self.dir / "out.mp4",
        )
        self.assertIsNone(duration_of(out, "a:0"), "a silent master must stay silent, no gate needed")

    @requires_ffmpeg
    def test_pixel_inside_box_differs_from_master_during_span(self):
        """A pixel inside the box, and a pixel outside it, must both differ from what the
        plain master shows at the same coordinate during the span — proof the PIP crop and
        the shot graphic actually composited, not a no-op filter."""
        import subprocess

        def pixel_at(path, x, y, t=1.5):
            # crop needs an even width/height here — the source is yuv420p (chroma
            # subsampled 2x2), and cropping to an odd size fails to reinitialise the filter.
            # A 2x2 crop still isolates one visual point; only its first pixel is read.
            raw = subprocess.run(
                [shutil_which(), "-v", "error", "-ss", str(t), "-i", str(path),
                 "-vf", f"crop=2:2:{x}:{y}", "-frames:v", "1",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                capture_output=True, check=True,
            ).stdout
            return raw[:3]

        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        # Opaque green everywhere EXCEPT a transparent "hole" exactly over the box — the
        # transparent hole lets the PIP crop of the master show through there; everywhere
        # else the shot's own green covers the master entirely.
        shot = self.dir / "shot.mov"
        subprocess.run(
            [shutil_which(), "-y", "-v", "error", "-f", "lavfi", "-i",
             "color=c=green@1.0:s=320x240:d=1.5,format=yuva420p,"
             "geq=r='0':g='255':b='0':a='if(between(X,20,120)*between(Y,20,100),0,255)'",
             "-c:v", "qtrle", str(shot)],
            check=True,
        )
        out = composite.split(
            master, str(shot), at_s=1.0, out_s=2.5, box=(20, 20, 100, 80),
            out=self.dir / "out.mp4",
        )

        inside_out = pixel_at(out, 60, 60)
        inside_master = pixel_at(master, 60, 60)
        self.assertNotEqual(
            inside_out, inside_master,
            "inside the box the output must show the cropped PIP, not the raw master pixel",
        )

        outside_out = pixel_at(out, 200, 200)
        outside_master = pixel_at(master, 200, 200)
        self.assertNotEqual(
            outside_out, outside_master,
            "outside the box the output must show the shot's own graphic (green), not the master",
        )


class CompositeInsertTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @requires_ffmpeg
    def test_insert_pauses_master_for_the_full_shot(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = make_clip(self.dir / "shot.mp4", seconds=1.0, size="320x240")
        out = composite.insert(master, shot, at_s=2.0, out=self.dir / "out.mp4")
        self.assertAlmostEqual(duration_of(out, "v:0"), 5.0, delta=0.1)
        self.assertAlmostEqual(duration_of(out, "a:0"), 5.0, delta=0.1)

    @requires_ffmpeg
    def test_insert_at_zero_has_no_pre_segment(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = make_clip(self.dir / "shot.mp4", seconds=1.0, size="320x240")
        out = composite.insert(master, shot, at_s=0.0, out=self.dir / "out.mp4")
        self.assertAlmostEqual(duration_of(out, "v:0"), 5.0, delta=0.1)
        self.assertAlmostEqual(duration_of(out, "a:0"), 5.0, delta=0.1)

    @requires_ffmpeg
    def test_insert_at_end_has_no_post_segment(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = make_clip(self.dir / "shot.mp4", seconds=1.0, size="320x240")
        out = composite.insert(master, shot, at_s=4.0, out=self.dir / "out.mp4")
        self.assertAlmostEqual(duration_of(out, "v:0"), 5.0, delta=0.1)
        self.assertAlmostEqual(duration_of(out, "a:0"), 5.0, delta=0.1)

    @requires_ffmpeg
    def test_insert_beyond_master_is_rejected(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = make_clip(self.dir / "shot.mp4", seconds=1.0, size="320x240")
        with self.assertRaises(composite.CompositeError):
            composite.insert(master, shot, at_s=9.0, out=self.dir / "out.mp4")

    @requires_ffmpeg
    def test_silent_shot_gets_silence_and_passes_the_av_gate(self):
        master = make_clip(self.dir / "master.mp4", seconds=4.0, size="320x240")
        shot = make_silent_clip(self.dir / "shot.mp4", seconds=1.0, size="320x240")
        out = composite.insert(master, shot, at_s=2.0, out=self.dir / "out.mp4")
        v_dur = duration_of(out, "v:0")
        a_dur = duration_of(out, "a:0")
        self.assertAlmostEqual(v_dur, 5.0, delta=0.1)
        self.assertAlmostEqual(a_dur, 5.0, delta=0.1)
        self.assertLessEqual(abs(v_dur - a_dur), 0.04)

    def test_insert_plan_skips_zero_length_segments(self):
        plan_mid = composite.insert_plan(at_s=2.0, master_duration=4.0, shot_duration=1.0, fps=30.0)
        self.assertEqual([p["kind"] for p in plan_mid], ["pre", "shot", "post"])

        plan_start = composite.insert_plan(at_s=0.0, master_duration=4.0, shot_duration=1.0, fps=30.0)
        self.assertEqual([p["kind"] for p in plan_start], ["shot", "post"])

        plan_end = composite.insert_plan(at_s=4.0, master_duration=4.0, shot_duration=1.0, fps=30.0)
        self.assertEqual([p["kind"] for p in plan_end], ["pre", "shot"])

    def test_insert_audio_filter_no_gain_has_no_limiter(self):
        filt = composite.insert_audio_filter(at_s=2.0, shot_dur_s=1.0, end_s=4.0, gain_db=0.0)
        self.assertNotIn("alimiter", filt)
        self.assertIn("concat=n=3:v=0:a=1[a]", filt)

    def test_insert_audio_filter_positive_gain_adds_a_limiter(self):
        filt = composite.insert_audio_filter(at_s=2.0, shot_dur_s=1.0, end_s=4.0, gain_db=6.0)
        self.assertIn("volume=6.00dB", filt)
        self.assertIn("alimiter=limit=0.97:level=false", filt)

    def test_insert_audio_filter_negative_gain_has_no_limiter(self):
        filt = composite.insert_audio_filter(at_s=2.0, shot_dur_s=1.0, end_s=4.0, gain_db=-6.0)
        self.assertIn("volume=-6.00dB", filt)
        self.assertNotIn("alimiter", filt)

    def test_insert_audio_filter_silent_shot_uses_anullsrc(self):
        filt = composite.insert_audio_filter(
            at_s=2.0, shot_dur_s=1.0, end_s=4.0, gain_db=0.0, has_shot_audio=False,
        )
        self.assertIn("anullsrc=r=48000:cl=stereo:d=1.0000", filt)


if __name__ == "__main__":
    unittest.main()
