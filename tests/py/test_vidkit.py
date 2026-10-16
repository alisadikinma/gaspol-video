import hashlib
import io
import json
import random
import struct
import tempfile
import unittest
from pathlib import Path

from tests.py.media import duration_of, make_clip, requires_ffmpeg
from tools.vidkit import beats, color, colormatch, cover, ff, gates, ingest, join, karaoke, mixdown, unwhite, loudness, patch, sheet, speech, synth, track


class IngestTest(unittest.TestCase):
    def test_scenes_cover_whole_video(self):
        sc = ingest.scenes_from_cuts([2.0, 5.0], 8.0)
        self.assertEqual(sc, [(0.0, 2.0), (2.0, 5.0), (5.0, 8.0)])

    def test_flash_cuts_are_dropped(self):
        sc = ingest.scenes_from_cuts([2.0, 2.2, 7.9], 8.0, min_len=0.6)
        self.assertEqual(sc, [(0.0, 2.0), (2.0, 8.0)])

    def test_no_cuts_is_one_scene(self):
        self.assertEqual(ingest.scenes_from_cuts([], 5.0), [(0.0, 5.0)])

    def test_rejects_zero_duration(self):
        with self.assertRaises(ValueError):
            ingest.scenes_from_cuts([], 0)

    @requires_ffmpeg
    def test_split_writes_clips_stills_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, v = Path(d) / "a.mp4", Path(d) / "b.mp4", Path(d) / "v.mp4"
            make_clip(str(a), 2.0)
            ff.ffmpeg("-i", a, "-vf", "negate", "-c:a", "copy", b)  # a hard visual cut
            ff.ffmpeg("-i", a, "-i", b, "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", v)
            rows = ingest.split_scenes(str(v), str(Path(d) / "out"), threshold=0.2)
            self.assertEqual(len(rows), 2)
            self.assertTrue((Path(d) / "out" / "scene-01-mid.png").exists())
            self.assertTrue((Path(d) / "out" / "scenes.json").exists())


class KaraokeTest(unittest.TestCase):
    W = [("Stop", 0.0, 0.4), ("bayar", 0.4, 0.8), ("langganan.", 0.9, 1.5), ("Bongkar", 1.6, 2.0)]

    def test_groups_close_at_sentence_end(self):
        g = karaoke.group_words(self.W)
        self.assertEqual([[w[0] for w in x] for x in g], [["Stop", "bayar"], ["langganan."], ["Bongkar"]])

    def test_c_sharp_is_merged(self):
        m = karaoke.merge_sharp([("C", 0, .2), ("Sharp", .2, .5)])
        self.assertEqual(m, [("C#", 0, .5)])

    def test_ass_has_karaoke_tags_and_watermark(self):
        ass = karaoke.build_ass(self.W, 3.0, watermark="@x", watermark_opacity=0.12)
        self.assertIn("\\kf", ass)
        self.assertIn("@x", ass)
        self.assertIn("\\1a&HE0&", ass)  # 88% transparent = 0xE0

    def test_no_watermark_when_none(self):
        self.assertNotIn("\\an5", karaoke.build_ass(self.W, 3.0))

    def test_bad_opacity_is_refused(self):
        with self.assertRaises(ValueError):
            karaoke.watermark_event("x", 3.0, opacity=0)


class CoverUnwhiteTest(unittest.TestCase):
    @requires_ffmpeg
    def test_cover_attaches_picture_and_keeps_length(self):
        with tempfile.TemporaryDirectory() as d:
            v, th, o = Path(d) / "v.mp4", Path(d) / "t.png", Path(d) / "o.mp4"
            make_clip(str(v), 2.0)
            ff.ffmpeg("-f", "lavfi", "-i", "color=c=red:s=320x240", "-frames:v", 1, th)
            cover.apply(str(v), str(th), str(o), hold_s=0.2, width=320, height=240)
            self.assertAlmostEqual(duration_of(str(o)), 2.0, delta=0.1)
            kinds = ff.run(["ffprobe", "-v", "error", "-show_entries", "stream_disposition=attached_pic", "-of", "csv=p=0", o])
            self.assertIn("1", kinds)

    def test_cover_refuses_zero_hold(self):
        with self.assertRaises(ValueError):
            cover.apply("a", "b", "c", hold_s=0)

    @requires_ffmpeg
    def test_unwhite_makes_white_transparent(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "l.png", Path(d) / "o.png"
            ff.ffmpeg("-f", "lavfi", "-i", "color=c=white:s=40x40", "-frames:v", 1, src)
            unwhite.unwhite(str(src), str(out))
            err = ff.run(["ffmpeg", "-v", "info", "-i", out, "-vf", "alphaextract,signalstats,metadata=print", "-f", "null", "-"],
                         capture_stderr=True)
            import re
            yavg = float(re.findall(r"YAVG=([\d.]+)", err)[0])
            self.assertLess(yavg, 10)  # all-white input -> almost fully transparent


class MixdownTest(unittest.TestCase):
    def test_missing_sfx_names_the_path_it_tried(self):
        with self.assertRaises(FileNotFoundError):
            mixdown.sfx_path("no-such-clip-xyz")

    def test_music_shorter_than_fades_is_refused(self):
        with self.assertRaises(ValueError):
            mixdown.build_music({"file": "x", "start": 9.0, "fade_in": 1.5, "fade_out": 1.5}, 10.0, "o.wav")

    @requires_ffmpeg
    def test_full_mix_hits_target_loudness_and_keeps_length(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            v, o, sfx, mus = d / "v.mp4", d / "o.mp4", d / "s.wav", d / "m.wav"
            make_clip(str(v), 4.0)
            ff.ffmpeg("-f", "lavfi", "-i", "sine=f=880:d=0.3", sfx)
            ff.ffmpeg("-f", "lavfi", "-i", "sine=f=220:d=2", mus)
            r = mixdown.run({"video": str(v), "out": str(o), "cues": [{"at": 1.0, "sfx": str(sfx), "gain": 0.8}],
                             "music": {"file": str(mus), "start": 0.5, "gain": 0.4, "fade_in": 0.5, "fade_out": 0.5}},
                            workdir=d / "w")
            self.assertAlmostEqual(duration_of(str(o)), 4.0, delta=0.15)
            self.assertAlmostEqual(mixdown.measure_lufs(str(d / "w" / "mix.wav")), -14.0, delta=1.0)

    @requires_ffmpeg
    def test_final_mux_is_tagged_bt709_with_and_without_subtitles(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            v = d / "v.mp4"
            make_clip(str(v), 1.5)
            ass = d / "s.ass"
            ass.write_text("[Script Info]\nScriptType: v4.00+\nPlayResX: 320\nPlayResY: 240\n"
                           "[V4+ Styles]\nFormat: Name, Fontname, Fontsize\nStyle: Default,Arial,20\n"
                           "[Events]\nFormat: Layer, Start, End, Style, Text\n"
                           "Dialogue: 0,0:00:00.00,0:00:01.00,Default,hi\n")
            for name, extra in (("plain", {}), ("subs", {"ass": str(ass)})):
                o = d / f"{name}.mp4"
                mixdown.run({"video": str(v), "out": str(o), **extra}, workdir=d / f"w-{name}")
                p = color.probe_color(str(o))
                self.assertEqual((p["color_space"], p["color_primaries"], p["color_transfer"]),
                                 ("bt709", "bt709", "bt709"), name)


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


def click_wav(path, clicks, seconds=6.0, rate=16000, channels=1, noise=0.003, amp=0.9):
    """Write a wav of short decaying clicks at ``clicks`` seconds over low noise."""
    import math
    import wave
    rnd = random.Random(7)
    n = int(seconds * rate)
    data = [rnd.uniform(-noise, noise) for _ in range(n)]
    for t in clicks:
        i0 = int(t * rate)
        for k in range(int(0.02 * rate)):
            if i0 + k < n:
                data[i0 + k] += amp * math.exp(-k / (0.004 * rate)) * math.sin(2 * math.pi * 900 * k / rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate)
        frames = bytearray()
        for v in data:
            frames += struct.pack("<h", int(max(-1, min(1, v)) * 32767)) * channels
        w.writeframes(bytes(frames))
    return str(path)


@requires_ffmpeg
class BeatsTest(unittest.TestCase):
    CLICKS = [0.5, 1.5, 2.5, 3.5, 4.5]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_five_clicks(self):
        wav = click_wav(self.dir / "c.wav", self.CLICKS)
        found = beats.detect(wav)
        self.assertEqual(len(found), 5, found)
        for got, want in zip(found, self.CLICKS):
            self.assertAlmostEqual(got, want, delta=0.03)

    def test_silence_has_no_beats(self):
        wav = click_wav(self.dir / "s.wav", [], noise=0.0)
        self.assertEqual(beats.detect(wav), [])

    def test_low_noise_only_has_no_beats(self):
        wav = click_wav(self.dir / "n.wav", [])
        self.assertEqual(beats.detect(wav), [])

    def test_missing_file_raises(self):
        with self.assertRaises(beats.BeatError):
            beats.detect(str(self.dir / "nope.wav"))

    def test_undecodable_file_raises(self):
        bad = self.dir / "bad.wav"
        bad.write_bytes(b"not audio at all")
        with self.assertRaises(beats.BeatError):
            beats.detect(str(bad))

    def test_clicks_closer_than_min_gap_collapse(self):
        wav = click_wav(self.dir / "g.wav", [1.0, 1.1, 3.0])
        found = beats.detect(wav, min_gap_s=0.25)
        self.assertEqual(len(found), 2, found)
        self.assertAlmostEqual(found[1], 3.0, delta=0.03)
        self.assertEqual(len(beats.detect(wav, min_gap_s=0.05)), 3)

    def test_single_beat(self):
        wav = click_wav(self.dir / "one.wav", [2.0])
        found = beats.detect(wav)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0], 2.0, delta=0.03)

    def test_stereo_44k_input_still_works(self):
        wav = click_wav(self.dir / "st.wav", self.CLICKS, rate=44100, channels=2)
        found = beats.detect(wav)
        self.assertEqual(len(found), 5, found)
        for got, want in zip(found, self.CLICKS):
            self.assertAlmostEqual(got, want, delta=0.03)

    def test_snap_moves_inside_window_only(self):
        self.assertEqual(beats.snap([1.54, 1.9], [1.5, 2.5], 0.12), [1.5, 1.9])

    def test_snap_picks_nearest_beat(self):
        self.assertEqual(beats.snap([1.58], [1.5, 1.62], 0.12), [1.62])

    def test_snap_window_zero_moves_nothing(self):
        self.assertEqual(beats.snap([1.54, 1.5], [1.5], 0), [1.54, 1.5])

    def test_snap_before_first_and_after_last_beat(self):
        self.assertEqual(beats.snap([0.05, 9.0, 0.45], [0.5, 4.0], 0.12), [0.05, 9.0, 0.5])

    def test_snap_with_no_beats_changes_nothing(self):
        self.assertEqual(beats.snap([1.0, 2.0], [], 0.12), [1.0, 2.0])

    def test_cli_prints_json_times(self):
        import io
        from contextlib import redirect_stdout
        from tools.vidkit.__main__ import main
        wav = click_wav(self.dir / "cli.wav", self.CLICKS)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["beats", wav])
        self.assertEqual(rc, 0)
        got = json.loads(buf.getvalue())
        self.assertEqual(len(got), 5)

    def test_cli_missing_file_fails(self):
        from tools.vidkit.__main__ import main
        self.assertEqual(main(["beats", str(self.dir / "nope.wav")]), 1)


if __name__ == "__main__":
    unittest.main()


class ColorTest(unittest.TestCase):
    def _encode(self, d, extra_in=(), name="o.mp4"):
        out = Path(d) / name
        ff.ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1", *extra_in,
                  "-vf", color.TAG_FILTER, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                  *color.ENCODE_FLAGS, "-an", out)
        return str(out)

    @requires_ffmpeg
    def test_encode_flags_tag_stream_as_bt709(self):
        with tempfile.TemporaryDirectory() as d:
            p = color.probe_color(self._encode(d))
            self.assertEqual(p["color_space"], "bt709")
            self.assertEqual(p["color_primaries"], "bt709")
            self.assertEqual(p["color_transfer"], "bt709")
            self.assertEqual(p["color_range"], "tv")

    def test_encode_flags_and_tag_filter_are_pinned(self):
        self.assertEqual(color.ENCODE_FLAGS, ["-colorspace", "bt709", "-color_primaries", "bt709",
                                              "-color_trc", "bt709", "-color_range", "tv"])
        self.assertEqual(color.TAG_FILTER, "setparams=colorspace=bt709:color_primaries=bt709:"
                                           "color_trc=bt709:range=tv")

    @requires_ffmpeg
    def test_probe_without_video_stream_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "a.wav"
            ff.ffmpeg("-f", "lavfi", "-i", "sine=f=440:d=0.2", wav)
            with self.assertRaises(ff.FFError) as cm:
                color.probe_color(str(wav))
            self.assertIn("no video stream", str(cm.exception))

    def _p(self, space="unknown", prim="unknown", trc="unknown"):
        return {"color_space": space, "color_primaries": prim, "color_transfer": trc,
                "color_range": "tv"}

    def test_bt709_needs_no_conversion(self):
        self.assertEqual(color.convert_filter(self._p("bt709", "bt709", "bt709")), "")

    def test_untagged_is_assumed_bt709(self):
        w = []
        self.assertEqual(color.convert_filter(self._p(), w), "")
        self.assertEqual(w, [])

    def test_explicit_bt601_is_converted(self):
        self.assertEqual(color.convert_filter(self._p("smpte170m", "smpte170m", "smpte170m")),
                         "colorspace=all=bt709:iall=bt601-6-525")
        self.assertEqual(color.convert_filter(self._p("bt470bg", "bt470bg", "bt470bg")),
                         "colorspace=all=bt709:iall=bt601-6-625")

    def test_unknown_value_is_not_converted_and_warns(self):
        w = []
        self.assertEqual(color.convert_filter(self._p("ycgco"), w, "clip.mp4"), "")
        self.assertEqual(len(w), 1)
        self.assertIn("clip.mp4", w[0])
        self.assertIn("ycgco", w[0])

    def test_hdr_transfer_is_left_alone_with_warning(self):
        for trc in ("smpte2084", "arib-std-b67"):
            w = []
            self.assertEqual(color.convert_filter(self._p("bt2020nc", "bt2020", trc), w, "h.mp4"), "")
            self.assertEqual(len(w), 1)
            self.assertIn(trc, w[0])


def _solid(path, rgb, seconds=1.0, size="64x48", audio=True):
    """A solid-colour clip, real ffmpeg. rgb is a 0-255 triple."""
    import subprocess
    hexc = "0x%02x%02x%02x" % tuple(rgb)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={hexc}:s={size}:r=10:d={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv444p", "-crf", "0", "-t", str(seconds)]
    cmd += ["-c:a", "aac"] if audio else ["-an"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, capture_output=True)
    return str(path)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@requires_ffmpeg
class ColorMatchTest(unittest.TestCase):
    GREY, WARM, COOL = (120, 120, 120), (135, 120, 105), (105, 120, 135)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def trio(self):
        return [_solid(self.d / f"{n}.mp4", c)
                for n, c in (("grey", self.GREY), ("warm", self.WARM), ("cool", self.COOL))]

    def test_mean_rgb_matches_generated_colour(self):
        for name, rgb in (("grey", self.GREY), ("warm", self.WARM), ("cool", self.COOL)):
            got = colormatch.mean_rgb(_solid(self.d / f"{name}.mp4", rgb))
            for g, w in zip(got, rgb):
                self.assertAlmostEqual(g, w, delta=2, msg=f"{name} {got}")

    def test_plan_moves_warm_and_cool_toward_median(self):
        rows = {Path(r["file"]).stem: r for r in colormatch.plan(self.trio())}
        gr, gg, gb = rows["warm"]["gain"]
        self.assertLess(gr, 1.0)
        self.assertGreater(gb, 1.0)
        cr, cg, cb = rows["cool"]["gain"]
        self.assertGreater(cr, 1.0)
        self.assertLess(cb, 1.0)
        for r in rows.values():
            self.assertAlmostEqual(r["delta"], max(abs(g - 1) for g in r["gain"]))
        # median of (120,135,105) = 120: grey needs nothing.
        for g in rows["grey"]["gain"]:
            self.assertAlmostEqual(g, 1.0, delta=0.02)

    def test_extreme_red_clip_clamps_at_max_gain(self):
        clips = [_solid(self.d / "a.mp4", (120, 120, 120)), _solid(self.d / "b.mp4", (120, 120, 120)),
                 _solid(self.d / "red.mp4", (240, 60, 60))]
        red = [r for r in colormatch.plan(clips) if r["file"].endswith("red.mp4")][0]
        self.assertAlmostEqual(red["gain"][0], 0.85, places=6)
        self.assertAlmostEqual(red["gain"][1], 1.15, places=6)
        self.assertAlmostEqual(red["gain"][2], 1.15, places=6)
        self.assertAlmostEqual(red["delta"], 0.15, places=6)
        loose = [r for r in colormatch.plan(clips, max_gain=0.6) if r["file"].endswith("red.mp4")][0]
        self.assertAlmostEqual(loose["gain"][0], 0.5, delta=0.02)

    def test_given_reference_has_unit_gain(self):
        clips = self.trio()
        rows = colormatch.plan(clips, reference=clips[1])
        self.assertEqual(rows[1]["gain"], (1.0, 1.0, 1.0))
        self.assertAlmostEqual(rows[0]["gain"][0], 135 / 120, delta=0.02)  # grey pulled toward warm

    def test_single_clip_is_unit_gain(self):
        rows = colormatch.plan([_solid(self.d / "one.mp4", self.WARM)])
        self.assertEqual(rows[0]["gain"], (1.0, 1.0, 1.0))
        self.assertEqual(rows[0]["delta"], 0.0)

    def test_near_black_clip_is_suspect_and_untouched(self):
        clips = [_solid(self.d / "a.mp4", self.GREY), _solid(self.d / "b.mp4", self.WARM),
                 _solid(self.d / "k.mp4", (2, 2, 2))]
        k = [r for r in colormatch.plan(clips) if r["file"].endswith("k.mp4")][0]
        self.assertEqual(k["suspect"], "near-black")
        self.assertEqual(k["gain"], (1.0, 1.0, 1.0))

    def test_undecodable_clip_names_the_file(self):
        bad = self.d / "broken.mp4"
        bad.write_bytes(b"not a video at all")
        with self.assertRaises(colormatch.ColorMatchError) as cm:
            colormatch.mean_rgb(str(bad))
        self.assertIn("broken.mp4", str(cm.exception))
        with self.assertRaises(colormatch.ColorMatchError) as cm:
            colormatch.plan([str(bad)])
        self.assertIn("broken.mp4", str(cm.exception))

    def test_missing_reference_is_an_error(self):
        with self.assertRaises(colormatch.ColorMatchError) as cm:
            colormatch.plan(self.trio(), reference=str(self.d / "nope.mp4"))
        self.assertIn("nope.mp4", str(cm.exception))

    def test_apply_shrinks_channel_spread_by_half(self):
        clips = self.trio()
        before = colormatch.spread([colormatch.mean_rgb(c) for c in clips])
        outs = []
        for r in colormatch.plan(clips):
            out = self.d / "out" / Path(r["file"]).name
            colormatch.apply(r["file"], out, r["gain"])
            outs.append(str(out))
        after = colormatch.spread([colormatch.mean_rgb(o) for o in outs])
        print(f"\n  colormatch spread before={before:.1f} after={after:.1f}")
        self.assertLessEqual(after, before * 0.5)

    def test_apply_keeps_audio_tags_bt709_and_never_overwrites(self):
        src = _solid(self.d / "s.mp4", self.WARM)
        sha = _sha(src)
        out = colormatch.apply(src, self.d / "o" / "s.mp4", (0.9, 1.0, 1.1))
        self.assertTrue(ff.has_audio(out))
        self.assertEqual(color.probe_color(out)["color_space"], "bt709")
        self.assertEqual(_sha(src), sha)
        with self.assertRaises(colormatch.ColorMatchError):
            colormatch.apply(src, src, (1.0, 1.0, 1.0))
        self.assertEqual(_sha(src), sha)


@requires_ffmpeg
class ColorMatchCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / "src").mkdir()
        self.clips = [_solid(self.d / "src" / f"{n}.mp4", c)
                      for n, c in (("grey", (120, 120, 120)), ("warm", (135, 120, 105)), ("cool", (105, 120, 135)))]

    def run_cli(self, *argv):
        import contextlib
        from tools.vidkit.__main__ import main
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = main(["colormatch", *argv])
        return rc, buf.getvalue(), err.getvalue()

    def test_report_only_writes_nothing_and_prints_table_and_spread(self):
        shas = [_sha(c) for c in self.clips]
        before = sorted(p.name for p in self.d.rglob("*"))
        rc, out, _ = self.run_cli(*self.clips)
        self.assertEqual(rc, 0)
        for n in ("grey.mp4", "warm.mp4", "cool.mp4"):
            self.assertIn(n, out)
        self.assertIn("spread", out)
        self.assertEqual(sorted(p.name for p in self.d.rglob("*")), before)
        self.assertEqual([_sha(c) for c in self.clips], shas)

    def test_apply_writes_only_clips_over_min_delta_and_copies_the_rest(self):
        shas = [_sha(c) for c in self.clips]
        outdir = self.d / "matched"
        rc, out, err = self.run_cli(*self.clips, "--apply", str(outdir), "--min-delta", "0.05")
        self.assertEqual(rc, 0, err)
        self.assertEqual(sorted(p.name for p in outdir.iterdir()), ["cool.mp4", "grey.mp4", "warm.mp4"])
        # grey is at the median: copied untouched, byte for byte.
        self.assertEqual(_sha(outdir / "grey.mp4"), shas[0])
        self.assertNotEqual(_sha(outdir / "warm.mp4"), shas[1])
        self.assertNotEqual(_sha(outdir / "cool.mp4"), shas[2])
        self.assertEqual([_sha(c) for c in self.clips], shas)
        self.assertIn("after", out)

    def test_high_min_delta_rewrites_nothing(self):
        outdir = self.d / "matched"
        rc, out, _ = self.run_cli(*self.clips, "--apply", str(outdir), "--min-delta", "0.5")
        self.assertEqual(rc, 0)
        for c in self.clips:
            self.assertEqual(_sha(outdir / Path(c).name), _sha(c))

    def test_apply_into_the_source_folder_is_refused(self):
        shas = [_sha(c) for c in self.clips]
        rc, _, err = self.run_cli(*self.clips, "--apply", str(self.d / "src"))
        self.assertEqual(rc, 1)
        self.assertIn("source", err)
        self.assertEqual([_sha(c) for c in self.clips], shas)

    def test_bad_clip_fails_with_file_name(self):
        bad = self.d / "bad.mp4"
        bad.write_bytes(b"x")
        rc, _, err = self.run_cli(*self.clips, str(bad))
        self.assertEqual(rc, 1)
        self.assertIn("bad.mp4", err)
