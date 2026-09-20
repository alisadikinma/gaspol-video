import json
import tempfile
import unittest
from pathlib import Path

from tests.py.media import duration_of, extract_frame, make_clip, psnr, requires_ffmpeg
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

    # ---------- motion ----------

    def _vf_of(self, cmd):
        return cmd[cmd.index("-vf") + 1]

    def test_punch_in_adds_crop_expression(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "punch-in", "from": 1.0, "to": 1.08}},
        ])
        loaded = edit_render.load_plan(plan, self.project, check_durations=False)
        cmds, _, _ = edit_render.build_commands(loaded)
        vf = self._vf_of(cmds[0])
        self.assertIn("scale=w='ceil(320*(1.0+(0.08)*t/2.0)/2)*2'", vf)
        self.assertIn("eval=frame", vf)
        self.assertIn("crop=320:240", vf)

    def test_no_motion_field_renders_byte_identical_filter(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0},
        ], width=1920, height=1080, fps=25)
        loaded = edit_render.load_plan(plan, self.project, check_durations=False)
        cmds, _, _ = edit_render.build_commands(loaded)
        vf = self._vf_of(cmds[0])
        self.assertEqual(
            vf,
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25",
        )

    def test_unknown_motion_kind_is_rejected(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "zoom-out"}},
        ])
        with self.assertRaises(edit_render.PlanError) as ctx:
            edit_render.load_plan(plan, self.project, check_durations=False)
        msg = str(ctx.exception)
        self.assertIn("segment 1", msg)
        self.assertIn("punch-in", msg)
        self.assertIn("punch-out", msg)
        self.assertIn("none", msg)

    def test_motion_over_max_zoom_is_rejected(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "punch-in", "from": 1.0, "to": 1.30}},
        ])
        with self.assertRaises(edit_render.PlanError) as ctx:
            edit_render.load_plan(plan, self.project, check_durations=False)
        self.assertIn("1.12", str(ctx.exception))

    def test_punch_in_direction_disagreeing_with_kind_is_rejected(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "punch-in", "from": 1.08, "to": 1.0}},
        ])
        with self.assertRaises(edit_render.PlanError):
            edit_render.load_plan(plan, self.project, check_durations=False)

    def test_punch_out_direction_descends(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "punch-out", "from": 1.08, "to": 1.0}},
        ])
        loaded = edit_render.load_plan(plan, self.project, check_durations=False)
        cmds, _, _ = edit_render.build_commands(loaded)
        vf = self._vf_of(cmds[0])
        self.assertIn("scale=w='ceil(320*(1.08+(-0.08)*t/2.0)/2)*2'", vf)

    def test_motion_with_pad_end_keeps_both_in_order(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "pad_end_s": 0.5, "motion": {"kind": "punch-in", "from": 1.0, "to": 1.08}},
        ])
        loaded = edit_render.load_plan(plan, self.project, check_durations=False)
        cmds, _, _ = edit_render.build_commands(loaded)
        vf = self._vf_of(cmds[0])
        self.assertIn("crop=", vf)
        self.assertIn("tpad=", vf)
        self.assertLess(vf.index("crop="), vf.index("tpad="))

    def test_motion_null_is_treated_as_absent(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": None},
        ], width=1920, height=1080, fps=25)
        loaded = edit_render.load_plan(plan, self.project, check_durations=False)
        cmds, _, _ = edit_render.build_commands(loaded)
        vf = self._vf_of(cmds[0])
        self.assertEqual(
            vf,
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25",
        )

    def test_motion_kind_none_renders_like_no_motion(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "none"}},
        ], width=1920, height=1080, fps=25)
        loaded = edit_render.load_plan(plan, self.project, check_durations=False)
        cmds, _, _ = edit_render.build_commands(loaded)
        vf = self._vf_of(cmds[0])
        self.assertEqual(
            vf,
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25",
        )

    def test_non_finite_motion_value_is_rejected(self):
        (self.project / "clips" / "scene-01.mp4").write_bytes(b"x")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "punch-in", "from": 1.0, "to": float("nan")}},
        ])
        with self.assertRaises(edit_render.PlanError) as ctx:
            edit_render.load_plan(plan, self.project, check_durations=False)
        self.assertIn("segment 1", str(ctx.exception))

    @requires_ffmpeg
    def test_motion_actually_zooms_the_picture(self):
        # A string match is not proof the filter runs. This renders it for real: the
        # first frame (zoom 1.00) must be nearly identical to the source, the last
        # frame (zoom 1.08) must genuinely differ — the picture actually moved.
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=2.0, size="640x480")
        plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "punch-in", "from": 1.0, "to": 1.08}},
        ], width=640, height=480, fps=25)
        out = edit_render.render(plan, self.project)

        work = self.project / "work"
        src_first = extract_frame(self.project / "clips" / "scene-01.mp4", work / "src-first.png", at_s=0)
        src_last = extract_frame(self.project / "clips" / "scene-01.mp4", work / "src-last.png", from_end_s=0.08)
        out_first = extract_frame(out, work / "out-first.png", at_s=0)
        out_last = extract_frame(out, work / "out-last.png", from_end_s=0.08)

        first_psnr = psnr(src_first, out_first)
        last_psnr = psnr(src_last, out_last)
        self.assertGreater(first_psnr, 30,
                            f"first frame should barely change at zoom 1.00, got PSNR {first_psnr}")
        self.assertLess(last_psnr, 20,
                         f"last frame should differ once zoomed to 1.08, got PSNR {last_psnr}")


if __name__ == "__main__":
    unittest.main()
