import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.py.media import duration_of, extract_frame, make_clip, psnr, requires_ffmpeg
from tools import edit_render
from tools.vidkit import color


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
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25" + TAG,
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
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25" + TAG,
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
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25" + TAG,
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
        make_clip(self.project / "clips" / "raw.mp4", seconds=2.0, size="640x480")
        # The master is now tagged bt709, so the source must carry the same tag or PNG
        # extraction would decode the two with different matrices and PSNR would measure that.
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(self.project / "clips" / "raw.mp4"),
                        "-c", "copy", "-bsf:v", "h264_metadata=matrix_coefficients=1:"
                        "colour_primaries=1:transfer_characteristics=1:video_full_range_flag=0",
                        str(self.project / "clips" / "scene-01.mp4")], check=True)
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


class TransitionValidationTest(unittest.TestCase):
    """transition_in is validated by load_plan; rendering it is a later phase."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "clips").mkdir()
        for n in ("scene-01.mp4", "scene-02.mp4"):
            (self.project / "clips" / n).write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def _load(self, first_extra=None, second_extra=None, check_durations=False):
        first = {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 3.0}
        second = {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": 3.0}
        first.update(first_extra or {})
        second.update(second_extra or {})
        plan = write_plan(self.project, [first, second])
        return edit_render.load_plan(plan, self.project, check_durations=check_durations)

    def test_transition_on_first_segment_is_rejected(self):
        with self.assertRaises(edit_render.PlanError) as ctx:
            self._load(first_extra={"transition_in": {"kind": "dissolve", "dur_s": 0.5}})
        self.assertIn("first segment", str(ctx.exception))


    def _rejects(self, transition, fragment, **kw):
        with self.assertRaises(edit_render.PlanError) as ctx:
            self._load(second_extra={"transition_in": transition}, **kw)
        self.assertIn("segment 2", str(ctx.exception))
        self.assertIn(fragment, str(ctx.exception))

    def test_unknown_transition_kind_is_rejected(self):
        self._rejects({"kind": "wipe", "dur_s": 0.5}, "wipe")

    def test_too_short_dur_is_rejected(self):
        self._rejects({"kind": "dissolve", "dur_s": 0.1}, "0.2")

    def test_too_long_dur_is_rejected(self):
        self._rejects({"kind": "dissolve", "dur_s": 1.5}, "1.0")

    def test_non_numeric_dur_is_rejected(self):
        self._rejects({"kind": "dissolve", "dur_s": "x"}, "dur_s")

    def test_nan_dur_is_rejected(self):
        self._rejects({"kind": "dissolve", "dur_s": float("nan")}, "finite")

    def test_non_object_transition_is_rejected(self):
        self._rejects("dissolve", "object")

    def test_dur_not_shorter_than_this_segment_is_rejected(self):
        with self.assertRaises(edit_render.PlanError) as ctx:
            self._load(second_extra={"out_s": 0.5, "transition_in": {"kind": "dissolve", "dur_s": 0.5}})
        self.assertIn("this segment", str(ctx.exception))

    def test_dur_not_shorter_than_previous_segment_is_rejected(self):
        with self.assertRaises(edit_render.PlanError) as ctx:
            self._load(first_extra={"out_s": 0.5},
                       second_extra={"transition_in": {"kind": "dissolve", "dur_s": 0.5}})
        self.assertIn("previous segment", str(ctx.exception))

    def test_previous_segment_padded_is_rejected(self):
        with self.assertRaises(edit_render.PlanError) as ctx:
            self._load(first_extra={"pad_end_s": 0.5, "pad_mode": "black"},
                       second_extra={"transition_in": {"kind": "dissolve", "dur_s": 0.5}})
        self.assertIn("black pad", str(ctx.exception))

    def test_null_transition_is_treated_as_absent(self):
        self.assertEqual(len(self._load(second_extra={"transition_in": None}).segments), 2)

    @requires_ffmpeg
    def test_insufficient_handle_is_rejected(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=2.0)
        make_clip(self.project / "clips" / "scene-02.mp4", seconds=3.0)
        with self.assertRaises(edit_render.PlanError) as ctx:
            self._load(first_extra={"out_s": 2.0},
                       second_extra={"transition_in": {"kind": "dissolve", "dur_s": 0.5}},
                       check_durations=True)
        self.assertIn("dissolve needs", str(ctx.exception))
        self.assertIn("scene-01.mp4", str(ctx.exception))

    @requires_ffmpeg
    def test_sufficient_handle_is_accepted(self):
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=4.0)
        make_clip(self.project / "clips" / "scene-02.mp4", seconds=3.0)
        loaded = self._load(first_extra={"out_s": 3.0},
                            second_extra={"transition_in": {"kind": "dissolve", "dur_s": 0.5}},
                            check_durations=True)
        self.assertEqual(loaded.segments[1]["transition_in"]["dur_s"], 0.5)


TAG = "," + color.TAG_FILTER
FROZEN_ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 *color.ENCODE_FLAGS, "-c:a", "aac", "-ar", "48000", "-ac", "2"]


class DissolveCommandsTest(unittest.TestCase):
    """build_commands only builds argv lists, so these run without ffmpeg installed."""

    def setUp(self):
        self._ffmpeg = edit_render.FFMPEG
        edit_render.FFMPEG = "ffmpeg"

    def tearDown(self):
        edit_render.FFMPEG = self._ffmpeg

    def _plan(self, segments):
        data = {"fps": 30, "width": 320, "height": 240, "segments": segments}
        return edit_render.Plan(data, "/proj", "/proj/work/edit-plan.json")

    def test_untagged_plan_commands_are_frozen(self):
        plan = self._plan([
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.5, "out_s": 2.5,
             "motion": {"kind": "punch-in", "from": 1.0, "to": 1.08}},
            {"kind": "shot", "src": "shots/c.mp4", "in_s": 0.0, "out_s": 1.5,
             "pad_end_s": 0.5, "pad_mode": "freeze"},
        ])
        cmds, parts, work = edit_render.build_commands(plan)
        base = "scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2"
        self.assertEqual(cmds, [
            ["ffmpeg", "-y", "-v", "error", "-ss", "0.0", "-t", "2.0", "-i", "/proj/clips/a.mp4",
             "-vf", base + ",fps=30" + TAG, "-af", "anull", "-t", "2.0", *FROZEN_ENCODE,
             "/proj/work/render/part-001.mp4"],
            ["ffmpeg", "-y", "-v", "error", "-ss", "0.5", "-t", "2.0", "-i", "/proj/clips/b.mp4",
             "-vf", base + ",scale=w='ceil(320*(1.0+(0.08)*t/2.0)/2)*2':"
                    "h='ceil(240*(1.0+(0.08)*t/2.0)/2)*2':eval=frame,crop=320:240,fps=30" + TAG,
             "-af", "anull", "-t", "2.0", *FROZEN_ENCODE, "/proj/work/render/part-002.mp4"],
            ["ffmpeg", "-y", "-v", "error", "-ss", "0.0", "-t", "1.5", "-i", "/proj/shots/c.mp4",
             "-vf", base + ",fps=30,tpad=stop_mode=clone:stop_duration=0.5" + TAG,
             "-af", "apad=pad_dur=0.5", "-t", "2.0", *FROZEN_ENCODE,
             "/proj/work/render/part-003.mp4"],
        ])
        self.assertEqual([str(p) for p in parts],
                         ["/proj/work/render/part-001.mp4", "/proj/work/render/part-002.mp4",
                          "/proj/work/render/part-003.mp4"])
        self.assertEqual(str(work), "/proj/work/render")

    def test_previous_segment_is_rendered_longer_by_the_dissolve(self):
        plan = self._plan([
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 2.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.5}},
        ])
        cmds = edit_render.build_commands(plan)[0]
        first = cmds[0]
        self.assertEqual(first[first.index("-t") + 1], "2.5")
        self.assertEqual(first[len(first) - first[::-1].index("-t")], "2.5")
        second = cmds[1]
        self.assertEqual(second[second.index("-t") + 1], "2.0")

    def test_motion_zoom_holds_over_the_handle(self):
        plan = self._plan([
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0,
             "motion": {"kind": "punch-in", "from": 1.0, "to": 1.08}},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 2.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.5}},
        ])
        vf = edit_render.build_commands(plan)[0][0]
        vf = vf[vf.index("-vf") + 1]
        self.assertIn("min(t\\,2.0)/2.0", vf)

    def test_group_of_two_merges_with_planned_offset(self):
        plan = self._plan([
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 2.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.5}},
            {"kind": "clip", "src": "clips/c.mp4", "in_s": 0.0, "out_s": 2.0},
        ])
        cmds, parts, _ = edit_render.build_commands(plan)
        self.assertEqual(len(cmds), 4)
        self.assertEqual([p.name for p in parts], ["group-001.mp4", "part-003.mp4"])
        graph = cmds[3][cmds[3].index("-filter_complex") + 1]
        self.assertIn("xfade=transition=fade:duration=0.5:offset=2.0", graph)
        self.assertIn("acrossfade=d=0.5:c1=tri:c2=tri", graph)
        self.assertEqual(cmds[3][-1], "/proj/work/render/group-001.mp4")

    def test_two_consecutive_dissolves_form_one_group_of_three(self):
        plan = self._plan([
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 2.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.5}},
            {"kind": "shot", "src": "shots/c.mp4", "in_s": 0.0, "out_s": 3.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.4}},
        ])
        cmds, parts, _ = edit_render.build_commands(plan)
        self.assertEqual([p.name for p in parts], ["group-001.mp4"])
        # a is 0.5s longer, b is 0.4s longer, c (last) is as planned
        durs = [c[c.index("-t") + 1] for c in cmds[:3]]
        self.assertEqual(durs, ["2.5", "2.4", "3.0"])
        graph = cmds[3][cmds[3].index("-filter_complex") + 1]
        self.assertIn("duration=0.5:offset=2.0", graph)
        self.assertIn("duration=0.4:offset=4.0", graph)

    def test_sheet_marks_the_dissolve_with_its_offset(self):
        plan = self._plan([
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 2.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.5}},
        ])
        sheet = edit_render.format_sheet(plan)
        self.assertIn("~0.5s dissolve at 2.00s", sheet)


class DissolveRenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "clips").mkdir()
        for n in (1, 2, 3):
            make_clip(self.project / "clips" / f"scene-0{n}.mp4", seconds=3.0)

    def tearDown(self):
        self.tmp.cleanup()

    def _segments(self, **second):
        return [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": 2.0, **second},
            {"kind": "clip", "src": "clips/scene-03.mp4", "in_s": 0.0, "out_s": 2.0},
        ]

    @requires_ffmpeg
    def test_dissolve_keeps_the_timeline_and_blends(self):
        dissolve = {"transition_in": {"kind": "dissolve", "dur_s": 0.5}}
        plan = write_plan(self.project, self._segments(**dissolve))
        out = edit_render.render(plan, self.project)
        v, a = duration_of(out, "v:0"), duration_of(out, "a:0")
        print(f"dissolve master: v:0 {v} a:0 {a}")
        self.assertAlmostEqual(v, 6.0, delta=0.04)
        self.assertAlmostEqual(a, 6.0, delta=0.04)
        self.assertTrue(edit_render.check_av_gate(out)[0])

        # Same plan without the dissolve is the reference for the two pure pictures.
        plain = write_plan(self.project, self._segments(), out="output/plain.mp4")
        plain_out = edit_render.render(plain, self.project)
        frame = lambda src, name, at: extract_frame(src, self.project / name, at_s=at)
        blended = frame(out, "blend.png", 2.2)
        pure_incoming = frame(plain_out, "in.png", 2.2)
        pure_outgoing = frame(plain_out, "out.png", 1.9)
        self.assertLess(psnr(blended, pure_incoming), 40.0)
        self.assertLess(psnr(blended, pure_outgoing), 40.0)
        # Well after the fade the picture is the plain incoming one again.
        self.assertGreater(psnr(frame(out, "late.png", 3.0), frame(plain_out, "late-plain.png", 3.0)), 30.0)

    @requires_ffmpeg
    def test_motion_segment_with_handle_renders(self):
        segs = self._segments(transition_in={"kind": "dissolve", "dur_s": 0.5})
        segs[0]["motion"] = {"kind": "punch-in", "from": 1.0, "to": 1.08}
        plan = write_plan(self.project, segs)
        out = edit_render.render(plan, self.project)
        self.assertAlmostEqual(duration_of(out, "v:0"), 6.0, delta=0.04)


if __name__ == "__main__":
    unittest.main()


class ColorTagCommandsTest(unittest.TestCase):
    def setUp(self):
        self._ffmpeg = edit_render.FFMPEG
        edit_render.FFMPEG = "ffmpeg"

    def tearDown(self):
        edit_render.FFMPEG = self._ffmpeg

    def _plan(self, segments):
        data = {"fps": 30, "width": 320, "height": 240, "segments": segments}
        return edit_render.Plan(data, "/proj", "/proj/work/edit-plan.json")

    def _dissolved(self):
        return self._plan([
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 2.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.5}},
        ])

    def test_every_libx264_encode_carries_the_colour_flags(self):
        cmds = edit_render.build_commands(self._dissolved())[0]
        self.assertEqual(len(cmds), 3)  # two segments + one merge
        for cmd in cmds:
            self.assertIn("libx264", cmd)
            i = cmd.index("-colorspace")
            self.assertEqual(cmd[i:i + len(color.ENCODE_FLAGS)], color.ENCODE_FLAGS)

    def test_segment_filter_ends_with_setparams(self):
        cmds = edit_render.build_commands(self._dissolved())[0]
        for cmd in cmds[:2]:
            self.assertTrue(cmd[cmd.index("-vf") + 1].endswith(color.TAG_FILTER))

    def test_merge_graph_tags_the_video_output(self):
        merge = edit_render.build_commands(self._dissolved())[0][2]
        graph = merge[merge.index("-filter_complex") + 1]
        self.assertIn(color.TAG_FILTER, graph)
        self.assertEqual(merge[merge.index("-map") + 1], "[vout]")

    @requires_ffmpeg
    def test_rendered_master_is_tagged_bt709_and_passes_the_gate(self):
        project = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(project, ignore_errors=True))
        (project / "clips").mkdir()
        make_clip(project / "clips" / "a.mp4", seconds=1.5)
        make_clip(project / "clips" / "b.mp4", seconds=1.5)
        plan = write_plan(project, [
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 1.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 1.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.4}},
        ])
        out = edit_render.render(plan, project)
        p = color.probe_color(str(out))
        self.assertEqual((p["color_space"], p["color_primaries"], p["color_transfer"]),
                         ("bt709", "bt709", "bt709"))
        ok, msg = edit_render.check_av_gate(out)
        self.assertTrue(ok, msg)


class Bt601SourceTest(unittest.TestCase):
    def _mean_rgb(self, path, vf):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", vf, "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        return [sum(raw[c::3]) / (len(raw) / 3) for c in range(3)]

    @requires_ffmpeg
    def test_bt601_source_is_converted_not_just_relabelled(self):
        project = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(project, ignore_errors=True))
        (project / "clips").mkdir()
        src = project / "clips" / "sd.mp4"
        tag601 = "setparams=colorspace=smpte170m:color_primaries=smpte170m:color_trc=smpte170m:range=tv"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc=size=320x240:rate=30:duration=1.5", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1.5", "-vf", tag601, "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-colorspace", "smpte170m", "-color_primaries",
                        "smpte170m", "-color_trc", "smpte170m", "-c:a", "aac", "-t", "1.5",
                        str(src)], check=True)
        self.assertEqual(color.probe_color(str(src))["color_space"], "smpte170m")
        plan = write_plan(project, [{"kind": "clip", "src": "clips/sd.mp4", "in_s": 0.0, "out_s": 1.5}])
        out = edit_render.render(plan, project)
        self.assertEqual(color.probe_color(str(out))["color_space"], "bt709")
        want = self._mean_rgb(src, "colorspace=all=bt709:iall=bt601-6-525")
        got = self._mean_rgb(out, "null")
        for w, g in zip(want, got):
            self.assertAlmostEqual(w, g, delta=3.0, msg=f"want {want} got {got}")


class SourceWarningTest(unittest.TestCase):
    def test_hdr_source_warns_once_and_is_left_unconverted(self):
        orig = color.probe_color
        color.probe_color = lambda path: {"color_space": "bt2020nc", "color_primaries": "bt2020",
                                          "color_transfer": "arib-std-b67", "color_range": "tv"}
        self.addCleanup(setattr, color, "probe_color", orig)
        import contextlib, io
        err, warned = io.StringIO(), set()
        with contextlib.redirect_stderr(err):
            a = edit_render._source_color_filter("h.mp4", warned)
            b = edit_render._source_color_filter("h.mp4", warned)
        self.assertEqual((a, b), ("", ""))
        self.assertEqual(err.getvalue().count("left unconverted"), 1)
        self.assertEqual(err.getvalue().count("\n"), 1)


def _sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class StageCacheRenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "clips").mkdir()
        for n in (1, 2):
            make_clip(self.project / "clips" / f"scene-0{n}.mp4", seconds=2.5)

    def tearDown(self):
        self.tmp.cleanup()

    def _segments(self, out2=1.5):
        return [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": out2},
        ]

    def _render(self, plan, **kw):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            out = edit_render.render(plan, self.project, **kw)
        text = buf.getvalue()
        encodes = [ln for ln in text.splitlines() if ln.startswith("+ ") and "libx264" in ln]
        return out, text, len(encodes)

    @requires_ffmpeg
    def test_second_run_skips_everything_and_master_is_identical(self):
        plan = write_plan(self.project, self._segments())
        out, text, n = self._render(plan)
        self.assertEqual(n, 2)
        self.assertIn("skipped 0 of 2 segments (cached)", text)
        first = _sha(out)

        out2, text2, n2 = self._render(plan)
        self.assertEqual(n2, 0)
        self.assertIn("skipped 2 of 2 segments (cached)", text2)
        self.assertIn("-f concat", text2, "the concat always runs")
        self.assertIn("A/V duration gate passed", text2, "the gate always runs")
        self.assertEqual(_sha(out2), first)

        out3, _, n3 = self._render(plan, cache=False)
        self.assertEqual(n3, 2)
        self.assertEqual(_sha(out3), first, "cached master must equal a full render")

    @requires_ffmpeg
    def test_changing_one_out_s_re_encodes_only_that_segment(self):
        self._render(write_plan(self.project, self._segments()))
        plan = write_plan(self.project, self._segments(out2=1.0))
        out, text, n = self._render(plan)
        self.assertEqual(n, 1)
        self.assertIn("skipped 1 of 2 segments (cached)", text)
        self.assertAlmostEqual(duration_of(out, "v:0"), 3.0, delta=0.2)

    @requires_ffmpeg
    def test_no_cache_re_encodes_everything(self):
        plan = write_plan(self.project, self._segments())
        self._render(plan)
        _, text, n = self._render(plan, cache=False)
        self.assertEqual(n, 2)
        self.assertNotIn("skipped", text, "no cache is consulted, so nothing is reported skipped")
        self.assertEqual(self._render(plan)[2], 0, "--no-cache leaves the cached parts alone")

    @requires_ffmpeg
    def test_changed_encode_command_invalidates_every_part(self):
        plan = write_plan(self.project, self._segments())
        self._render(plan)
        orig = color.ENCODE_FLAGS
        color.ENCODE_FLAGS = orig + ["-metadata", "title=cache-test"]
        self.addCleanup(setattr, color, "ENCODE_FLAGS", orig)
        _, text, n = self._render(plan)
        self.assertEqual(n, 2)
        self.assertIn("skipped 0 of 2 segments (cached)", text)

    @requires_ffmpeg
    def test_older_renderer_version_is_stale(self):
        plan = write_plan(self.project, self._segments())
        self._render(plan)
        orig = edit_render.RENDERER_VERSION
        edit_render.RENDERER_VERSION = "2"
        self.addCleanup(setattr, edit_render, "RENDERER_VERSION", orig)
        self.assertEqual(self._render(plan)[2], 2)

    @requires_ffmpeg
    def test_source_rewritten_with_same_bytes_stays_fresh(self):
        plan = write_plan(self.project, self._segments())
        self._render(plan)
        src = self.project / "clips" / "scene-01.mp4"
        src.write_bytes(src.read_bytes())
        self.assertEqual(self._render(plan)[2], 0)

    @requires_ffmpeg
    def test_changed_source_bytes_re_encode_that_segment(self):
        plan = write_plan(self.project, self._segments())
        self._render(plan)
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=2.6)
        self.assertEqual(self._render(plan)[2], 1)

    @requires_ffmpeg
    def test_deleted_part_is_re_encoded(self):
        plan = write_plan(self.project, self._segments())
        self._render(plan)
        parts = sorted((self.project / ".tmp" / "edit-parts").glob("part-*.mp4"))
        self.assertEqual(len(parts), 2)
        parts[0].unlink()
        self.assertEqual(self._render(plan)[2], 1)

    @requires_ffmpeg
    def test_identical_segments_get_distinct_stages(self):
        seg = {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 1.0}
        plan = write_plan(self.project, [dict(seg), dict(seg)])
        self._render(plan)
        data = json.loads((self.project / ".tmp" / "edit-parts" / "stages.json").read_text())
        self.assertEqual(sorted(data), ["seg-1", "seg-2"])
        self.assertEqual(self._render(plan)[2], 0)

    @requires_ffmpeg
    def test_dissolve_group_merge_is_cached_too(self):
        segs = self._segments(out2=1.5)
        segs[1]["transition_in"] = {"kind": "dissolve", "dur_s": 0.4}
        plan = write_plan(self.project, segs)
        out, _, n = self._render(plan)
        self.assertEqual(n, 3)
        first = _sha(out)
        out2, text, n2 = self._render(plan)
        self.assertEqual(n2, 0)
        self.assertIn("skipped 2 of 2 segments (cached)", text)
        self.assertEqual(_sha(out2), first)

    @requires_ffmpeg
    def test_unwritable_parts_dir_falls_back_to_a_full_render(self):
        (self.project / ".tmp").write_text("a file where the cache dir should be")
        plan = write_plan(self.project, self._segments())
        out, text, n = self._render(plan)
        self.assertEqual(n, 2)
        self.assertIn("caching disabled", text)
        self.assertTrue(Path(out).is_file())
        self.assertEqual(self._render(plan)[2], 2)

    @requires_ffmpeg
    def test_unwritable_cache_file_warns_and_still_renders(self):
        parts = self.project / ".tmp" / "edit-parts"
        (parts / "stages.json").mkdir(parents=True)
        plan = write_plan(self.project, self._segments())
        out, text, n = self._render(plan)
        self.assertEqual(n, 2)
        self.assertIn("caching disabled", text)
        self.assertTrue(Path(out).is_file())

    def test_zero_segments_still_rejected_and_leaves_no_cache(self):
        plan = write_plan(self.project, [])
        with self.assertRaises(edit_render.PlanError):
            edit_render.render(plan, self.project)
        self.assertFalse((self.project / ".tmp").exists())

    def test_cli_has_cache_and_no_cache_flags(self):
        import contextlib, io
        from unittest import mock
        seen = []
        with mock.patch.object(edit_render, "render",
                               side_effect=lambda *a, **k: seen.append(k) or "x"):
            edit_render.main([str(self.project)])
            edit_render.main([str(self.project), "--no-cache"])
            edit_render.main([str(self.project), "--cache"])
        self.assertEqual([k["cache"] for k in seen], [True, False, True])

    @requires_ffmpeg
    def test_print_lists_cached_or_rendered_per_stage(self):
        import contextlib, io
        plan = write_plan(self.project, self._segments())

        def shown():
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                edit_render.main([str(self.project), "--print"])
            return buf.getvalue()

        before = shown()
        self.assertIn("seg-1: rendered", before)
        self.assertIn("seg-2: rendered", before)
        self._render(plan)
        after = shown()
        self.assertIn("seg-1: cached", after)
        self.assertIn("seg-2: cached", after)
        write_plan(self.project, self._segments(out2=1.0))
        self.assertIn("seg-1: cached", shown())
        self.assertIn("seg-2: rendered", shown())


class EncoderSelectionTest(unittest.TestCase):
    """GASPOL_VIDEO_ENCODER wiring. build_commands only builds argv lists."""
    HW = {"libx264", "h264_videotoolbox"}

    def setUp(self):
        self._ffmpeg = edit_render.FFMPEG
        edit_render.FFMPEG = "ffmpeg"
        self.addCleanup(setattr, edit_render, "FFMPEG", self._ffmpeg)

    def _plan(self):
        data = {"fps": 30, "width": 320, "height": 240, "segments": [
            {"kind": "clip", "src": "clips/a.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/b.mp4", "in_s": 0.0, "out_s": 2.0,
             "transition_in": {"kind": "dissolve", "dur_s": 0.5}},
        ]}
        return edit_render.Plan(data, "/proj", "/proj/work/edit-plan.json")

    def _build(self, env):
        from unittest import mock
        import os
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GASPOL_VIDEO_ENCODER", None)
            if env is not None:
                os.environ["GASPOL_VIDEO_ENCODER"] = env
            with mock.patch.object(edit_render, "_available_encoders", return_value=self.HW):
                return edit_render.build_commands(self._plan())[0]

    def test_env_unset_is_byte_identical_to_the_frozen_recipe(self):
        for cmd in self._build(None):
            i = cmd.index("-c:v")
            self.assertEqual(cmd[i:i + len(FROZEN_ENCODE)], FROZEN_ENCODE)

    def test_explicit_libx264_equals_unset(self):
        self.assertEqual(self._build("libx264"), self._build(None))

    def test_hardware_choice_changes_every_encode_and_keeps_colour_flags(self):
        for cmd in self._build("h264_videotoolbox"):
            self.assertIn("h264_videotoolbox", cmd)
            self.assertNotIn("libx264", cmd)
            self.assertNotIn("-crf", cmd)
            for flag in color.ENCODE_FLAGS:
                self.assertIn(flag, cmd)

    def test_auto_with_hardware_available_uses_it(self):
        self.assertTrue(all("h264_videotoolbox" in c for c in self._build("auto")))

    def test_unknown_value_is_a_plan_error(self):
        with self.assertRaises(edit_render.PlanError):
            self._build("bogus")


class EncoderCacheAndFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "clips").mkdir()
        make_clip(self.project / "clips" / "scene-01.mp4", seconds=2.5)
        make_clip(self.project / "clips" / "scene-02.mp4", seconds=2.5)
        self.plan = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": 1.5},
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def _quiet_render(self, **kw):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            edit_render.render(self.plan, self.project, **kw)
        return buf.getvalue()

    @requires_ffmpeg
    def test_encoder_change_invalidates_the_cache(self):
        from unittest import mock
        import os
        self._quiet_render()
        loaded = edit_render.load_plan(self.plan, self.project)
        self.assertEqual([s for _, s in edit_render.stage_status(loaded)], ["cached", "cached"])
        env = {"GASPOL_VIDEO_ENCODER": "h264_videotoolbox"}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(edit_render, "_available_encoders",
                                  return_value={"libx264", "h264_videotoolbox"}):
            status = edit_render.stage_status(loaded)
        self.assertEqual([s for _, s in status], ["rendered", "rendered"])

    @requires_ffmpeg
    def test_failing_hardware_encode_falls_back_and_still_renders(self):
        from unittest import mock
        import os
        real = edit_render._run_encode

        def fake(cmd):
            if "h264_videotoolbox" in cmd:
                raise edit_render.ff.FFError("videotoolbox exploded")
            return real(cmd)
        with mock.patch.dict(os.environ, {"GASPOL_VIDEO_ENCODER": "h264_videotoolbox"}), \
                mock.patch.object(edit_render, "_available_encoders",
                                  return_value={"libx264", "h264_videotoolbox"}), \
                mock.patch.object(edit_render, "_run_encode", side_effect=fake):
            text = self._quiet_render(cache=False)
        self.assertIn("encoder h264_videotoolbox failed, retried with libx264", text)
        self.assertTrue((self.project / "output" / "master.mp4").exists())
        self.assertIn("A/V duration gate passed", text)

    def test_missing_ffmpeg_listing_means_libx264_only(self):
        from unittest import mock
        with mock.patch.object(edit_render.subprocess, "run", side_effect=OSError("no ffmpeg")):
            self.assertEqual(edit_render._available_encoders(), set())
