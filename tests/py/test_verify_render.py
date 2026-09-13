import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tools import gen_subs, verify_render


def audio_plan_one_layer(text, dur_s=4.0, scene=1, at_s=0.0, kind="narration"):
    return {"audio_source": "elevenlabs", "scenes": [
        {"scene": scene, "audio_source": "elevenlabs", "layers": [
            {"kind": kind, "cast": "c1", "at_s": at_s, "dur_s": dur_s, "from": "tts",
             "text": text, "out": f"vo/scene-{scene:02d}-narr.mp3"},
        ]},
    ]}


def edit_plan_segments(segments):
    return {"fps": 30, "width": 1920, "height": 1080, "out": "output/master.mp4",
            "segments": segments}


def evenly_timed_words(text, total_ms, confidence=0.95):
    """ASR words spread evenly across total_ms, matching the script word-for-word."""
    words = text.replace(".", "").split()
    n = len(words)
    step = total_ms / n
    out = []
    for i, w in enumerate(words):
        start = int(round(i * step))
        end = int(round((i + 1) * step)) - 20  # small gap, never touching, never >= 400ms
        out.append({"text": w, "start_ms": start, "end_ms": max(start + 10, end), "confidence": confidence})
    return out


class VerifyRenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_plans(self, audio_plan, edit_plan):
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(audio_plan))
        (self.project / "work" / "edit-plan.json").write_text(json.dumps(edit_plan))

    def _run(self, rendered_words):
        audio_plan = audio_plan_one_layer("Tiap truk antre 42 menit di gerbang.")
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 4.0}])
        self._write_plans(audio_plan, edit_plan)
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": rendered_words}))
        return verify_render.verify(self.project, asr_json=str(asr_path))

    def test_identical_render_is_clean(self):
        rendered = evenly_timed_words("Tiap truk antre 42 menit di gerbang", 4000)
        outcome = self._run(rendered)
        r = outcome["result"]
        self.assertEqual(len(r["inserted"]), 0)
        self.assertEqual(len(r["missing"]), 0)
        self.assertEqual(len(r["replaced"]), 0)
        self.assertEqual(len(r["gaps"]), 0)
        self.assertEqual(len(r["lowconf"]), 0)
        self.assertEqual(r["drift_flags"], 0)
        self.assertEqual(outcome["exit_code"], 0)

    def test_extra_word_is_inserted_and_fails(self):
        rendered = evenly_timed_words("Tiap truk antre 42 menit di gerbang", 4000)
        rendered.insert(2, {"text": "eh", "start_ms": rendered[1]["end_ms"] + 5,
                             "end_ms": rendered[1]["end_ms"] + 50, "confidence": 0.9})
        outcome = self._run(rendered)
        self.assertEqual(len(outcome["result"]["inserted"]), 1)
        self.assertEqual(outcome["exit_code"], 1)

    def test_dropped_word_is_missing(self):
        rendered = evenly_timed_words("Tiap truk antre 42 menit di gerbang", 4000)
        del rendered[4]  # "menit"
        outcome = self._run(rendered)
        self.assertEqual(len(outcome["result"]["missing"]), 1)
        self.assertEqual(outcome["result"]["missing"][0]["word"], "menit")
        self.assertEqual(outcome["exit_code"], 1)

    def test_word_heard_differently_is_replaced_not_missing_and_still_passes(self):
        rendered = evenly_timed_words("Tiap truk antre 42 menit di gerbang", 4000)
        rendered[-1]["text"] = "gerbong"
        outcome = self._run(rendered)
        r = outcome["result"]
        self.assertEqual(len(r["replaced"]), 1)
        self.assertEqual(r["replaced"][0]["expected"], "gerbang")
        self.assertEqual(r["replaced"][0]["heard"], "gerbong")
        self.assertEqual(len(r["missing"]), 0)
        self.assertEqual(len(r["inserted"]), 0)
        self.assertEqual(outcome["exit_code"], 0)

    def test_punctuation_and_case_are_not_counted(self):
        rendered = evenly_timed_words("Tiap truk antre 42 menit di gerbang", 4000)
        rendered[0]["text"] = "TIAP,"
        rendered[-1]["text"] = "Gerbang."
        outcome = self._run(rendered)
        r = outcome["result"]
        self.assertEqual(len(r["inserted"]), 0)
        self.assertEqual(len(r["missing"]), 0)
        self.assertEqual(len(r["replaced"]), 0)

    def test_big_interior_gap_is_flagged(self):
        rendered = evenly_timed_words("Tiap truk antre 42 menit di gerbang", 4000)
        # push every word after the gap later by 600ms, opening a gap inside the SAME layer
        for w in rendered[4:]:
            w["start_ms"] += 600
            w["end_ms"] += 600
        outcome = self._run(rendered)
        self.assertEqual(len(outcome["result"]["gaps"]), 1)

    def test_gap_between_two_layers_is_not_flagged(self):
        audio_plan = {"audio_source": "elevenlabs", "scenes": [
            {"scene": 1, "audio_source": "elevenlabs", "layers": [
                {"kind": "narration", "cast": "c1", "at_s": 0.0, "dur_s": 2.0, "from": "tts",
                 "text": "Truk antre", "out": "vo/scene-01-narr.mp3"},
            ]},
            {"scene": 2, "audio_source": "elevenlabs", "layers": [
                {"kind": "narration", "cast": "c1", "at_s": 0.0, "dur_s": 2.0, "from": "tts",
                 "text": "Gerbang dibuka", "out": "vo/scene-02-narr.mp3"},
            ]},
        ]}
        edit_plan = edit_plan_segments([
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0},
            {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": 2.0},
        ])
        self._write_plans(audio_plan, edit_plan)
        rendered = [
            {"text": "Truk", "start_ms": 0, "end_ms": 400, "confidence": 0.95},
            {"text": "antre", "start_ms": 400, "end_ms": 900, "confidence": 0.95},
            # a full second of silence at the scene boundary — expected, not an anomaly
            {"text": "Gerbang", "start_ms": 2000, "end_ms": 2400, "confidence": 0.95},
            {"text": "dibuka", "start_ms": 2400, "end_ms": 2900, "confidence": 0.95},
        ]
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": rendered}))
        outcome = verify_render.verify(self.project, asr_json=str(asr_path))
        self.assertEqual(len(outcome["result"]["gaps"]), 0)

    def test_low_confidence_word_is_flagged(self):
        rendered = evenly_timed_words("Tiap truk antre 42 menit di gerbang", 4000)
        rendered[3]["confidence"] = 0.5
        outcome = self._run(rendered)
        self.assertEqual(len(outcome["result"]["lowconf"]), 1)

    def test_second_scene_planned_start_includes_pad_end_s(self):
        audio_plan = {"audio_source": "elevenlabs", "scenes": [
            {"scene": 1, "audio_source": "elevenlabs", "layers": [
                {"kind": "narration", "cast": "c1", "at_s": 0.0, "dur_s": 2.0, "from": "tts",
                 "text": "Truk antre", "out": "vo/scene-01-narr.mp3"},
            ]},
            {"scene": 2, "audio_source": "elevenlabs", "layers": [
                {"kind": "narration", "cast": "c1", "at_s": 0.0, "dur_s": 1.0, "from": "tts",
                 "text": "Gerbang", "out": "vo/scene-02-narr.mp3"},
            ]},
        ]}
        # segment 1 is 2.0s of clip + 0.5s pad -> scene 2 starts at 2.5s, not 2.0s
        edit_plan = edit_plan_segments([
            {"kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 2.0, "pad_end_s": 0.5},
            {"kind": "clip", "src": "clips/scene-02.mp4", "in_s": 0.0, "out_s": 1.0},
        ])
        starts = verify_render.scene_starts(edit_plan)
        self.assertAlmostEqual(starts[1], 0.0)
        self.assertAlmostEqual(starts[2], 2.5)

        self._write_plans(audio_plan, edit_plan)
        rendered = [
            {"text": "Truk", "start_ms": 0, "end_ms": 400, "confidence": 0.95},
            {"text": "antre", "start_ms": 400, "end_ms": 900, "confidence": 0.95},
            # scene 2's word lands right at the planned 2.5s start -> no drift
            {"text": "Gerbang", "start_ms": 2500, "end_ms": 2900, "confidence": 0.95},
        ]
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": rendered}))
        outcome = verify_render.verify(self.project, asr_json=str(asr_path))
        self.assertEqual(outcome["result"]["drift_flags"], 0)

    def test_drift_beyond_budget_is_flagged(self):
        audio_plan = audio_plan_one_layer("Truk antre", dur_s=2.0)
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 2.0}])
        self._write_plans(audio_plan, edit_plan)
        # planned layer start is 0.0s; render starts 400ms late
        rendered = [
            {"text": "Truk", "start_ms": 400, "end_ms": 800, "confidence": 0.95},
            {"text": "antre", "start_ms": 800, "end_ms": 1300, "confidence": 0.95},
        ]
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": rendered}))
        outcome = verify_render.verify(self.project, asr_json=str(asr_path))
        self.assertEqual(outcome["result"]["drift_flags"], 1)

    def test_drift_within_budget_is_not_flagged(self):
        audio_plan = audio_plan_one_layer("Truk antre", dur_s=2.0)
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 2.0}])
        self._write_plans(audio_plan, edit_plan)
        # 100ms late — inside the 0.25s budget
        rendered = [
            {"text": "Truk", "start_ms": 100, "end_ms": 500, "confidence": 0.95},
            {"text": "antre", "start_ms": 500, "end_ms": 1000, "confidence": 0.95},
        ]
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": rendered}))
        outcome = verify_render.verify(self.project, asr_json=str(asr_path))
        self.assertEqual(outcome["result"]["drift_flags"], 0)

    def test_missing_audio_plan_raises_named_error(self):
        (self.project / "work" / "edit-plan.json").write_text(json.dumps(edit_plan_segments([])))
        with self.assertRaises(verify_render.VerifyError) as ctx:
            verify_render.verify(self.project, asr_json=str(self.project / "asr.json"))
        self.assertIn("audio-plan.json", str(ctx.exception))

    def test_no_key_and_no_asr_json_exits_3(self):
        audio_plan = audio_plan_one_layer("Truk antre")
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 2.0}])
        self._write_plans(audio_plan, edit_plan)
        outcome = verify_render.verify(self.project, env={})
        self.assertEqual(outcome["exit_code"], 3)

    def test_fewer_edit_segments_than_scenes_reports_skip_note(self):
        audio_plan = {"audio_source": "elevenlabs", "scenes": [
            {"scene": 1, "layers": [{"kind": "narration", "at_s": 0.0, "dur_s": 2.0,
                                      "text": "Halo dunia", "from": "tts", "out": "x"}]},
            {"scene": 2, "layers": [{"kind": "narration", "at_s": 0.0, "dur_s": 2.0,
                                      "text": "Selamat pagi", "from": "tts", "out": "y"}]},
        ]}
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 2.0}])
        self._write_plans(audio_plan, edit_plan)
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": evenly_timed_words("Halo dunia", 2000)}))
        logged = []
        outcome = verify_render.verify(self.project, asr_json=str(asr_path), log=logged.append)
        self.assertTrue(
            any("drift check skipped: 1 edit segments for 2 scenes" in line for line in logged),
            logged,
        )
        report = Path(outcome["report_path"]).read_text()
        self.assertIn("drift check skipped: 1 edit segments for 2 scenes", report)

    def test_nothing_to_verify_when_no_narration_or_dialogue_layers(self):
        audio_plan = {"audio_source": "elevenlabs", "scenes": [
            {"scene": 1, "audio_source": "platform-native", "layers": [
                {"kind": "sfx", "at_s": 0.0, "dur_s": 1.0, "text": "", "out": "sfx/x.mp3"},
            ]},
        ]}
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 2.0}])
        self._write_plans(audio_plan, edit_plan)
        outcome = verify_render.verify(self.project, env={})
        self.assertEqual(outcome["exit_code"], 0)

    # -- GV-2: spoken vs written numbers must not false-FAIL P6 -----------------------

    def _run_with_script(self, script_text, rendered_words):
        audio_plan = audio_plan_one_layer(script_text, dur_s=4.0)
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 4.0}])
        self._write_plans(audio_plan, edit_plan)
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": rendered_words}))
        return verify_render.verify(self.project, asr_json=str(asr_path))

    def test_script_words_asr_digits_is_clean(self):
        # script: "Tiap truk antre empat puluh dua menit" ; ASR collapsed the spoken
        # number to the single digit token "42" (real AssemblyAI behaviour, see
        # docs/evals/verify-render-run.md).
        rendered = [
            {"text": "Tiap", "start_ms": 0, "end_ms": 300, "confidence": 0.95},
            {"text": "truk", "start_ms": 300, "end_ms": 550, "confidence": 0.95},
            {"text": "antre", "start_ms": 550, "end_ms": 870, "confidence": 0.95},
            {"text": "42", "start_ms": 870, "end_ms": 1350, "confidence": 0.95},
            {"text": "menit", "start_ms": 1350, "end_ms": 1850, "confidence": 0.95},
        ]
        outcome = self._run_with_script("Tiap truk antre empat puluh dua menit", rendered)
        r = outcome["result"]
        self.assertEqual(len(r["missing"]), 0)
        self.assertEqual(len(r["inserted"]), 0)
        self.assertEqual(len(r["replaced"]), 0)
        self.assertEqual(outcome["exit_code"], 0)

    def test_script_digits_asr_words_is_clean(self):
        # the reverse: script writes "42", the ASR (or a human-read TTS quirk) comes
        # back with the number spelled out in words.
        rendered = [
            {"text": "empat", "start_ms": 0, "end_ms": 200, "confidence": 0.95},
            {"text": "puluh", "start_ms": 200, "end_ms": 400, "confidence": 0.95},
            {"text": "dua", "start_ms": 400, "end_ms": 600, "confidence": 0.95},
            {"text": "menit", "start_ms": 600, "end_ms": 900, "confidence": 0.95},
        ]
        outcome = self._run_with_script("42 menit", rendered)
        r = outcome["result"]
        self.assertEqual(len(r["missing"]), 0)
        self.assertEqual(len(r["inserted"]), 0)
        self.assertEqual(len(r["replaced"]), 0)
        self.assertEqual(outcome["exit_code"], 0)

    def test_a_genuinely_different_number_is_still_replaced(self):
        rendered = [
            {"text": "42", "start_ms": 0, "end_ms": 400, "confidence": 0.95},
        ]
        outcome = self._run_with_script("empat puluh tiga", rendered)
        r = outcome["result"]
        self.assertEqual(len(r["replaced"]), 1)
        self.assertEqual(r["replaced"][0]["expected"], "43")
        self.assertEqual(r["replaced"][0]["heard"], "42")
        self.assertEqual(len(r["missing"]), 0)
        self.assertEqual(len(r["inserted"]), 0)

    def test_collapsed_number_timestamps_span_first_to_last_source_word(self):
        # "empat puluh dua" spoken as 3 separate ASR words; the collapsed "42" token's
        # start/end must come from the FIRST and LAST source words, not just the first.
        audio_plan = audio_plan_one_layer("empat puluh dua", dur_s=3.0)
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 3.0}])
        self._write_plans(audio_plan, edit_plan)
        rendered = [
            {"text": "empat", "start_ms": 0, "end_ms": 300, "confidence": 0.95},
            {"text": "puluh", "start_ms": 300, "end_ms": 600, "confidence": 0.95},
            {"text": "dua", "start_ms": 600, "end_ms": 900, "confidence": 0.95},
        ]
        asr_path = self.project / "asr.json"
        asr_path.write_text(json.dumps({"words": rendered}))
        outcome = verify_render.verify(self.project, asr_json=str(asr_path))
        r = outcome["result"]
        self.assertEqual(len(r["missing"]), 0)
        # the drift row for this layer should anchor on the FIRST source word (0ms)
        self.assertEqual(len(r["drift_rows"]), 1)
        self.assertEqual(r["drift_rows"][0]["start_ms"], 0)


class NumberCollapseTest(unittest.TestCase):
    """Unit tests for the Indonesian/English number-word parser."""

    def test_id_units(self):
        cases = {
            "nol": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
            "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
        }
        for word, val in cases.items():
            with self.subTest(word=word):
                self.assertEqual(verify_render.collapse_numbers([word]), [str(val)])

    def test_id_teens_and_tens(self):
        cases = {
            "sepuluh": 10, "sebelas": 11,
        }
        for word, val in cases.items():
            with self.subTest(word=word):
                self.assertEqual(verify_render.collapse_numbers([word]), [str(val)])
        self.assertEqual(verify_render.collapse_numbers(["dua", "belas"]), ["12"])
        self.assertEqual(verify_render.collapse_numbers(["sembilan", "belas"]), ["19"])
        self.assertEqual(verify_render.collapse_numbers(["dua", "puluh"]), ["20"])
        self.assertEqual(verify_render.collapse_numbers(["dua", "puluh", "lima"]), ["25"])

    def test_id_hundreds_thousands_millions(self):
        self.assertEqual(verify_render.collapse_numbers(["seratus"]), ["100"])
        self.assertEqual(verify_render.collapse_numbers(["seratus", "dua"]), ["102"])
        self.assertEqual(
            verify_render.collapse_numbers(["dua", "ratus", "tiga", "puluh"]), ["230"])
        self.assertEqual(verify_render.collapse_numbers(["seribu"]), ["1000"])
        self.assertEqual(
            verify_render.collapse_numbers(["dua", "ribu", "dua", "puluh", "enam"]), ["2026"])
        self.assertEqual(verify_render.collapse_numbers(["satu", "juta"]), ["1000000"])
        self.assertEqual(
            verify_render.collapse_numbers(["lima", "juta", "tiga", "ratus", "ribu"]),
            ["5300000"])

    def test_en_numbers(self):
        cases = {
            "zero": "0", "seven": "7", "twelve": "12", "forty two": "42",
            "one hundred": "100", "one hundred and five": "105",
            "two thousand twenty six": "2026", "three million": "3000000",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(verify_render.collapse_numbers(phrase.split()), [expected])
        # hyphenated form, as it comes out of norm() (hyphen -> space)
        self.assertEqual(verify_render.collapse_numbers(["twenty", "one"]), ["21"])

    def test_non_number_words_are_left_unchanged(self):
        for word in ["menit", "satuan", "setiap", "seribuan"]:
            with self.subTest(word=word):
                self.assertEqual(verify_render.collapse_numbers([word]), [word])

    def test_number_run_inside_a_sentence(self):
        words = "setiap truk antre empat puluh dua menit".split()
        self.assertEqual(
            verify_render.collapse_numbers(words),
            ["setiap", "truk", "antre", "42", "menit"])

    def test_thousands_separators_normalise_to_plain_int(self):
        self.assertEqual(verify_render.norm("2.026"), ["2026"])
        self.assertEqual(verify_render.norm("2,026"), ["2026"])
        self.assertEqual(verify_render.norm("1.500.000"), ["1500000"])

    def test_percent_sign_and_word_map_to_persen(self):
        self.assertEqual(verify_render.norm("42%"), ["42", "persen"])
        self.assertEqual(verify_render.norm("42 percent"), ["42", "persen"])
        self.assertEqual(
            verify_render.collapse_numbers(verify_render.norm("empat puluh dua persen")),
            ["42", "persen"])

    def test_a_different_number_is_not_collapsed_into_a_match(self):
        self.assertEqual(verify_render.collapse_numbers(["empat", "puluh", "tiga"]), ["43"])
        self.assertNotEqual(
            verify_render.collapse_numbers(["empat", "puluh", "tiga"]),
            verify_render.collapse_numbers(["42"]))


class MainErrorWrappingTest(unittest.TestCase):
    """main() must never let a transcription-layer exception escape as a raw traceback —
    it should print `verify_render: <message>` and exit 1, same as VerifyError already does."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        (self.project / "output").mkdir()
        audio_plan = audio_plan_one_layer("Halo dunia")
        edit_plan = edit_plan_segments([{"kind": "clip", "src": "clips/scene-01.mp4",
                                          "in_s": 0.0, "out_s": 2.0}])
        (self.project / "work" / "audio-plan.json").write_text(json.dumps(audio_plan))
        (self.project / "work" / "edit-plan.json").write_text(json.dumps(edit_plan))
        (self.project / "output" / "master.mp4").write_bytes(b"fake")

    def tearDown(self):
        self.tmp.cleanup()

    def test_subtitle_error_from_transcription_is_caught(self):
        with mock.patch.object(verify_render, "_load_env",
                                return_value={"ASSEMBLYAI_API_KEY": "x"}), \
             mock.patch.object(verify_render, "_extract_audio"), \
             mock.patch.object(verify_render, "transcribe_assemblyai",
                                side_effect=gen_subs.SubtitleError("AssemblyAI failed: boom")):
            rc = verify_render.main([str(self.project)])
        self.assertEqual(rc, 1)

    def test_url_error_from_transcription_is_caught(self):
        with mock.patch.object(verify_render, "_load_env",
                                return_value={"ASSEMBLYAI_API_KEY": "x"}), \
             mock.patch.object(verify_render, "_extract_audio"), \
             mock.patch.object(verify_render, "transcribe_assemblyai",
                                side_effect=urllib.error.URLError("network down")):
            rc = verify_render.main([str(self.project)])
        self.assertEqual(rc, 1)

    def test_os_error_from_transcription_is_caught(self):
        with mock.patch.object(verify_render, "_load_env",
                                return_value={"ASSEMBLYAI_API_KEY": "x"}), \
             mock.patch.object(verify_render, "_extract_audio"), \
             mock.patch.object(verify_render, "transcribe_assemblyai",
                                side_effect=OSError("disk full")):
            rc = verify_render.main([str(self.project)])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
