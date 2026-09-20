import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import gen_captions


AUDIO_PLAN = {
    "audio_source": "mixed",
    "scenes": [
        {"scene": 1, "audio_source": "elevenlabs", "layers": [
            {"kind": "narration", "cast": "c1", "at_s": 0.4, "dur_s": 2.4, "from": "tts",
             "text": "Sistem ANPR membaca plat itu dalam dua detik.",
             "out": "vo/scene-01-narr.mp3"}]},
        {"scene": 2, "audio_source": "platform-native", "layers": [
            {"kind": "dialogue", "cast": "c2", "at_s": 6.0, "dur_s": 2.0, "from": "clip",
             "text": "Sudah lewat, Pak.", "out": "vo/scene-02-c2.mp3"}]},
    ],
}

VO_MANIFEST = {
    "items": [
        {"id": "scene-01-narr", "file": "vo/scene-01-narr.mp3", "scene": 1, "duration_s": 2.4,
         "words": [
             {"text": "Sistem", "start_ms": 0, "end_ms": 400},
             {"text": "ANPR", "start_ms": 400, "end_ms": 800},
             {"text": "membaca", "start_ms": 800, "end_ms": 1300},
             {"text": "plat", "start_ms": 1300, "end_ms": 1600},
             {"text": "itu", "start_ms": 1600, "end_ms": 1800},
             {"text": "dalam", "start_ms": 1800, "end_ms": 2050},
             {"text": "dua", "start_ms": 2050, "end_ms": 2200},
             {"text": "detik.", "start_ms": 2200, "end_ms": 2400},
         ]},
        {"id": "scene-02-c2", "file": "vo/scene-02-c2.mp3", "scene": 2, "duration_s": 2.0,
         "words": []},
    ]
}


def _long_scene_words():
    """18 words, three page buckets, at least four scoring spans of different rules."""
    texts = ["Sistem", "ANPR", "membaca", "5", "tahun", "tapi", "OCR", "jalan", "lalu",
             "bukan", "padahal", "10", "persen", "justru", "lambat", "cepat", "malah", "saja"]
    words = []
    t = 0
    for text in texts:
        words.append({"text": text, "start_ms": t, "end_ms": t + 300})
        t += 300
    return words


class GenCaptionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        (self.project / "vo").mkdir()
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(AUDIO_PLAN))
        (self.project / "vo" / "vo-manifest.json").write_text(json.dumps(VO_MANIFEST))
        (self.project / "strategic-brief.md").write_text("# Brief\n\nProduct: **INDUSIA Gate**\n")
        (self.project / "cast-profile.md").write_text("## cast-c1 — Ali Sadikin\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_builds_plan_from_manifest_words(self):
        plan = gen_captions.build_caption_plan(self.project)
        scene1 = [s for s in plan["scenes"] if s["scene"] == 1]
        self.assertEqual(len(scene1), 1)
        self.assertEqual(scene1[0]["timing_source"], "elevenlabs")
        rules = [h["rule"] for h in scene1[0]["highlights"]]
        self.assertIn("number-unit", rules)

    def test_scene_with_empty_words_and_no_api_key_is_untimed(self):
        plan = gen_captions.build_caption_plan(self.project, api_key=None)
        self.assertFalse([s for s in plan["scenes"] if s["scene"] == 2])
        untimed = {u["scene"]: u["reason"] for u in plan["untimed"]}
        self.assertEqual(untimed[2], "no words in manifest and no ASSEMBLYAI_API_KEY")

    def test_scene_with_empty_words_uses_assemblyai_when_available(self):
        fake_words = {"words": [
            {"text": "Sudah", "start_ms": 0, "end_ms": 300, "confidence": 0.9},
            {"text": "lewat", "start_ms": 300, "end_ms": 600, "confidence": 0.9},
            {"text": "Pak", "start_ms": 600, "end_ms": 900, "confidence": 0.9},
        ]}
        with patch("tools.gen_captions.transcribe_assemblyai", return_value=fake_words) as mocked:
            plan = gen_captions.build_caption_plan(self.project, api_key="fake-key")
        mocked.assert_called_once()
        scene2 = [s for s in plan["scenes"] if s["scene"] == 2]
        self.assertEqual(len(scene2), 1)
        self.assertEqual(scene2[0]["timing_source"], "assemblyai")
        self.assertEqual(len(scene2[0]["words"]), 3)

    def test_rerun_without_force_does_not_rewrite(self):
        rc1 = gen_captions.main([str(self.project)])
        self.assertEqual(rc1, 0)
        out_path = self.project / "work" / "caption-plan.json"
        content1 = out_path.read_text()

        rc2 = gen_captions.main([str(self.project)])
        self.assertEqual(rc2, 0)
        content2 = out_path.read_text()
        self.assertEqual(content1, content2)

    def test_force_regenerates_with_byte_identical_scenes(self):
        gen_captions.main([str(self.project)])
        out_path = self.project / "work" / "caption-plan.json"
        plan1 = json.loads(out_path.read_text())

        rc = gen_captions.main([str(self.project), "--force"])
        self.assertEqual(rc, 0)
        plan2 = json.loads(out_path.read_text())

        self.assertEqual(plan1["scenes"], plan2["scenes"])
        self.assertEqual(plan1["untimed"], plan2["untimed"])

    def test_three_page_scene_caps_to_one_highlight(self):
        audio_plan = {
            "scenes": [{"scene": 9, "audio_source": "elevenlabs", "layers": [
                {"kind": "narration", "at_s": 0.0, "out": "vo/scene-09-narr.mp3",
                 "text": "long scene"}]}]
        }
        words = _long_scene_words()
        manifest = {"items": [{"id": "scene-09-narr", "file": "vo/scene-09-narr.mp3",
                                "scene": 9, "words": words}]}
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(audio_plan))
        (self.project / "vo" / "vo-manifest.json").write_text(json.dumps(manifest))

        plan = gen_captions.build_caption_plan(self.project)
        scene9 = [s for s in plan["scenes"] if s["scene"] == 9][0]
        # 18 words -> 3 pages -> allowed = max(1, 3 // 4) == 1, despite >= 4 candidate spans.
        self.assertEqual(len(scene9["highlights"]), 1)
        self.assertEqual(scene9["highlights"][0]["rule"], "number-unit")

    def test_missing_manifest_exits_nonzero_naming_file(self):
        (self.project / "vo" / "vo-manifest.json").unlink()
        rc = gen_captions.main([str(self.project)])
        self.assertEqual(rc, 1)

    def test_invalid_manifest_json_names_file_in_message(self):
        (self.project / "vo" / "vo-manifest.json").write_text("{not valid json")
        with self.assertRaises(gen_captions.CaptionPlanError) as ctx:
            gen_captions.build_caption_plan(self.project)
        self.assertIn("vo-manifest.json", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
