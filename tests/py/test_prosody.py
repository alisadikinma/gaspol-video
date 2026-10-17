import contextlib
import io
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from tools.vidkit import __main__ as vcli
from tools.vidkit import prosody


def write_wav(path, segments, sr=16000):
    """segments: [(seconds, freq_hz or 0 for silence, amplitude 0..1)]."""
    frames = bytearray()
    for dur, freq, amp in segments:
        for i in range(int(dur * sr)):
            v = amp * math.sin(2 * math.pi * freq * i / sr) if freq else 0.0
            frames += struct.pack("<h", int(v * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


class LoadWordsTest(unittest.TestCase):
    def _load(self, doc):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.json"
            p.write_text(json.dumps(doc))
            return prosody.load_words(p)

    def test_assemblyai_ms(self):
        w = self._load({"words": [{"text": "Hi.", "start_ms": 100, "end_ms": 400}]})
        self.assertEqual(w, [("Hi.", 0.1, 0.4)])

    def test_raw_assemblyai_transcript_ms(self):
        w = self._load({"text": "Hi.", "words": [{"text": "Hi.", "start": 100, "end": 400, "confidence": 0.9}]})
        self.assertEqual(w, [("Hi.", 0.1, 0.4)])

    def test_words_without_times_raise_value_error(self):
        with self.assertRaises(ValueError):
            self._load({"words": [{"text": "Hi."}]})

    def test_triplets(self):
        self.assertEqual(self._load([["Hi", 0.1, 0.4]]), [("Hi", 0.1, 0.4)])

    def test_word_dicts_seconds(self):
        self.assertEqual(self._load([{"word": "Hi", "start": 0.1, "end": 0.4}]), [("Hi", 0.1, 0.4)])

    def test_unknown_shape_raises(self):
        with self.assertRaises(ValueError):
            self._load({"nope": 1})


class SentencesTest(unittest.TestCase):
    W = [("Yeah,", 0.0, 0.4), ("it", 0.4, 0.6), ("flies.", 0.6, 1.0),
         ("But", 1.5, 1.7), ("how?", 1.7, 2.0)]

    def test_split_on_sentence_end(self):
        s = prosody.sentences(self.W)
        self.assertEqual([x["text"] for x in s], ["Yeah, it flies.", "But how?"])

    def test_pace_and_pause(self):
        s = prosody.sentences(self.W)
        self.assertAlmostEqual(s[0]["wps"], 3.0)
        self.assertAlmostEqual(s[0]["pause_after"], 0.5)
        self.assertIsNone(s[1]["pause_after"])

    def test_trailing_words_without_period_form_a_sentence(self):
        s = prosody.sentences([("follow", 0.0, 0.5), ("along", 0.5, 1.0)])
        self.assertEqual(len(s), 1)

    def test_empty(self):
        self.assertEqual(prosody.sentences([]), [])


class PitchTest(unittest.TestCase):
    def test_sine_pitch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.wav"
            write_wav(p, [(0.5, 220, 0.5)])
            samples, sr = prosody.read_wav(p)
            hz = prosody.pitch_hz(samples, sr, 0.1, 0.4)
            self.assertAlmostEqual(hz, 220, delta=220 * 0.03)

    def test_silence_has_no_pitch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.wav"
            write_wav(p, [(0.5, 0, 0)])
            samples, sr = prosody.read_wav(p)
            self.assertIsNone(prosody.pitch_hz(samples, sr, 0.1, 0.4))

    def test_rejects_stereo(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.wav"
            with wave.open(str(p), "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(b"\0\0\0\0" * 100)
            with self.assertRaises(ValueError):
                prosody.read_wav(p)


class ReportTest(unittest.TestCase):
    def _fixture(self, d):
        wav = Path(d) / "v.wav"
        # four words of 0.3 s; the third is louder and higher: the stressed one
        write_wav(wav, [(0.3, 150, 0.2), (0.3, 150, 0.2), (0.3, 300, 0.8), (0.3, 150, 0.2)])
        words = [("this", 0.0, 0.3), ("car", 0.3, 0.6), ("FLIES", 0.6, 0.9), ("today.", 0.9, 1.2)]
        return wav, words

    def test_stressed_word_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            wav, words = self._fixture(d)
            r = prosody.report(wav, words)
            self.assertEqual([e["word"] for e in r["emphasis"]], ["FLIES"])
            self.assertAlmostEqual(r["overall"]["wps"], 4 / 1.2, places=2)
            self.assertEqual(len(r["sentences"]), 1)
            self.assertGreater(r["overall"]["pitch_range_st"], 10)

    def test_cli_writes_json(self):
        with tempfile.TemporaryDirectory() as d:
            wav, words = self._fixture(d)
            wj = Path(d) / "w.json"
            wj.write_text(json.dumps([[w, s, e] for w, s, e in words]))
            out = Path(d) / "r.json"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vcli.main(["prosody", str(wav), str(wj), "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertIn("sentences", json.loads(out.read_text()))


class GateTest(unittest.TestCase):
    REP = {"overall": {"wps": 1.7, "pause_mean_s": 0.6, "pitch_range_st": 8.0}}

    def test_flat_slow_take_fails_every_threshold(self):
        p = prosody.gate(self.REP, min_range_st=10, min_wps=2.4, max_pause_s=0.35)
        self.assertEqual(len(p), 3)
        self.assertTrue(any("pitch range 8.0 st < 10" in x for x in p))

    def test_no_thresholds_no_problems(self):
        self.assertEqual(prosody.gate(self.REP), [])

    def test_unmeasured_value_fails_its_threshold(self):
        rep = {"overall": {"wps": None, "pause_mean_s": None, "pitch_range_st": None}}
        self.assertEqual(len(prosody.gate(rep, min_range_st=10, min_wps=2)), 2)

    def test_missing_pause_is_not_a_problem(self):
        rep = {"overall": {"wps": 3, "pause_mean_s": None, "pitch_range_st": 12}}
        self.assertEqual(prosody.gate(rep, max_pause_s=0.3), [])

    def test_cli_exit_1_on_flat_take(self):
        with tempfile.TemporaryDirectory() as d:
            wav, words = ReportTest()._fixture(d)
            wj = Path(d) / "w.json"
            wj.write_text(json.dumps([[w, s, e] for w, s, e in words]))
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = vcli.main(["prosody", str(wav), str(wj), "--min-range-st", "40"])
            self.assertEqual(rc, 1)
            self.assertIn("pitch range", err.getvalue())

    def test_cli_exit_0_when_take_passes(self):
        with tempfile.TemporaryDirectory() as d:
            wav, words = ReportTest()._fixture(d)
            wj = Path(d) / "w.json"
            wj.write_text(json.dumps([[w, s, e] for w, s, e in words]))
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vcli.main(["prosody", str(wav), str(wj), "--min-range-st", "10", "--min-wps", "3"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
