import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from tools import mix_sfx


def write_wav(path, samples, rate=48000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples))
    return str(path)


def tone(seconds, freq=220.0, amp=0.3, rate=48000):
    return [amp * math.sin(2 * math.pi * freq * i / rate) for i in range(int(seconds * rate))]


def silence(seconds, rate=48000):
    return [0.0] * int(seconds * rate)


def click(at_s, total_s, width_s=0.05, amp=0.9, rate=48000):
    """A short transient inside otherwise silent audio."""
    out = [0.0] * int(total_s * rate)
    start = int(at_s * rate)
    for i in range(int(width_s * rate)):
        if start + i < len(out):
            out[start + i] = amp * math.sin(2 * math.pi * 2000 * i / rate)
    return out


class RmsWindowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rms_window_sizes(self):
        """A 50ms click must be measured in a tight window.

        Over 0.6s the same transient is diluted into nothing, which is how an inaudible
        cue passes a cue sheet review while being inaudible in the video.
        """
        path = write_wav(self.dir / "clicky.wav", click(1.0, 3.0))
        tight = mix_sfx.rms_dbfs(path, at_s=1.0, window_s=0.3)
        wide = mix_sfx.rms_dbfs(path, at_s=1.0, window_s=0.6)
        self.assertGreater(tight, wide + 2.0,
                           f"a 0.6s window must dilute the click: tight={tight:.1f} wide={wide:.1f}")
        self.assertEqual(mix_sfx.window_for("pop-reveal"), mix_sfx.TRANSIENT_WINDOW_S)
        self.assertEqual(mix_sfx.window_for("amb-factory-floor"), mix_sfx.SUSTAINED_WINDOW_S)

    def test_riser_is_measured_at_its_final_third(self):
        rate = 48000
        ramp = [(i / (2.0 * rate)) * 0.9 * math.sin(2 * math.pi * 300 * i / rate)
                for i in range(int(2.0 * rate))]
        path = write_wav(self.dir / "riser.wav", silence(1.0) + ramp)
        start = mix_sfx.rms_dbfs(path, at_s=1.1, window_s=0.3)
        end = mix_sfx.measure_cue(path, at_s=1.0, sfx_id="riser-short", duration_s=2.0)
        self.assertGreater(end, start,
                           "a riser measured at its start reads quiet; its energy is at the end")

    def test_audibility_delta_flags_an_inaudible_cue(self):
        # The voice sits well below the cue so the assertion tests the MECHANISM rather
        # than sitting on the +4 dB threshold, where a fixture passes or fails on rounding.
        voice = write_wav(self.dir / "voice.wav", tone(3.0, amp=0.15))
        mixed_loud = write_wav(self.dir / "loud.wav",
                               [a + b for a, b in zip(tone(3.0, amp=0.15), click(1.0, 3.0, amp=0.9))])
        mixed_quiet = write_wav(self.dir / "quiet.wav",
                                [a + b for a, b in zip(tone(3.0, amp=0.15), click(1.0, 3.0, amp=0.005))])

        loud = mix_sfx.audibility_delta(voice, mixed_loud, at_s=1.0, sfx_id="pop-reveal")
        quiet = mix_sfx.audibility_delta(voice, mixed_quiet, at_s=1.0, sfx_id="pop-reveal")

        self.assertGreaterEqual(loud, mix_sfx.STORY_CRITICAL_DB)
        self.assertLess(quiet, mix_sfx.TEXTURE_MIN_DB)


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        catalog = self.project / "catalog.json"
        catalog.write_text(json.dumps({"clips": [
            {"id": "pop-reveal", "file": "clips/pop-reveal.mp3", "duration_s": 0.4,
             "category": "emphasis", "loudness_lufs": -20.0},
            {"id": "amb-factory-floor", "file": "clips/amb-factory-floor.mp3", "duration_s": 12.0,
             "category": "ambience", "loudness_lufs": -20.0},
        ]}))
        self.catalog = catalog

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, events, **extra):
        data = {"master": "output/master.mp4", "catalog": str(self.catalog),
                "render": {"out": "output/master-mixed.mp4", "duck": True},
                "events": events}
        data.update(extra)
        path = self.project / "work" / "sfx-plan.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    def test_empty_event_list_is_allowed_and_says_so(self):
        plan = mix_sfx.load_plan(self._plan([]), self.project, master_duration_s=30.0)
        self.assertEqual(plan.events, [])
        self.assertTrue(any("no cues" in n.lower() for n in plan.notes))

    def test_two_cues_at_the_same_time_layer_rather_than_replace(self):
        plan = mix_sfx.load_plan(self._plan([
            {"at_s": 4.0, "sfx_id": "pop-reveal", "gain_db": 0},
            {"at_s": 4.0, "sfx_id": "amb-factory-floor", "gain_db": -16},
        ]), self.project, master_duration_s=30.0)
        self.assertEqual(len(plan.events), 2, "a layered pair must survive as two events")

    def test_cue_past_the_master_is_rejected(self):
        with self.assertRaises(mix_sfx.PlanError) as ctx:
            mix_sfx.load_plan(self._plan([
                {"at_s": 44.0, "sfx_id": "pop-reveal", "gain_db": 0},
            ]), self.project, master_duration_s=30.0)
        self.assertIn("44.0", str(ctx.exception))

    def test_unknown_sfx_id_is_rejected_with_the_id(self):
        with self.assertRaises(mix_sfx.PlanError) as ctx:
            mix_sfx.load_plan(self._plan([
                {"at_s": 1.0, "sfx_id": "whoosh-that-does-not-exist", "gain_db": 0},
            ]), self.project, master_duration_s=30.0)
        self.assertIn("whoosh-that-does-not-exist", str(ctx.exception))

    def test_no_optional_drops_only_optional_cues(self):
        plan = mix_sfx.load_plan(self._plan([
            {"at_s": 1.0, "sfx_id": "pop-reveal", "gain_db": 0},
            {"at_s": 2.0, "sfx_id": "pop-reveal", "gain_db": -6, "optional": True},
        ]), self.project, master_duration_s=30.0, include_optional=False)
        self.assertEqual(len(plan.events), 1)
        self.assertEqual(plan.events[0]["at_s"], 1.0)

    def test_density_over_the_ceiling_is_a_note_not_a_failure(self):
        events = [{"at_s": i * 0.5, "sfx_id": "pop-reveal", "gain_db": 0} for i in range(30)]
        plan = mix_sfx.load_plan(self._plan(events), self.project, master_duration_s=60.0)
        self.assertTrue(any("density" in n.lower() for n in plan.notes))

    def test_sheet_is_readable_and_names_every_cue(self):
        plan = mix_sfx.load_plan(self._plan([
            {"at_s": 12.4, "sfx_id": "amb-factory-floor", "gain_db": -16,
             "cue": "wide shot of production line"},
        ]), self.project, master_duration_s=30.0)
        sheet = mix_sfx.format_sheet(plan)
        self.assertIn("amb-factory-floor", sheet)
        self.assertIn("12.40", sheet)
        self.assertIn("production line", sheet)


if __name__ == "__main__":
    unittest.main()
