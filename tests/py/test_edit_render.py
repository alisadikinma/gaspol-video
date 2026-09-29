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


FROZEN_ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2"]


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
             "-vf", base + ",fps=30", "-af", "anull", "-t", "2.0", *FROZEN_ENCODE,
             "/proj/work/render/part-001.mp4"],
            ["ffmpeg", "-y", "-v", "error", "-ss", "0.5", "-t", "2.0", "-i", "/proj/clips/b.mp4",
             "-vf", base + ",scale=w='ceil(320*(1.0+(0.08)*t/2.0)/2)*2':"
                    "h='ceil(240*(1.0+(0.08)*t/2.0)/2)*2':eval=frame,crop=320:240,fps=30",
             "-af", "anull", "-t", "2.0", *FROZEN_ENCODE, "/proj/work/render/part-002.mp4"],
            ["ffmpeg", "-y", "-v", "error", "-ss", "0.0", "-t", "1.5", "-i", "/proj/shots/c.mp4",
             "-vf", base + ",fps=30,tpad=stop_mode=clone:stop_duration=0.5",
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
