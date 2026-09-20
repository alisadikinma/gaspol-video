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

    # -- Phase B2: align_to_script() -----------------------------------------

    def test_asr_text_never_reaches_the_plan(self):
        asr_words = [
            {"text": "Sistem", "start_ms": 0, "end_ms": 400},
            {"text": "ANPR", "start_ms": 400, "end_ms": 800},
        ]
        aligned = gen_captions.align_to_script(asr_words, "Sistem ANPR-nya")
        texts = [w["text"] for w in aligned]
        self.assertEqual(texts, ["Sistem", "ANPR-nya"])
        self.assertEqual(aligned[0]["start_ms"], 0)
        self.assertEqual(aligned[0]["end_ms"], 400)
        self.assertEqual(aligned[1]["start_ms"], 400)
        self.assertEqual(aligned[1]["end_ms"], 800)

    def test_empty_asr_words_raises(self):
        with self.assertRaises(gen_captions.CaptionPlanError):
            gen_captions.align_to_script([], "Sistem ANPR")

    def test_whitespace_only_script_text_raises(self):
        asr_words = [{"text": "Sistem", "start_ms": 0, "end_ms": 400}]
        with self.assertRaises(gen_captions.CaptionPlanError):
            gen_captions.align_to_script(asr_words, "   ")

    def test_dropped_word_is_interpolated_strictly_between_neighbours(self):
        # Recognizer never heard "dua" at all.
        asr_words = [
            {"text": "satu", "start_ms": 0, "end_ms": 300},
            {"text": "tiga", "start_ms": 900, "end_ms": 1200},
        ]
        aligned = gen_captions.align_to_script(asr_words, "satu dua tiga")
        self.assertEqual([w["text"] for w in aligned], ["satu", "dua", "tiga"])
        self.assertEqual((aligned[0]["start_ms"], aligned[0]["end_ms"]), (0, 300))
        self.assertEqual((aligned[2]["start_ms"], aligned[2]["end_ms"]), (900, 1200))
        # Strictly between the flanking (matched) words' own timings.
        self.assertGreater(aligned[1]["start_ms"], aligned[0]["end_ms"])
        self.assertLess(aligned[1]["end_ms"], aligned[2]["start_ms"])

    def test_recognizer_extra_word_is_dropped_entirely(self):
        # Recognizer heard a filler word the script never had.
        asr_words = [
            {"text": "eh", "start_ms": 0, "end_ms": 100},
            {"text": "satu", "start_ms": 100, "end_ms": 400},
        ]
        aligned = gen_captions.align_to_script(asr_words, "satu")
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["text"], "satu")
        self.assertEqual((aligned[0]["start_ms"], aligned[0]["end_ms"]), (100, 400))

    def test_head_and_tail_unmatched_clamp_to_recognizer_span(self):
        asr_words = [
            {"text": "mulai", "start_ms": 0, "end_ms": 100},
            {"text": "satu", "start_ms": 100, "end_ms": 400},
            {"text": "dua", "start_ms": 400, "end_ms": 700},
            {"text": "akhir", "start_ms": 700, "end_ms": 900},
        ]
        aligned = gen_captions.align_to_script(asr_words, "oh satu dua ya")
        self.assertEqual([w["text"] for w in aligned], ["oh", "satu", "dua", "ya"])
        # Head clamps to the recognizer's FIRST timing, tail to its LAST — never
        # before the first word or after the last.
        self.assertEqual((aligned[0]["start_ms"], aligned[0]["end_ms"]), (0, 100))
        self.assertEqual((aligned[3]["start_ms"], aligned[3]["end_ms"]), (700, 900))
        self.assertEqual((aligned[1]["start_ms"], aligned[1]["end_ms"]), (100, 400))
        self.assertEqual((aligned[2]["start_ms"], aligned[2]["end_ms"]), (400, 700))

    def test_zero_matches_spreads_timing_evenly_across_recognizer_span(self):
        asr_words = [
            {"text": "lain", "start_ms": 0, "end_ms": 500},
            {"text": "ucap", "start_ms": 500, "end_ms": 1000},
        ]
        aligned = gen_captions.align_to_script(asr_words, "beda kata")
        self.assertEqual([w["text"] for w in aligned], ["beda", "kata"])
        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0]["start_ms"], 0)
        self.assertEqual(aligned[1]["end_ms"], 1000)
        self.assertLessEqual(aligned[0]["end_ms"], aligned[1]["start_ms"])

    def test_aligned_flag_only_on_assemblyai_scenes(self):
        fake_words = {"words": [
            {"text": "Sudah", "start_ms": 0, "end_ms": 300},
            {"text": "lewat", "start_ms": 300, "end_ms": 600},
            {"text": "Pak", "start_ms": 600, "end_ms": 900},
        ]}
        with patch("tools.gen_captions.transcribe_assemblyai", return_value=fake_words):
            plan = gen_captions.build_caption_plan(self.project, api_key="fake-key")
        scene1 = [s for s in plan["scenes"] if s["scene"] == 1][0]
        scene2 = [s for s in plan["scenes"] if s["scene"] == 2][0]
        self.assertNotIn("aligned", scene1)
        self.assertTrue(scene2["aligned"])

    def test_highlight_spans_address_script_words_not_recognizer_words(self):
        audio_plan = {
            "scenes": [{"scene": 31, "audio_source": "platform-native", "layers": [
                {"kind": "dialogue", "at_s": 0.0, "out": "vo/scene-31-c1.mp3",
                 "text": "Ambil lima menit saja"}]}]
        }
        manifest = {"items": [{"id": "scene-31-c1", "file": "vo/scene-31-c1.mp3",
                                "scene": 31, "words": []}]}
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(audio_plan))
        (self.project / "vo" / "vo-manifest.json").write_text(json.dumps(manifest))

        # Recognizer mishears "lima" as "l1ma" — it must never reach the plan.
        fake_words = {"words": [
            {"text": "Ambil", "start_ms": 0, "end_ms": 300},
            {"text": "l1ma", "start_ms": 300, "end_ms": 600},
            {"text": "menit", "start_ms": 600, "end_ms": 900},
            {"text": "saja", "start_ms": 900, "end_ms": 1200},
        ]}
        with patch("tools.gen_captions.transcribe_assemblyai", return_value=fake_words):
            plan = gen_captions.build_caption_plan(self.project, api_key="fake-key")

        scene31 = [s for s in plan["scenes"] if s["scene"] == 31][0]
        texts = [w["text"] for w in scene31["words"]]
        self.assertEqual(texts, ["Ambil", "lima", "menit", "saja"])
        highlight = [h for h in scene31["highlights"] if h["rule"] == "number-unit"][0]
        self.assertEqual(highlight["start_word"], 1)
        self.assertEqual(highlight["end_word"], 2)
        self.assertEqual(scene31["words"][highlight["start_word"]]["text"], "lima")


if __name__ == "__main__":
    unittest.main()
