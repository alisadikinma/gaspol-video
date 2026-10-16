import contextlib
import io
import json
import math
import subprocess
import tempfile
import unittest
import wave
from array import array
from pathlib import Path

from tests.py.media import make_clip, requires_ffmpeg
from tools.vidkit import __main__ as cli
from tools.vidkit import audiostudy

RATE = 16000


def click_track(times, seconds, rate=RATE, width_ms=5):
    """Silence with a short alternating-sign burst at each time (a broadband transient)."""
    buf = array("h", [0] * int(seconds * rate))
    for t in times:
        start = int(t * rate)
        for i in range(int(rate * width_ms / 1000)):
            buf[start + i] = 20000 if i % 2 == 0 else -20000
    return buf


def write_wav(path, samples, rate=RATE):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return str(path)


class OnsetsTest(unittest.TestCase):
    def test_five_clicks_found_within_30ms(self):
        times = [0.5, 1.2, 2.0, 2.8, 3.5]
        found = audiostudy.onsets(click_track(times, 4.0), RATE)
        self.assertEqual(len(found), 5)
        for want, got in zip(times, found):
            self.assertAlmostEqual(got, want, delta=0.03)

    def test_silence_has_no_onsets(self):
        self.assertEqual(audiostudy.onsets(array("h", [0] * RATE), RATE), [])

    def test_tiny_buffer_has_no_onsets(self):
        self.assertEqual(audiostudy.onsets(click_track([0.0], 0.005), RATE), [])
        self.assertEqual(audiostudy.onsets(array("h"), RATE), [])

    def test_continuous_sine_has_no_onsets(self):
        sine = array("h", [int(12000 * math.sin(2 * math.pi * 440 * i / RATE)) for i in range(RATE * 2)])
        self.assertEqual(audiostudy.onsets(sine, RATE), [])

    def test_clicks_closer_than_min_gap_collapse(self):
        found = audiostudy.onsets(click_track([1.0, 1.03], 2.0), RATE)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0], 1.0, delta=0.03)


class TempoTest(unittest.TestCase):
    def test_120_bpm_click_train(self):
        bpm = audiostudy.tempo([0.5 * i for i in range(1, 13)])
        self.assertTrue(119 <= bpm <= 121, bpm)

    def test_too_few_onsets_gives_none(self):
        self.assertIsNone(audiostudy.tempo([0.1, 0.9]))
        self.assertIsNone(audiostudy.tempo([]))

    def test_slow_pulse_folds_into_range(self):
        bpm = audiostudy.tempo([1.5 * i for i in range(1, 9)])  # 40 BPM folds to 80
        self.assertTrue(79 <= bpm <= 81, bpm)


class RelateTest(unittest.TestCase):
    def test_labels(self):
        words, cuts = [1.0, 3.0], [2.0, 3.0]
        rows = audiostudy.relate([1.02, 2.01, 3.0, 4.5], words, cuts)
        self.assertEqual([r["label"] for r in rows], ["on-word", "on-cut", "both", "free"])
        self.assertAlmostEqual(rows[0]["d_word"], -0.02, places=3)
        self.assertEqual(rows[1]["nearest_cut"], 2.0)

    def test_empty_words_and_cuts_give_none_distances(self):
        row = audiostudy.relate([1.0], [], [])[0]
        self.assertIsNone(row["d_word"])
        self.assertIsNone(row["nearest_word_start"])
        self.assertIsNone(row["d_cut"])
        self.assertEqual(row["label"], "free")


@requires_ffmpeg
class MediaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_decode_mono_reads_clicks_from_a_wav(self):
        wav = write_wav(self.dir / "c.wav", click_track([0.5], 1.0))
        samples = audiostudy.decode_mono(wav)
        self.assertEqual(len(samples), RATE)
        self.assertGreater(max(samples), 10000)

    def test_decode_mono_without_audio_stream_raises(self):
        clip = make_clip(self.dir / "mute.mp4", 1.0, audio=False)
        with self.assertRaisesRegex(ValueError, "no audio stream"):
            audiostudy.decode_mono(clip)

    def test_energy_profile_keeps_tail_of_one_second(self):
        clip = make_clip(self.dir / "five.mp4", 5.0)
        prof = audiostudy.energy_profile(clip, seg_s=2.0)
        self.assertEqual(len(prof), 3)
        self.assertAlmostEqual(prof[-1]["end"] - prof[-1]["start"], 1.0, delta=0.1)
        self.assertTrue(all(p["dbfs"] < 0 for p in prof))

    def test_energy_profile_drops_tail_under_half_a_second(self):
        for secs in (4.2, 4.3):
            clip = make_clip(self.dir / f"c{secs}.mp4", secs)
            self.assertEqual(len(audiostudy.energy_profile(clip, seg_s=2.0)), 2, secs)

    def lavfi_audio(self, name, source):
        out = self.dir / name
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", source,
                        "-t", "1", str(out)], check=True)
        return out

    def test_study_audio_only_file_has_no_cuts(self):
        clip = self.lavfi_audio("tone.wav", "sine=frequency=440:duration=1")
        rep = audiostudy.study(clip)
        self.assertEqual(rep["cuts"], [])
        self.assertAlmostEqual(rep["duration"], 1.0, delta=0.2)

    def test_study_silent_clip_stores_null_loudness_and_valid_json(self):
        clip = self.lavfi_audio("silence.wav", "anullsrc=r=16000:cl=mono")
        rep = audiostudy.study(clip)
        self.assertIsNone(rep["loudness_lufs"])
        self.assertNotIn("Infinity", json.dumps(rep, allow_nan=False))

    def test_study_returns_every_key_and_serializes(self):
        clip = make_clip(self.dir / "s.mp4", 2.0)
        rep = audiostudy.study(clip, words=[["ok", 0.5, 0.8]])
        for key in ("clip", "duration", "loudness_lufs", "cuts", "onsets", "tempo_bpm", "energy", "relations"):
            self.assertIn(key, rep)
        self.assertAlmostEqual(rep["duration"], 2.0, delta=0.2)
        self.assertEqual(json.loads(json.dumps(rep)), rep)


@requires_ffmpeg
class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["audiostudy", *map(str, args)])
        return code, out.getvalue(), err.getvalue()

    def test_writes_json_and_prints_one_line(self):
        clip = make_clip(self.dir / "a.mp4", 2.0)
        words = self.dir / "w.json"
        words.write_text(json.dumps([["halo", 0.2, 0.6]]))
        report = self.dir / "r.json"
        code, out, _ = self.run_cli(clip, "--words", words, "--out", report)
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertEqual(json.loads(report.read_text())["clip"], str(clip))

    def test_silent_clip_prints_silent(self):
        clip = self.dir / "silence.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "anullsrc=r=16000:cl=mono", "-t", "1", str(clip)], check=True)
        code, out, _ = self.run_cli(clip)
        self.assertEqual(code, 0)
        self.assertIn("silent", out)

    def test_missing_file_fails_with_one_line(self):
        code, _, err = self.run_cli(self.dir / "nope.mp4")
        self.assertNotEqual(code, 0)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
