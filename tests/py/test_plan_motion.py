import json
import tempfile
import unittest
from pathlib import Path

import tools.plan_motion as plan_motion
from tools import edit_render


def write_plan(project, segments, **extra):
    plan = {"fps": 30, "width": 1920, "height": 1080, "out": "output/master.mp4",
            "segments": segments}
    plan.update(extra)
    path = project / "work" / "edit-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2))
    return path


class PlanMotionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "clips").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _touch(self, name):
        (self.project / "clips" / name).write_bytes(b"x")

    def test_long_segment_splits_into_alternating_beats(self):
        self._touch("scene-12.mp4")
        plan_path = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-12.mp4", "in_s": 0.0, "out_s": 8.4},
        ])
        data = plan_motion.load_plan_data(plan_path)
        report = plan_motion.plan_motion(data)

        segments = data["segments"]
        self.assertEqual(len(segments), 2)
        first, second = segments
        self.assertEqual(first["motion"], {"kind": "punch-in", "from": 1.0, "to": 1.08})
        self.assertEqual(second["motion"], {"kind": "punch-out", "from": 1.08, "to": 1.0})
        self.assertAlmostEqual(first["out_s"] - first["in_s"], 4.2)
        self.assertAlmostEqual(second["out_s"] - second["in_s"], 4.2)
        self.assertAlmostEqual(first["in_s"], 0.0)
        self.assertAlmostEqual(first["out_s"], 4.2)
        self.assertAlmostEqual(second["in_s"], 4.2)
        self.assertAlmostEqual(second["out_s"], 8.4)
        self.assertEqual(report["changed"], ["S12 8.4s -> in 0.0-4.2, out 4.2-8.4"])
        self.assertEqual(report["skipped"], [])

    # ---------- edge cases ----------

    def test_five_second_segment_stays_single_with_slow_punch_in(self):
        self._touch("scene-01.mp4")
        plan_path = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 5.0},
        ])
        data = plan_motion.load_plan_data(plan_path)
        report = plan_motion.plan_motion(data)

        self.assertEqual(len(data["segments"]), 1)
        self.assertEqual(data["segments"][0]["motion"],
                          {"kind": "punch-in", "from": 1.0, "to": 1.04})
        self.assertEqual(report["changed"], ["S1 5.0s -> in 0.0-5.0"])

    def test_five_point_zero_one_second_segment_becomes_two_beats(self):
        self._touch("scene-02.mp4")
        plan_path = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": 5.01},
        ])
        data = plan_motion.load_plan_data(plan_path)
        plan_motion.plan_motion(data)

        self.assertEqual(len(data["segments"]), 2)

    def test_thirty_second_segment_becomes_six_beats_alternating(self):
        self._touch("scene-03.mp4")
        plan_path = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-03.mp4", "in_s": 0.0, "out_s": 30.0},
        ])
        data = plan_motion.load_plan_data(plan_path)
        plan_motion.plan_motion(data)

        segments = data["segments"]
        self.assertEqual(len(segments), 6)
        kinds = [s["motion"]["kind"] for s in segments]
        self.assertEqual(kinds, ["punch-in", "punch-out", "punch-in",
                                  "punch-out", "punch-in", "punch-out"])
        for s in segments:
            self.assertAlmostEqual(s["out_s"] - s["in_s"], 5.0)

    def test_existing_motion_is_left_unchanged_and_listed_as_skipped(self):
        self._touch("scene-04.mp4")
        manual_motion = {"kind": "punch-out", "from": 1.05, "to": 1.0}
        plan_path = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-04.mp4", "in_s": 0.0, "out_s": 9.0,
             "motion": manual_motion},
        ])
        data = plan_motion.load_plan_data(plan_path)
        report = plan_motion.plan_motion(data)

        self.assertEqual(len(data["segments"]), 1)
        self.assertEqual(data["segments"][0]["motion"], manual_motion)
        self.assertEqual(report["changed"], [])
        self.assertEqual(report["skipped"], ["S4: already has motion"])

    def test_shot_segment_is_skipped_with_reason_already_animated(self):
        (self.project / "shots" / "out").mkdir(parents=True)
        (self.project / "shots" / "out" / "MetricReveal.mp4").write_bytes(b"x")
        plan_path = write_plan(self.project, [
            {"kind": "shot", "src": "shots/out/MetricReveal.mp4", "in_s": 0.0, "out_s": 9.0},
        ])
        data = plan_motion.load_plan_data(plan_path)
        report = plan_motion.plan_motion(data)

        self.assertEqual(len(data["segments"]), 1)
        self.assertNotIn("motion", data["segments"][0])
        self.assertEqual(report["changed"], [])
        self.assertEqual(report["skipped"], ["segment 1: already animated"])

    def test_empty_segment_list_writes_unchanged_plan_and_exits_zero(self):
        plan_path = write_plan(self.project, [])
        rc = plan_motion.main([str(self.project)])
        self.assertEqual(rc, 0)
        data = json.loads(plan_path.read_text())
        self.assertEqual(data["segments"], [])

    def test_out_s_not_after_in_s_raises_naming_segment_index(self):
        self._touch("scene-05.mp4")
        plan_path = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-05.mp4", "in_s": 2.0, "out_s": 1.0},
        ])
        data = plan_motion.load_plan_data(plan_path)
        with self.assertRaises(plan_motion.PlanMotionError) as ctx:
            plan_motion.plan_motion(data)
        self.assertIn("segment 1", str(ctx.exception))

    def test_running_twice_reports_zero_changes(self):
        self._touch("scene-06.mp4")
        write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-06.mp4", "in_s": 0.0, "out_s": 8.4},
        ])
        rc1 = plan_motion.main([str(self.project)])
        self.assertEqual(rc1, 0)

        plan_path = self.project / "work" / "edit-plan.json"
        data = plan_motion.load_plan_data(plan_path)
        report = plan_motion.plan_motion(data)
        self.assertEqual(report["changed"], [])

    def test_generated_plan_survives_edit_render_load_plan(self):
        self._touch("scene-07.mp4")
        plan_path = write_plan(self.project, [
            {"kind": "clip", "src": "clips/scene-07.mp4", "in_s": 0.0, "out_s": 8.4},
        ])
        data = plan_motion.load_plan_data(plan_path)
        plan_motion.plan_motion(data)
        plan_path.write_text(json.dumps(data, indent=2))

        loaded = edit_render.load_plan(plan_path, self.project, check_durations=False)
        self.assertEqual(len(loaded.segments), 2)

    def test_missing_plan_file_exits_nonzero_naming_file(self):
        rc = plan_motion.main([str(self.project)])
        self.assertEqual(rc, 1)

    def test_invalid_plan_json_names_file_in_message(self):
        path = self.project / "work" / "edit-plan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not valid json")
        with self.assertRaises(plan_motion.PlanMotionError) as ctx:
            plan_motion.load_plan_data(path)
        self.assertIn("edit-plan.json", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
