import json
import tempfile
import unittest
from pathlib import Path

from tests.py.media import duration_of, make_clip, requires_ffmpeg
from tools import edit_render


def write_plan(project, segments, **extra):
    plan = {"fps": 30, "width": 320, "height": 240, "out": "output/master.mp4",
            "segments": segments}
    plan.update(extra)
    path = project / "work" / "edit-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2))
    return path


class EditRenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "clips").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    # ---------- the gate this tool exists for ----------

    @requires_ffmpeg
    def test_av_duration_gate(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=2.0)
        make_clip(self.project / "clips" / "scene-02.mp4", seconds=2.0)
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": 1.5},
        ])
        out = edit_render.render(plan, self.project)
        v, a = duration_of(out, "v:0"), duration_of(out, "a:0")
        self.assertIsNotNone(a, "the master must carry audio")
        self.assertLessEqual(abs(v - a), edit_render.AV_TOLERANCE_S,
                             f"A/V gate should have rejected this: v={v} a={a}")

    @requires_ffmpeg
    def test_one_segment_renders(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=1.5)
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 1.5},
        ])
        out = edit_render.render(plan, self.project)
        self.assertTrue(Path(out).exists())
        self.assertAlmostEqual(duration_of(out, "v:0"), 1.5, delta=0.2)

    # ---------- rejected input ----------

    def test_zero_segments_is_rejected(self):
        plan = write_plan(self.project, [])
        with self.assertRaises(edit_render.PlanError):
            edit_render.load_plan(plan, self.project)

    def test_malformed_json_names_the_problem(self):
        path = self.project / "work" / "edit-plan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"fps": 30, "segments": [}')
        with self.assertRaises(edit_render.PlanError) as ctx:
            edit_render.load_plan(path, self.project)
        self.assertIn("edit-plan.json", str(ctx.exception))

    def test_unknown_segment_kind_is_rejected(self):
        plan = write_plan(self.project, [
            {"kind": "titlecard", "src": "clips/scene-01.mp4", "in_s": 0, "out_s": 1},
        ])
        with self.assertRaises(edit_render.PlanError) as ctx:
            edit_render.load_plan(plan, self.project)
        self.assertIn("titlecard", str(ctx.exception))

    def test_missing_source_file_is_rejected_before_rendering(self):
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-99.mp4", "in_s": 0.0, "out_s": 2.0},
        ])
        with self.assertRaises(edit_render.PlanError) as ctx:
            edit_render.load_plan(plan, self.project)
        self.assertIn("scene-99", str(ctx.exception))

    @requires_ffmpeg
    def test_trim_beyond_clip_length_is_rejected(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=1.0)
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 5.0},
        ])
        with self.assertRaises(edit_render.PlanError) as ctx:
            edit_render.load_plan(plan, self.project)
        self.assertIn("longer than", str(ctx.exception))

    def test_negative_and_inverted_range_rejected(self):
        for seg in ({"in_s": -1.0, "out_s": 2.0}, {"in_s": 2.0, "out_s": 1.0}):
            plan = write_plan(self.project, [
                dict(kind="clip", src="clips/scene-01.mp4", **seg),
            ])
            with self.assertRaises(edit_render.PlanError):
                edit_render.load_plan(plan, self.project)

    # ---------- warnings, not failures ----------

    @requires_ffmpeg
    def test_long_pad_warns_but_still_renders(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=1.0)
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 1.0,
             "pad_end_s": 1.6, "pad_mode": "freeze"},
        ])
        loaded = edit_render.load_plan(plan, self.project)
        self.assertTrue(any("pad" in w.lower() for w in loaded.warnings),
                        f"a pad over {edit_render.PAD_WARN_S}s must warn; warnings={loaded.warnings}")

    # ---------- degradation ----------

    def test_missing_ffmpeg_prints_command_and_does_not_raise(self):
        original = edit_render.FFMPEG
        try:
            edit_render.FFMPEG = None
            plan = write_plan(self.project, [
                {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 1.0},
            ])
            (self.project / "clips" / "scene-01.mp4").write_bytes(b"not really a clip")
            result = edit_render.render(plan, self.project, allow_degraded=True)
            self.assertIsNone(result)
        finally:
            edit_render.FFMPEG = original

    def test_sheet_lists_every_segment(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 1.0},
        ])
        loaded = edit_render.load_plan(plan, self.project, check_durations=False)
        sheet = edit_render.format_sheet(loaded)
        self.assertIn("scene-01.mp4", sheet)
        self.assertIn("1.00", sheet)


if __name__ == "__main__":
    unittest.main()
