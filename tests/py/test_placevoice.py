import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.py.media import requires_ffmpeg
from tests.py.test_prosody import write_wav
from tools.vidkit import __main__ as vcli
from tools.vidkit import ff, placevoice


class GapsTest(unittest.TestCase):
    def test_gaps_outside_speech(self):
        words = [("a", 0.5, 1.0), ("b", 1.1, 1.6), ("c", 2.6, 3.0)]
        self.assertEqual(placevoice.ambience_gaps(words, 4.0, min_gap=0.3, pad=0.05),
                         [(0.0, 0.45), (1.65, 2.55), (3.05, 4.0)])

    def test_no_gap_long_enough(self):
        self.assertEqual(placevoice.ambience_gaps([("a", 0.1, 3.95)], 4.0, min_gap=0.3), [])

    def test_quiet_runs_skip_loud_frames(self):
        env = [(i / 100, -40.0) for i in range(100)] + [(1 + i / 100, -12.0) for i in range(50)] \
            + [(1.5 + i / 100, -38.0) for i in range(60)]
        runs = placevoice.quiet_runs(env, max_db=-25, min_len=0.3)
        self.assertEqual(len(runs), 2)
        self.assertAlmostEqual(runs[0][1], 1.0, places=2)
        self.assertAlmostEqual(runs[1][0], 1.5, places=2)

    def test_single_frame_spikes_do_not_break_a_quiet_run(self):
        env = [(i / 100, -24.0 if i % 9 == 0 else -32.0) for i in range(60)]  # real ambience flickers
        self.assertEqual(placevoice.quiet_runs(env, max_db=-26, min_len=0.3), [(0.0, 0.6)])
        self.assertEqual(placevoice.quiet_runs(env, max_db=-26, min_len=0.3, smooth=1), [])

    def test_intersect(self):
        self.assertEqual(placevoice.intersect([(0, 2), (3, 5)], [(1, 4)], 0.3), [(1, 2), (3, 4)])

    def test_unknown_space_rejected(self):
        with self.assertRaises(ValueError):
            placevoice.voice_chain("cave")


class PlaceTest(unittest.TestCase):
    def _fixture(self, d):
        clip, voice = Path(d) / "c.mp4", Path(d) / "v.wav"
        bed = Path(d) / "bed.wav"
        # original clip audio: ambience tone, a loud "speech" burst 1-2 s, ambience again
        write_wav(bed, [(1.0, 80, 0.05), (1.0, 300, 0.6), (2.0, 80, 0.05)])
        ff.ffmpeg("-f", "lavfi", "-i", "color=c=black:s=64x64:d=4", "-i", str(bed),
                  "-shortest", "-c:v", "libx264", "-c:a", "aac", str(clip))
        write_wav(voice, [(1.0, 0, 0), (1.0, 220, 0.2), (2.0, 0, 0)])  # dry, quieter replacement
        return clip, voice, [("udara", 1.0, 2.0)]

    @requires_ffmpeg
    def test_output_keeps_length_and_matches_level(self):
        with tempfile.TemporaryDirectory() as d:
            clip, voice, words = self._fixture(d)
            out = Path(d) / "o.mp4"
            r = placevoice.place(str(clip), str(voice), words, str(out), bed="gaps")
            p = ff.probe(str(out))
            self.assertAlmostEqual(p["audio"]["duration"], p["video"]["duration"], delta=0.05)
            self.assertGreater(r["gain_db"], 3)            # replacement was quieter, brought up
            self.assertGreater(r["bed_s"], 2.5)             # ambience taken from the gaps

    @requires_ffmpeg
    def test_speech_level_matches_original_after_the_chain(self):
        # the space chain (echo gains, compression) changes level; matching must happen after it
        with tempfile.TemporaryDirectory() as d:
            clip, voice, words = self._fixture(d)
            for space in placevoice.SPACES:
                out = Path(d) / f"o-{space}.mp4"
                placevoice.place(str(clip), str(voice), words, str(out), space=space)
                got, want = placevoice._rms_db(str(out), 1.0, 2.0), placevoice._rms_db(str(clip), 1.0, 2.0)
                self.assertAlmostEqual(got, want, delta=1.0, msg=space)

    @requires_ffmpeg
    def test_non_word_vocal_in_a_gap_is_kept_out_of_the_bed(self):
        # a laugh after the word: loud, but no ASR word covers it
        with tempfile.TemporaryDirectory() as d:
            clip, voice = Path(d) / "c.mp4", Path(d) / "v.wav"
            bed = Path(d) / "bed.wav"
            write_wav(bed, [(1.0, 80, 0.05), (1.0, 300, 0.6), (1.5, 250, 0.5), (0.5, 80, 0.05)])
            ff.ffmpeg("-f", "lavfi", "-i", "color=c=black:s=64x64:d=4", "-i", str(bed),
                      "-shortest", "-c:v", "libx264", "-c:a", "aac", str(clip))
            write_wav(voice, [(1.0, 0, 0), (1.0, 220, 0.2), (2.0, 0, 0)])
            r = placevoice.place(str(clip), str(voice), [("udara", 1.0, 2.0)], str(Path(d) / "o.mp4"),
                                 bed="gaps")
            self.assertLess(r["bed_s"], 1.6)  # 0-0.95 and 3.5-4.0 only, not the 2-3.5 laugh

    @requires_ffmpeg
    def test_stems_bed_covers_the_whole_clip(self):
        # a separated background stem is the scene's own air, full length: nothing is looped
        with tempfile.TemporaryDirectory() as d:
            clip, voice, words = self._fixture(d)
            bg = Path(d) / "bg.wav"
            write_wav(bg, [(4.0, 80, 0.05)])
            calls = []

            def sep(c, work):
                calls.append(c)
                return str(bg)

            out = Path(d) / "o.mp4"
            r = placevoice.place(str(clip), str(voice), words, str(out), bed="stems", separator=sep)
            self.assertEqual(calls, [str(clip)])
            self.assertEqual(r["bed"], "stems")
            self.assertAlmostEqual(r["bed_s"], 4.0, delta=0.05)
            got, want = placevoice._rms_db(str(out), 1.0, 2.0), placevoice._rms_db(str(clip), 1.0, 2.0)
            self.assertAlmostEqual(got, want, delta=1.0)

    @requires_ffmpeg
    def test_default_bed_is_gaps_even_with_demucs_installed(self):
        # stems sounded worse by ear in the field; it must never switch on by itself
        with tempfile.TemporaryDirectory() as d:
            clip, voice, words = self._fixture(d)
            orig = placevoice.shutil.which
            placevoice.shutil.which = lambda name: "/usr/bin/" + name
            try:
                r = placevoice.place(str(clip), str(voice), words, str(Path(d) / "o.mp4"),
                                     separator=lambda c, w: self.fail("separator called"))
            finally:
                placevoice.shutil.which = orig
            self.assertEqual(r["bed"], "gaps")

    def test_stems_without_demucs_is_an_error(self):
        orig = placevoice.shutil.which
        placevoice.shutil.which = lambda name: None
        try:
            with self.assertRaises(ff.FFMissing):
                placevoice.separate("c.mp4", "work")
        finally:
            placevoice.shutil.which = orig

    @requires_ffmpeg
    @unittest.skipUnless(placevoice.shutil.which("demucs"), "demucs not installed")
    def test_real_demucs_split_gives_a_full_length_background(self):
        with tempfile.TemporaryDirectory() as d:
            clip, _, _ = self._fixture(d)
            bg = placevoice.separate(str(clip), Path(d) / "work")
            self.assertAlmostEqual(ff.probe(bg)["duration"], 4.0, delta=0.1)

    def test_unknown_bed_rejected(self):
        with self.assertRaises(ValueError):
            placevoice.place("c.mp4", "v.wav", [("a", 0, 1)], "o.mp4", bed="noise")

    @requires_ffmpeg
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            clip, voice, words = self._fixture(d)
            wj = Path(d) / "w.json"
            wj.write_text(json.dumps([[w, s, e] for w, s, e in words]))
            out = Path(d) / "o.mp4"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vcli.main(["placevoice", str(clip), str(voice), str(wj), str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
