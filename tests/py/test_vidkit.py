import json
import tempfile
import unittest
from pathlib import Path

from tests.py.media import duration_of, make_clip, requires_ffmpeg
from tools.vidkit import ff, gates, join, loudness, patch, sheet, speech, synth, track


class PureLogicTest(unittest.TestCase):
    def test_clip_starts_overlap(self):
        self.assertEqual(join.clip_starts([8, 4, 4], [0.6, 0.4]), [0.0, 7.4, 11.0])
        self.assertAlmostEqual(join.total_length([8, 4, 4], [0.6, 0.4]), 15.0)

    def test_clip_starts_rejects_wrong_seam_count(self):
        with self.assertRaises(ValueError):
            join.clip_starts([8, 4], [0.5, 0.5])

    def test_words_from_alignment(self):
        al = {"characters": list("hi yo"),
              "character_start_times_seconds": [0, .1, .2, .3, .4],
              "character_end_times_seconds": [.1, .2, .3, .4, .5]}
        self.assertEqual(speech.words_from_alignment(al),
                         [{"word": "hi", "start": 0, "end": .2}, {"word": "yo", "start": .3, "end": .5}])

    def test_speech_spans_merge_and_gaps(self):
        layers = [{"at": 0.0, "words": [{"start": 1.0, "end": 2.0}]},
                  {"at": 2.0, "words": [{"start": 0.1, "end": 1.0}]},
                  {"at": 8.0, "words": [{"start": 0.0, "end": 1.0}]}]
        spans = speech.speech_spans(layers, pad=0.25)
        self.assertEqual(spans, [(0.75, 3.25), (7.75, 9.25)])
        self.assertEqual(speech.gaps(spans, 12.0, min_len=1.0), [(3.25, 7.75), (9.25, 12.0)])

    def test_snap_to_gaps_moves_only_cues_under_speech(self):
        spans = [(0.75, 3.25), (7.75, 9.25)]
        cues = [{"id": "hit", "at_s": 2.0}, {"id": "ok", "at_s": 5.0}, {"id": "bed", "at_s": 2.0}]
        moved, report = speech.snap_to_gaps(cues, spans, 12.0, window=2.0, keep=("bed",))
        by = {c["id"]: c for c in moved}
        self.assertEqual(by["hit"]["at_s"], 3.35)
        self.assertEqual(by["hit"]["at_s_orig"], 2.0)
        self.assertEqual(by["ok"]["at_s"], 5.0)
        self.assertEqual(by["bed"]["at_s"], 2.0)
        self.assertEqual(cues[0]["at_s"], 2.0)  # input untouched
        self.assertEqual(len(report), 1)

    def test_snap_leaves_cue_without_reachable_gap(self):
        moved, report = speech.snap_to_gaps([{"id": "x", "at_s": 2.0}], [(0.0, 12.0)], 12.0)
        self.assertEqual(moved[0]["at_s"], 2.0)
        self.assertEqual(report, [])

    def test_smooth_track_removes_angle_jitter_and_spike(self):
        pts = [{"t": i * .25, "x": 100.0, "y": 50.0, "w": 200.0, "h": 100.0, "deg": d}
               for i, d in enumerate([8, -6, 7, -5, 8, -6, 7, -5, 8])]
        pts[4]["x"] = 400.0  # one-frame spike
        out = track.smooth_track(pts, window=5)
        self.assertEqual({p["x"] for p in out}, {100.0})
        self.assertEqual(len({p["deg"] for p in out}), 1)

    def test_smooth_track_shrink_keeps_centre(self):
        out = track.smooth_track([{"t": 0, "x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0, "deg": 0}], shrink=0.9)
        self.assertEqual((out[0]["x"], out[0]["w"]), (5.0, 90.0))

    def test_smooth_track_rejects_even_window(self):
        with self.assertRaises(ValueError):
            track.smooth_track([], window=4)


@requires_ffmpeg
class MediaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def clip(self, name, **kw):
        return make_clip(self.dir / name, **kw)

    def test_probe(self):
        info = ff.probe(self.clip("a.mp4", seconds=1.0, fps=25))
        self.assertEqual((info["video"]["width"], info["video"]["height"]), (320, 240))
        self.assertAlmostEqual(info["video"]["fps"], 25.0)
        self.assertTrue(ff.has_audio(self.dir / "a.mp4"))

    def test_gate_av_passes_and_fails(self):
        gates.gate_av(self.clip("ok.mp4", seconds=1.5))
        with self.assertRaises(gates.GateError):
            gates.gate_av(self.clip("bad.mp4", seconds=2.0, audio_seconds=1.2))

    def test_gate_uniform_flags_mixed_rates(self):
        a = self.clip("a.mp4", seconds=1.0)
        b = self.dir / "b.mp4"
        ff.ffmpeg("-i", a, "-c:v", "copy", "-ar", "48000", "-ac", "2", b)
        with self.assertRaises(gates.GateError):
            gates.gate_uniform([a, b])
        gates.gate_uniform([a, a])

    def test_concat_copy_refuses_non_uniform(self):
        a = self.clip("a.mp4", seconds=1.0)
        b = self.dir / "b.mp4"
        ff.ffmpeg("-i", a, "-c:v", "copy", "-ar", "48000", "-ac", "2", b)
        with self.assertRaises(gates.GateError):
            join.concat_copy([a, b], self.dir / "o.mp4")

    def test_concat_copy_joins(self):
        a = self.clip("a.mp4", seconds=1.0)
        out = join.concat_copy([a, a], self.dir / "o.mp4")
        self.assertAlmostEqual(duration_of(out), 2.0, delta=0.15)

    def test_xfade_length_is_overlapped_and_av_matches(self):
        a = self.clip("a.mp4", seconds=2.0)
        b = self.clip("b.mp4", seconds=2.0)
        r = join.join_xfade([a, b], self.dir / "x.mp4", [0.5])
        self.assertAlmostEqual(r["length"], 3.5)
        self.assertAlmostEqual(duration_of(r["out"]), 3.5, delta=0.1)
        gates.gate_av(r["out"], tolerance=0.1)

    def test_xfade_zero_transition_is_clamped_not_broken(self):
        a = self.clip("a.mp4", seconds=2.0)
        r = join.join_xfade([a, a, a], self.dir / "x.mp4", [0.0, 0.5])
        self.assertAlmostEqual(duration_of(r["out"]), r["length"], delta=0.1)

    def test_freeze_box_keeps_duration_and_size(self):
        a = self.clip("a.mp4", seconds=1.0)
        out = patch.freeze_box(a, self.dir / "f.mp4", 10, 10, 60, 30, frame=0)
        self.assertAlmostEqual(duration_of(out), 1.0, delta=0.1)
        self.assertEqual(ff.probe(out)["video"]["width"], 320)

    def test_contact_sheet_and_montage(self):
        a = self.clip("a.mp4", seconds=2.0)
        s = sheet.contact_sheet(a, self.dir / "s.jpg", frames=4)
        self.assertTrue(Path(s).stat().st_size > 0)
        m = sheet.montage([s, s, s], self.dir / "m.jpg", cols=2, cell=(200, 100))
        self.assertTrue(Path(m).stat().st_size > 0)

    def test_synth_presets_are_audible_but_not_clipped(self):
        for name, length in (("notification", 0.6), ("alarm", 2.2)):
            out = getattr(synth, name)(self.dir / f"{name}.wav")
            peak, _ = synth.measure(out)
            self.assertLess(peak, -0.5, name)
            self.assertGreater(peak, -40.0, name)
            self.assertAlmostEqual(ff.duration(out), length, delta=0.05)

    def test_normalize_hits_target_and_keeps_av_aligned(self):
        a = self.clip("a.mp4", seconds=3.0)
        r = loudness.normalize(a, self.dir / "n.mp4", lufs=-14.0)
        self.assertAlmostEqual(r["after"]["I"], -14.0, delta=1.0)
        gates.gate_av(self.dir / "n.mp4")

    def test_energy_db_tracks_loud_vs_silent(self):
        wav = self.dir / "t.wav"
        ff.ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
                  "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-filter_complex",
                  "[0:a]aresample=16000[a];[1:a]atrim=0:0.5[s];[a][s]concat=n=2:v=0:a=1", wav)
        env = speech.energy_db(wav, 0, 1.0, hop=0.1)
        self.assertGreater(env[1][1], env[-2][1] + 30)


try:
    import cv2  # noqa: F401
    import numpy  # noqa: F401
    HAVE_CV = True
except ImportError:
    HAVE_CV = False


@requires_ffmpeg
@unittest.skipUnless(HAVE_CV, "cv2/numpy not importable (run with the tools/setup.sh venv)")
class BondTest(unittest.TestCase):
    def test_bond_print_writes_same_length_clip_and_changes_pixels(self):
        import cv2
        import numpy as np
        from tools.vidkit import bond
        tmp = Path(tempfile.mkdtemp())
        # flat light-grey "cloth" so the fabric mask accepts it
        src = tmp / "cloth.mp4"
        ff.ffmpeg("-f", "lavfi", "-i", "color=c=0xC8C8C8:s=270x480:r=12:d=1", "-c:v", "libx264",
                  "-pix_fmt", "yuv420p", src)
        png = tmp / "print.png"
        img = np.zeros((100, 400, 4), np.uint8)
        img[..., :3] = (20, 20, 20)
        img[..., 3] = 255
        cv2.imwrite(str(png), img)
        out = tmp / "out.mp4"
        r = bond.bond_print(src, out, png, cx=540, top=900, width=500, roi=(180, 800, 940, 1400))
        self.assertEqual(r["frames"], 12)
        self.assertAlmostEqual(duration_of(out), 1.0, delta=0.15)
        a, b = tmp / "a.png", tmp / "b.png"
        ff.ffmpeg("-i", out, "-vf", "select=eq(n\\,0),crop=300:60:390:900", "-frames:v", "1", a)
        ff.ffmpeg("-i", src, "-vf", "scale=1080:1920,select=eq(n\\,0),crop=300:60:390:900", "-frames:v", "1", b)
        diff = np.abs(cv2.imread(str(a)).astype(int) - cv2.imread(str(b)).astype(int)).mean()
        self.assertGreater(diff, 20, "print should darken the cloth where it lands")


if __name__ == "__main__":
    unittest.main()
