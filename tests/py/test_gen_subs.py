import json
import tempfile
import unittest
from pathlib import Path

from tools import gen_subs


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
    ]
}


class GenSubsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        (self.project / "vo").mkdir()
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(AUDIO_PLAN))
        (self.project / "vo" / "vo-manifest.json").write_text(json.dumps(VO_MANIFEST))
        (self.project / "strategic-brief.md").write_text(
            "# Brief\n\nProduct: **INDUSIA Gate**\nDomain equipment: ANPR camera, boom barrier.\n"
            "Location: Cikarang, Indonesia.\n")
        (self.project / "cast-profile.md").write_text("## cast-c1 — Ali Sadikin\n## cast-c2 — Rudi\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_text_comes_from_script_not_asr(self):
        """ASR supplies timing only. A mangled transcript must not reach the screen."""
        mangled = {"words": [
            {"text": "sudah", "start_ms": 0, "end_ms": 400},
            {"text": "le", "start_ms": 400, "end_ms": 600},
            {"text": "what", "start_ms": 600, "end_ms": 900},
            {"text": "pak", "start_ms": 900, "end_ms": 1200},
        ]}
        plan = gen_subs.build_plan(self.project, asr_results={"scene-02-c2": mangled})
        cue = [c for c in plan["cues"] if c["scene"] == 2][0]
        self.assertEqual(cue["text"], "Sudah lewat, Pak.")
        self.assertEqual(cue["from"], "assemblyai")
        self.assertAlmostEqual(cue["at_s"], 6.0, delta=0.01)

    def test_tts_timestamps_are_used_when_available(self):
        plan = gen_subs.build_plan(self.project)
        cue = [c for c in plan["cues"] if c["scene"] == 1][0]
        self.assertEqual(cue["from"], "tts-timestamps")
        self.assertAlmostEqual(cue["at_s"], 0.4, delta=0.01)
        self.assertGreater(cue["end_s"], cue["at_s"])

    def test_keyterms_are_derived_from_the_brief_and_the_cast(self):
        terms = gen_subs.derive_keyterms(self.project)
        joined = " ".join(terms).lower()
        self.assertIn("anpr", joined)
        self.assertIn("indusia", joined)
        self.assertTrue(any("cikarang" in t.lower() for t in terms))

    def test_cues_never_overlap(self):
        plan = gen_subs.build_plan(self.project)
        cues = sorted(plan["cues"], key=lambda c: c["at_s"])
        for a, b in zip(cues, cues[1:]):
            self.assertLessEqual(a["end_s"], b["at_s"] + 1e-6,
                                 f"cue {a['index']} overlaps cue {b['index']}")

    def test_cue_past_the_master_is_rejected(self):
        with self.assertRaises(gen_subs.SubtitleError):
            gen_subs.build_plan(self.project, master_duration_s=1.0)

    def test_long_line_is_wrapped_not_clipped(self):
        line = "Sistem membaca plat kendaraan yang masuk gerbang utama pelabuhan dalam dua detik saja"
        lines = gen_subs.split_lines(line, max_chars=38)
        for part in lines:
            self.assertLessEqual(len(part), 38, "a caption line must never exceed the reading width")
        self.assertEqual(" ".join(lines).split(), line.split(), "no word may be lost")

    def test_a_line_too_long_for_one_screen_becomes_two_cues(self):
        """Squeezing would clip words or blow past the reading width. Splitting does neither."""
        long_text = ("Sistem membaca plat kendaraan yang masuk gerbang utama pelabuhan "
                     "dalam dua detik saja dan langsung mencatatnya ke dashboard operasional")
        plan_data = json.loads((self.project / "work" / "audio-plan.json").read_text())
        plan_data["scenes"][0]["layers"][0]["text"] = long_text
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(plan_data))
        plan = gen_subs.build_plan(self.project)
        scene1 = [c for c in plan["cues"] if c["scene"] == 1]
        self.assertGreater(len(scene1), 1)
        recovered = " ".join(c["text"].replace("\n", " ") for c in scene1)
        self.assertEqual(recovered.split(), long_text.split(), "no word may be lost in the split")
        for cue in scene1:
            self.assertLessEqual(len(cue["text"].split("\n")), 2)

    def test_em_dash_survives_in_a_caption(self):
        """The em-dash ban is about spoken audio. Printed text is not read aloud by anyone."""
        plan_data = json.loads((self.project / "work" / "audio-plan.json").read_text())
        plan_data["scenes"][0]["layers"][0]["text"] = "Dua detik — bukan dua menit."
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(plan_data))
        plan = gen_subs.build_plan(self.project)
        self.assertIn("—", plan["cues"][0]["text"])

    def test_missing_timing_source_lists_the_scene_instead_of_guessing(self):
        (self.project / "vo" / "vo-manifest.json").unlink()
        plan = gen_subs.build_plan(self.project, asr_results={})
        self.assertTrue(plan["untimed"], "scenes with no timing source must be listed")
        self.assertIn(1, plan["untimed"])
        self.assertIn(2, plan["untimed"])

    def test_srt_is_well_formed(self):
        plan = gen_subs.build_plan(self.project)
        srt = gen_subs.to_srt(plan["cues"])
        self.assertTrue(srt.startswith("1\n"))
        self.assertIn(" --> ", srt)
        self.assertIn("00:00:0", srt)

    def test_empty_narration_produces_an_empty_plan_not_a_crash(self):
        (self.project / "work" / "audio-plan.json").write_text(json.dumps({"scenes": []}))
        plan = gen_subs.build_plan(self.project)
        self.assertEqual(plan["cues"], [])


if __name__ == "__main__":
    unittest.main()
