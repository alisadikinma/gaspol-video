import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import music_brief


def make_brief(**over):
    brief = {
        "topic": "container port automation",
        "domain": "port logistics",
        "tone": "Serious",
        "sound_world": "container port, cranes, industrial pulse",
        "segments": [
            {"from_s": 0, "to_s": 20, "beat": "hook", "energy": 4},
            {"from_s": 20, "to_s": 90, "beat": "body", "energy": 2},
        ],
    }
    brief.update(over)
    return brief


class BuildPromptTest(unittest.TestCase):
    def test_topic_and_sound_world_change_the_prompt(self):
        seg = {"from_s": 0, "to_s": 30, "beat": "body", "energy": 3}
        port = music_brief.build_prompt(make_brief(), seg)
        ward = music_brief.build_prompt(
            make_brief(topic="hospital ward", sound_world="hospital ward, soft monitors, hushed air"), seg)
        self.assertNotEqual(port, ward)
        for prompt in (port, ward):
            self.assertLessEqual(len(prompt), 400)
            self.assertIn("no vocals", prompt)
        self.assertIn("container port", port)
        self.assertIn("hospital ward", ward)

    def test_order_is_tone_beat_world_energy_tail(self):
        seg = {"from_s": 0, "to_s": 30, "beat": "build", "energy": 5}
        prompt = music_brief.build_prompt(make_brief(), seg)
        parts = ["restrained low pulse", "gradually rising tension", "container port",
                 "maximum energy", "instrumental, no vocals"]
        positions = [prompt.index(p) for p in parts]
        self.assertEqual(positions, sorted(positions))

    def test_overlong_sound_world_stays_under_cap(self):
        brief = make_brief(sound_world="x" * 600)
        seg = {"from_s": 0, "to_s": 30, "beat": "body", "energy": 3}
        prompt = music_brief.build_prompt(brief, seg)
        self.assertLessEqual(len(prompt), 400)
        self.assertTrue(prompt.endswith("leaves room for a speaking voice"))

    def test_energy_dropped_before_world_is_trimmed(self):
        seg = {"from_s": 0, "to_s": 30, "beat": "body", "energy": 3}
        base = ", ".join([music_brief.TONE_WORDS["Serious"], music_brief.BEAT_WORDS["body"],
                          music_brief.TAIL])
        room = 400 - len(base) - len("medium energy, ")
        brief = make_brief(sound_world="w" * (room + 5))
        prompt = music_brief.build_prompt(brief, seg)
        self.assertNotIn("medium energy", prompt)
        self.assertIn("w" * (room + 5), prompt)

    def test_unicode_sound_world(self):
        seg = {"from_s": 0, "to_s": 30, "beat": "body", "energy": 3}
        prompt = music_brief.build_prompt(make_brief(sound_world="gamelan, suling, kopi tubruk"), seg)
        self.assertIn("gamelan", prompt)
        prompt = music_brief.build_prompt(make_brief(sound_world="東京の駅 café"), seg)
        self.assertIn("東京の駅 café", prompt)


class MoodIdTest(unittest.TestCase):
    def test_same_input_same_id(self):
        self.assertEqual(music_brief.mood_id("a prompt", 30), music_brief.mood_id("a prompt", 30))

    def test_shape(self):
        mid = music_brief.mood_id("a prompt", 30)
        self.assertRegex(mid, r"^brief-[0-9a-f]{10}$")

    def test_different_length_different_id(self):
        self.assertNotEqual(music_brief.mood_id("p", 30), music_brief.mood_id("p", 31))

    def test_different_beat_different_id(self):
        brief = make_brief()
        a = music_brief.build_prompt(brief, {"from_s": 0, "to_s": 30, "beat": "hook", "energy": 3})
        b = music_brief.build_prompt(brief, {"from_s": 0, "to_s": 30, "beat": "peak", "energy": 3})
        self.assertNotEqual(music_brief.mood_id(a, 30), music_brief.mood_id(b, 30))


class LengthTest(unittest.TestCase):
    def test_clamp(self):
        seg = lambda a, b: {"from_s": a, "to_s": b}
        self.assertEqual(music_brief.segment_length_s(seg(0, 4)), 10)
        self.assertEqual(music_brief.segment_length_s(seg(0, 10)), 10)
        self.assertEqual(music_brief.segment_length_s(seg(0, 120)), 120)
        self.assertEqual(music_brief.segment_length_s(seg(0, 600)), 120)
        self.assertEqual(music_brief.segment_length_s(seg(5, 47.5)), 42.5)


class ValidateTest(unittest.TestCase):
    def assertRefuses(self, brief, needle):
        with self.assertRaises(music_brief.BriefError) as ctx:
            music_brief.validate(brief)
        self.assertIn(needle, str(ctx.exception))

    def test_valid_brief_passes(self):
        music_brief.validate(make_brief())

    def test_empty_topic(self):
        self.assertRefuses(make_brief(topic="  "), "topic")

    def test_missing_domain(self):
        brief = make_brief()
        del brief["domain"]
        self.assertRefuses(brief, "domain")

    def test_empty_sound_world(self):
        self.assertRefuses(make_brief(sound_world=""), "sound_world")

    def test_unknown_tone(self):
        self.assertRefuses(make_brief(tone="Angry"), "tone")

    def test_unknown_beat(self):
        segs = [{"from_s": 0, "to_s": 20, "beat": "drop", "energy": 3}]
        self.assertRefuses(make_brief(segments=segs), "segment 1: beat")

    def test_energy_out_of_range(self):
        for energy in (0, 6, "high", True):
            segs = [{"from_s": 0, "to_s": 20, "beat": "hook", "energy": energy}]
            self.assertRefuses(make_brief(segments=segs), "segment 1: energy")

    def test_overlap(self):
        segs = [{"from_s": 0, "to_s": 20, "beat": "hook", "energy": 3},
                {"from_s": 15, "to_s": 40, "beat": "body", "energy": 3}]
        self.assertRefuses(make_brief(segments=segs), "overlap")

    def test_duplicate_segments_overlap(self):
        seg = {"from_s": 0, "to_s": 20, "beat": "hook", "energy": 3}
        self.assertRefuses(make_brief(segments=[seg, dict(seg)]), "overlap")

    def test_end_not_after_start(self):
        segs = [{"from_s": 10, "to_s": 10, "beat": "hook", "energy": 3}]
        self.assertRefuses(make_brief(segments=segs), "segment 1: to_s")

    def test_non_numeric_times(self):
        segs = [{"from_s": "a", "to_s": 10, "beat": "hook", "energy": 3}]
        self.assertRefuses(make_brief(segments=segs), "segment 1: from_s")

    def test_no_segments(self):
        self.assertRefuses(make_brief(segments=[]), "segments")


class NonFiniteTest(unittest.TestCase):
    def test_nan_and_infinity_refused_naming_segment_and_field(self):
        for field, bad in (("from_s", float("nan")), ("to_s", float("inf")),
                           ("to_s", float("nan")), ("from_s", float("-inf"))):
            brief = make_brief()
            brief["segments"][0][field] = bad
            with self.assertRaises(music_brief.BriefError) as cm:
                music_brief.validate(brief)
            self.assertIn("segment 1", str(cm.exception))
            self.assertIn(field, str(cm.exception))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        self.brief_path = self.project / "work" / "music-brief.json"
        self.brief_path.write_text(json.dumps(make_brief()), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = music_brief.main([str(self.project), *args])
        return code, out.getvalue(), err.getvalue()

    def test_writes_palette_and_plan(self):
        code, _, _ = self.run_main()
        self.assertEqual(code, 0)
        palette = json.loads((self.project / "work" / "music-palette.json").read_text())
        plan = json.loads((self.project / "work" / "music-plan.json").read_text())
        self.assertEqual(len(palette["moods"]), 2)
        self.assertEqual(palette["defaults"]["model"], "music_v2")
        brief = make_brief()
        for mood, seg in zip(palette["moods"], brief["segments"]):
            prompt = music_brief.build_prompt(brief, seg)
            self.assertEqual(mood["prompt"], prompt)
            self.assertEqual(mood["tones"], ["Serious"])
            length = music_brief.segment_length_s(seg)
            self.assertEqual(mood["duration_s"], length)
            self.assertEqual(mood["id"], music_brief.mood_id(prompt, length))
        self.assertEqual([s["track"] for s in plan["segments"]],
                         [f"library:{m['id']}" for m in palette["moods"]])
        self.assertEqual([(s["from_s"], s["to_s"]) for s in plan["segments"]], [(0, 20), (20, 90)])
        self.assertNotIn("gain_db", plan["segments"][0])

    def test_preserves_existing_out(self):
        plan_path = self.project / "work" / "music-plan.json"
        plan_path.write_text(json.dumps({"out": "output/custom.mp4", "segments": []}))
        self.assertEqual(self.run_main()[0], 0)
        self.assertEqual(json.loads(plan_path.read_text())["out"], "output/custom.mp4")

    def test_print_writes_nothing(self):
        code, out, _ = self.run_main("--print")
        self.assertEqual(code, 0)
        self.assertFalse((self.project / "work" / "music-palette.json").exists())
        self.assertFalse((self.project / "work" / "music-plan.json").exists())
        self.assertIn("hook", out)
        self.assertIn("brief-", out)

    def test_identical_rerun_same_ids(self):
        self.run_main()
        first = (self.project / "work" / "music-palette.json").read_text()
        self.run_main()
        self.assertEqual(first, (self.project / "work" / "music-palette.json").read_text())

    def test_missing_brief(self):
        self.brief_path.unlink()
        code, _, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("music-brief.json", err)

    def test_bad_json(self):
        self.brief_path.write_text("{not json")
        code, _, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_invalid_field_exit_2_and_no_files(self):
        self.brief_path.write_text(json.dumps(make_brief(tone="Angry")))
        code, _, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("tone", err)
        self.assertFalse((self.project / "work" / "music-palette.json").exists())

    def test_malformed_existing_plan_exit_2_and_nothing_written(self):
        plan_path = self.project / "work" / "music-plan.json"
        plan_path.write_text("{broken")
        code, _, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("music-plan.json", err)
        self.assertEqual(plan_path.read_text(), "{broken")
        self.assertFalse((self.project / "work" / "music-palette.json").exists())

    def test_existing_plan_keeps_other_keys(self):
        plan_path = self.project / "work" / "music-plan.json"
        plan_path.write_text(json.dumps({"out": "o.mp4", "bed_source": "palette", "extra": 7,
                                         "segments": []}))
        code, out, err = self.run_main()
        self.assertEqual(code, 0)
        plan = json.loads(plan_path.read_text())
        self.assertEqual((plan["bed_source"], plan["extra"], plan["out"]), ("palette", 7, "o.mp4"))
        self.assertEqual(len(plan["segments"]), 2)
        self.assertNotIn("bed_source", out + err)

    def test_bed_source_video_warns_segments_replaced(self):
        plan_path = self.project / "work" / "music-plan.json"
        plan_path.write_text(json.dumps({"out": "o.mp4", "bed_source": "video", "segments": []}))
        code, out, err = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(plan_path.read_text())["bed_source"], "video")
        self.assertIn("bed_source", out + err)
        self.assertIn("replaced", out + err)

    def test_palette_failure_leaves_plan_unwritten_and_no_temp_files(self):
        (self.project / "work" / "music-palette.json").mkdir()
        code, _, _ = self.run_main()
        self.assertNotEqual(code, 0)
        self.assertFalse((self.project / "work" / "music-plan.json").exists())
        self.assertEqual([p.name for p in (self.project / "work").glob("*.tmp")], [])

    def test_atomic_write_ignores_planted_symlink_temp_name(self):
        victim = self.project / "victim.txt"
        victim.write_text("keep")
        (self.project / "work" / "music-plan.json.tmp").symlink_to(victim)
        self.assertEqual(self.run_main()[0], 0)
        self.assertEqual(victim.read_text(), "keep")

    def test_custom_brief_path(self):
        other = self.project / "work" / "alt.json"
        other.write_text(json.dumps(make_brief()))
        self.brief_path.unlink()
        self.assertEqual(self.run_main("--brief", "work/alt.json")[0], 0)


if __name__ == "__main__":
    unittest.main()
