import contextlib
import hashlib
import io
import json
import os
import random
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests.py.media import duration_of, make_clip, requires_ffmpeg
from tools.vidkit import __main__ as vcli
from tools.vidkit import layout, title
from tools.vidkit import beats, color, colormatch, cover, encoder, ff, gates, ingest, join, karaoke, mixdown, unwhite, loudness, patch, sheet, speech, synth, tidy, track


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

    def test_download_passes_browser_cookies_to_yt_dlp(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ff, "run") as run:
            target = Path(d) / "source.mp4"
            run.side_effect = lambda cmd, **kw: target.write_bytes(b"x")
            ingest.download("https://x/reel", d, cookies_from_browser="chrome")
            cmd = run.call_args[0][0]
            self.assertEqual(cmd[cmd.index("--cookies-from-browser") + 1], "chrome")
            self.assertEqual(cmd[-1], "https://x/reel")

    def test_download_without_cookies_has_no_cookie_flag(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ff, "run") as run:
            run.side_effect = lambda cmd, **kw: (Path(d) / "source.mp4").write_bytes(b"x")
            ingest.download("https://x/reel", d)
            self.assertNotIn("--cookies-from-browser", run.call_args[0][0])

    def test_download_section_fetches_only_that_range(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ff, "run") as run:
            run.side_effect = lambda cmd, **kw: (Path(d) / "source.mp4").write_bytes(b"x")
            ingest.download("https://x/v", d, section="1362.5-1366")
            cmd = run.call_args[0][0]
            self.assertEqual(cmd[cmd.index("--download-sections") + 1], "*1362.5-1366")

    def test_download_rejects_malformed_section(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ff, "run") as run:
            for bad in ("90", "10-5", "a-b"):
                with self.assertRaises(ValueError):
                    ingest.download("https://x/v", d, section=bad)
            run.assert_not_called()

    def test_cli_ingest_forwards_cookies_flag(self):
        with mock.patch.object(ingest, "download", return_value="p") as dl, \
                contextlib.redirect_stdout(io.StringIO()):
            vcli.main(["ingest", "https://x/reel", "out", "--cookies-from-browser", "chrome"])
        dl.assert_called_once_with("https://x/reel", "out", "source", "chrome", None)

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

    def test_old_call_without_profile_is_byte_identical(self):
        w = [("a", 0, .5), ("b", .5, 1), ("c", 1, 1.5), ("d", 1.5, 2)]
        ass = karaoke.build_ass(w, 3.0, "@x")
        self.assertEqual(hashlib.sha1(ass.encode()).hexdigest(), "6b9d8e631d67606f3e5dad4848ec3bd5b70069d6")

    def _style(self, ass):
        line = next(l for l in ass.splitlines() if l.startswith("Style: Sub,"))
        f = line[len("Style: "):].split(",")
        return {"size": int(f[2]), "align": int(f[18]), "margin_v": int(f[21])}

    def test_profile_sets_size_margin_and_baseline_inside_safe_box(self):
        prof = layout.load("short-organic")
        st = self._style(karaoke.build_ass(self.W, 5.0, profile="short-organic"))
        self.assertEqual(st["size"], round(layout.value(prof, "subtitle.font_pct") * 1920))
        self.assertEqual(st["align"], 2)
        baseline = 1920 - st["margin_v"]
        self.assertEqual(baseline, round(layout.value(prof, "subtitle.baseline_y_pct") * 1920))
        self.assertLessEqual(baseline, layout.safe_box(prof)[3])

    def test_profile_per_group_four_breaks_into_two_lines(self):
        w = [(c, i * .5, i * .5 + .5) for i, c in enumerate(["aa", "bb", "cc", "dd", "ee"])]
        ass = karaoke.build_ass(w, 5.0, profile="short-organic")
        first = next(l for l in ass.splitlines() if l.startswith("Dialogue"))
        self.assertIn("aa {\\kf50}bb \\N{\\kf50}cc".replace(" \\N", "\\N"), first.replace(" \\N", "\\N"))
        self.assertEqual(first.count("\\N"), 1)
        self.assertEqual(first.count("\\kf"), 4)  # highlight spans the break
        self.assertNotIn("ee", first)  # group is 4 words, fifth starts the next

    def test_profile_short_group_stays_one_line(self):
        w = [("aa", 0, .5), ("bb", .5, 1), ("cc.", 1, 1.5)]
        ass = karaoke.build_ass(w, 3.0, profile="short-organic")
        self.assertNotIn("\\N", ass)

    def test_explicit_values_win_over_profile(self):
        ass = karaoke.build_ass(self.W, 5.0, profile="short-organic", font_size=70, margin_v=200, per_group=2)
        st = self._style(ass)
        self.assertEqual((st["size"], st["margin_v"]), (70, 200))
        self.assertNotIn("\\N", ass)

    def test_other_size_scales_pct_values(self):
        st = self._style(karaoke.build_ass(self.W, 5.0, profile="short-organic", width=540, height=960))
        self.assertEqual(st["size"], round(0.029 * 960))
        self.assertEqual(st["margin_v"], 960 - round(0.617 * 960))

    def test_unknown_profile_names_valid_ones(self):
        with self.assertRaises(KeyError) as cm:
            karaoke.build_ass(self.W, 5.0, profile="nope")
        self.assertIn("short-organic", str(cm.exception))

    def test_watermark_box_inside_safe_area_at_profile_size(self):
        prof = layout.load("short-organic")
        x0, y0, x1, y1 = layout.safe_box(prof)
        ass = karaoke.build_ass(self.W, 5.0, watermark="@alisadikinma", profile="short-organic")
        line = next(l for l in ass.splitlines() if "\\an5" in l)
        fs = int(line.split("\\fs")[1].split("\\")[0])
        half_w = len("@alisadikinma") * fs * 0.6 / 2
        self.assertGreaterEqual(540 - half_w, x0)
        self.assertLessEqual(540 + half_w, x1)
        self.assertGreaterEqual(960 - fs / 2, y0)
        self.assertLessEqual(960 + fs / 2, y1)

    def test_watermark_too_wide_for_safe_area_is_refused(self):
        with self.assertRaises(ValueError):
            karaoke.build_ass(self.W, 5.0, watermark="@" + "x" * 40, profile="short-organic")

    def test_cli_unknown_profile_exits_2_with_names(self):
        with tempfile.TemporaryDirectory() as d:
            wf = Path(d) / "w.json"
            wf.write_text(json.dumps(self.W))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = vcli.main(["karaoke", str(wf), str(Path(d) / "o.ass"), "--total", "3", "--profile", "nope"])
            self.assertEqual(rc, 2)
            self.assertIn("short-organic", err.getvalue())

    def test_cli_default_profile_and_none_opt_out(self):
        with tempfile.TemporaryDirectory() as d:
            wf, o = Path(d) / "w.json", Path(d) / "o.ass"
            wf.write_text(json.dumps(self.W))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(vcli.main(["karaoke", str(wf), str(o), "--total", "3"]), 0)
                self.assertEqual(self._style(o.read_text())["size"], round(0.029 * 1920))
                self.assertEqual(vcli.main(["karaoke", str(wf), str(o), "--total", "3", "--profile", "none"]), 0)
                self.assertEqual(self._style(o.read_text())["size"], 86)


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

    def test_probe_returns_pix_fmt(self):
        info = ff.probe(self.clip("a.mp4", seconds=1.0))
        self.assertEqual(info["video"]["pix_fmt"], "yuv420p")

    def test_probe_audio_only_has_no_video(self):
        wav = self.dir / "a.wav"
        ff.ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=1", wav)
        info = ff.probe(wav)
        self.assertIsNone(info["video"])
        self.assertIsNotNone(info["audio"])

    def test_missing_binary_raises_ffmissing(self):
        clip = self.clip("a.mp4", seconds=1.0)
        empty = tempfile.mkdtemp(dir=self.dir)
        with mock.patch.dict(os.environ, {"PATH": empty}):
            with self.assertRaises(ff.FFMissing) as ctx:
                ff.probe(clip)
        self.assertEqual(str(ctx.exception), "ffprobe not found on PATH")
        self.assertIsInstance(ctx.exception, ff.FFError)

    def test_missing_binary_with_heartbeat_raises_ffmissing(self):
        empty = tempfile.mkdtemp(dir=self.dir)
        with mock.patch.dict(os.environ, {"PATH": empty}):
            with self.assertRaises(ff.FFMissing) as ctx:
                ff.run(["ffmpeg", "-version"], heartbeat_s=1)
        self.assertEqual(str(ctx.exception), "ffmpeg not found on PATH")

    def test_nonzero_exit_is_plain_fferror(self):
        bad = self.dir / "bad.mp4"
        bad.write_text("not media")
        with self.assertRaises(ff.FFError) as ctx:
            ff.probe(bad)
        self.assertNotIsInstance(ctx.exception, ff.FFMissing)

    def test_tools_and_missing(self):
        self.assertEqual(ff.TOOLS, ("ffmpeg", "ffprobe"))
        self.assertEqual(ff.missing(), [])
        empty = tempfile.mkdtemp(dir=self.dir)
        with mock.patch.dict(os.environ, {"PATH": empty}):
            self.assertEqual(ff.missing(), ["ffmpeg", "ffprobe"])

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

    def test_untagged_is_assumed_bt709_with_one_warning(self):
        w = []
        self.assertEqual(color.convert_filter(self._p(), w, "u.mp4"), "")
        self.assertEqual(len(w), 1)
        self.assertIn("u.mp4", w[0])
        self.assertIn("assuming bt709", w[0])

    def test_unknown_matrix_with_bt601_primaries_or_transfer_is_converted(self):
        w = []
        self.assertEqual(color.convert_filter(self._p(prim="smpte170m"), w),
                         "colorspace=all=bt709:iall=bt601-6-525")
        self.assertEqual(color.convert_filter(self._p(prim="bt470bg"), w),
                         "colorspace=all=bt709:iall=bt601-6-625")
        self.assertEqual(color.convert_filter(self._p(trc="smpte170m"), w),
                         "colorspace=all=bt709:iall=bt601-6-525")
        self.assertEqual(w, [])

    def test_partly_tagged_bt709_primaries_stay_quiet(self):
        w = []
        self.assertEqual(color.convert_filter(self._p(prim="bt709"), w), "")
        self.assertEqual(w, [])

    def test_full_range_is_detected_from_range_or_pix_fmt(self):
        self.assertTrue(color.is_full_range({"color_range": "pc"}))
        self.assertTrue(color.is_full_range({"color_range": "unknown", "pix_fmt": "yuvj420p"}))
        self.assertFalse(color.is_full_range({"color_range": "tv", "pix_fmt": "yuv420p"}))

    def test_source_filters_orders_range_before_matrix(self):
        from unittest import mock
        probe = {"color_space": "smpte170m", "color_primaries": "smpte170m",
                 "color_transfer": "smpte170m", "color_range": "pc", "pix_fmt": "yuvj420p"}
        with mock.patch.object(color, "probe_color", return_value=probe):
            self.assertEqual(color.source_filters("x.mp4"),
                             [color.FULL_TO_LIMITED, "colorspace=all=bt709:iall=bt601-6-525"])

    def test_probe_uses_the_resolved_ffprobe(self):
        from unittest import mock
        with mock.patch.object(color, "FFPROBE", "/opt/x/ffprobe"), \
                mock.patch.object(color.ff, "run", return_value='{"streams": [{}]}') as run:
            color.probe_color("a.mp4")
        self.assertEqual(run.call_args[0][0][0], "/opt/x/ffprobe")

    def test_failed_probe_on_an_existing_file_warns_with_the_error(self):
        import contextlib
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.mp4"
            bad.write_bytes(b"not a video")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(color.source_filters(str(bad)), [])
            self.assertEqual(err.getvalue().count("\n"), 1)
            self.assertIn("bad.mp4", err.getvalue())
            self.assertIn("probe failed", err.getvalue())

    def test_failed_probe_on_a_file_that_does_not_exist_is_silent(self):
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(color.source_filters("/no/such/clip.mp4"), [])
        self.assertEqual(err.getvalue(), "")

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


class FingerprintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.a = self.d / "a.bin"
        self.a.write_bytes(b"alpha")

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_inputs_same_fingerprint(self):
        from tools.vidkit import stages
        one = stages.fingerprint([self.a], {"x": 1, "y": [2]})
        two = stages.fingerprint([self.a], {"y": [2], "x": 1})
        self.assertEqual(one, two)
        self.assertRegex(one, r"^[0-9a-f]{64}$")

    def test_file_bytes_params_and_version_each_change_it(self):
        from tools.vidkit import stages
        base = stages.fingerprint([self.a], {"x": 1})
        self.assertNotEqual(base, stages.fingerprint([self.a], {"x": 2}))
        self.assertNotEqual(base, stages.fingerprint([self.a], {"x": 1}, version="2"))
        self.a.write_bytes(b"alphb")
        self.assertNotEqual(base, stages.fingerprint([self.a], {"x": 1}))

    def test_same_bytes_under_another_name_is_the_same(self):
        from tools.vidkit import stages
        b = self.d / "b.bin"
        b.write_bytes(b"alpha")
        self.assertEqual(stages.fingerprint([self.a]), stages.fingerprint([b]))

    def test_file_order_matters(self):
        from tools.vidkit import stages
        b = self.d / "b.bin"
        b.write_bytes(b"beta")
        self.assertNotEqual(stages.fingerprint([self.a, b]), stages.fingerprint([b, self.a]))

    def test_missing_file_names_itself(self):
        from tools.vidkit import stages
        with self.assertRaises(stages.StageError) as cm:
            stages.fingerprint([self.d / "gone.bin"])
        self.assertIn("gone.bin", str(cm.exception))

    def test_large_file_is_streamed_in_order(self):
        from tools.vidkit import stages
        big = self.d / "big.bin"
        big.write_bytes(b"z" * (3 * 1024 * 1024 + 5))
        self.assertEqual(stages.fingerprint([big]), stages.fingerprint([big]))
        big.write_bytes(b"z" * (3 * 1024 * 1024 + 4) + b"y")
        self.assertNotEqual(stages.fingerprint([big]),
                            stages.fingerprint([self.d / "a.bin"]))


class StageCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.out = self.d / "out.bin"
        self.out.write_bytes(b"x")
        self.path = self.d / "cache" / "stages.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_then_fresh(self):
        from tools.vidkit import stages
        c = stages.StageCache(self.path)
        self.assertFalse(c.is_fresh("s", "fp1", [self.out]))
        c.record("s", "fp1", [self.out])
        self.assertTrue(stages.StageCache(self.path).is_fresh("s", "fp1", [self.out]))
        self.assertFalse(c.is_fresh("s", "fp2", [self.out]))
        self.assertFalse(c.is_fresh("other", "fp1", [self.out]))

    def test_deleted_output_is_not_fresh(self):
        from tools.vidkit import stages
        c = stages.StageCache(self.path)
        c.record("s", "fp1", [self.out])
        self.out.unlink()
        self.assertFalse(c.is_fresh("s", "fp1", [self.out]))

    def test_corrupt_cache_is_empty_and_replaced_on_record(self):
        from tools.vidkit import stages
        self.path.parent.mkdir()
        self.path.write_text("{not json")
        c = stages.StageCache(self.path)
        self.assertFalse(c.is_fresh("s", "fp1", [self.out]))
        c.record("s", "fp1", [self.out])
        self.assertEqual(json.loads(self.path.read_text())["s"]["fp"], "fp1")

    def test_wrong_shape_cache_is_empty(self):
        from tools.vidkit import stages
        self.path.parent.mkdir()
        self.path.write_text("[1, 2]")
        self.assertFalse(stages.StageCache(self.path).is_fresh("s", "fp1", [self.out]))

    def test_failed_replace_keeps_the_old_cache(self):
        from unittest import mock
        from tools.vidkit import stages
        c = stages.StageCache(self.path)
        c.record("s", "old", [self.out])
        before = self.path.read_text()
        with mock.patch("os.replace", side_effect=OSError("boom")):
            c.record("s", "new", [self.out])
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["stages.json"])

    def test_unwritable_dir_warns_and_never_caches(self):
        import contextlib
        from tools.vidkit import stages
        blocker = self.d / "file"
        blocker.write_text("x")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            c = stages.StageCache(blocker / "sub" / "stages.json")
            c.record("s", "fp1", [self.out])
        self.assertIn("caching disabled", err.getvalue())
        self.assertFalse(c.is_fresh("s", "fp1", [self.out]))


class EncoderChooseTest(unittest.TestCase):
    HW = {"libx264", "h264_videotoolbox"}

    def test_available_parses_encoders_listing(self):
        text = (" V....D libx264              libx264 H.264\n"
                " V....D h264_videotoolbox    VideoToolbox H.264 Encoder\n"
                " A....D aac                  AAC\n"
                " ------\n Encoders:\n")
        self.assertEqual(encoder.available(text), {"libx264", "h264_videotoolbox", "aac"})

    def test_available_empty_output(self):
        self.assertEqual(encoder.available(""), set())

    def test_unset_and_libx264_choose_libx264(self):
        self.assertEqual(encoder.choose(None, self.HW), ("libx264", None))
        self.assertEqual(encoder.choose("", self.HW), ("libx264", None))
        self.assertEqual(encoder.choose("libx264", self.HW), ("libx264", None))

    def test_auto_picks_hardware_when_available(self):
        self.assertEqual(encoder.choose("auto", self.HW), ("h264_videotoolbox", None))

    def test_auto_without_hardware_is_libx264(self):
        self.assertEqual(encoder.choose("auto", {"libx264"}), ("libx264", None))

    def test_explicit_hardware_unavailable_warns_and_falls_back(self):
        name, warn = encoder.choose("h264_videotoolbox", {"libx264"})
        self.assertEqual(name, "libx264")
        self.assertIn("h264_videotoolbox", warn)

    def test_explicit_hardware_available(self):
        self.assertEqual(encoder.choose("h264_videotoolbox", self.HW), ("h264_videotoolbox", None))

    def test_unknown_value_raises(self):
        with self.assertRaises(encoder.EncoderError):
            encoder.choose("bogus", self.HW)


class EncoderArgsTest(unittest.TestCase):
    def test_libx264_default_is_exactly_the_legacy_args(self):
        self.assertEqual(" ".join(encoder.video_args("libx264")),
                         "-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p")

    def test_libx264_crf_override(self):
        self.assertIn("18", encoder.video_args("libx264", crf=18))

    def test_hardware_bitrate_by_height(self):
        self.assertEqual(encoder.video_args("h264_videotoolbox", height=1080),
                         ["-c:v", "h264_videotoolbox", "-b:v", "12M", "-pix_fmt", "yuv420p"])
        self.assertIn("6M", encoder.video_args("h264_videotoolbox", height=720))
        self.assertIn("8M", encoder.video_args("h264_videotoolbox", height=480))

    def test_unknown_encoder_name_raises(self):
        with self.assertRaises(encoder.EncoderError):
            encoder.video_args("nvenc")


class EncoderFallbackTest(unittest.TestCase):
    def _builder(self):
        return lambda name: ["ffmpeg", "-c:v", name]

    def test_hardware_failure_retries_once_with_libx264(self):
        import contextlib
        calls = []

        def run(cmd):
            calls.append(cmd)
            if "h264_videotoolbox" in cmd:
                raise ff.FFError("hw boom")
            return "ok"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = encoder.run_with_fallback(self._builder(), "h264_videotoolbox", run)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1], ["ffmpeg", "-c:v", "libx264"])
        self.assertIn("encoder h264_videotoolbox failed, retried with libx264", out.getvalue())

    def test_libx264_failure_is_not_retried(self):
        calls = []

        def run(cmd):
            calls.append(cmd)
            raise ff.FFError("sw boom")
        with self.assertRaises(ff.FFError):
            encoder.run_with_fallback(self._builder(), "libx264", run)
        self.assertEqual(len(calls), 1)

    def test_both_fail_raises_with_both_tails(self):
        def run(cmd):
            raise ff.FFError("tail-" + cmd[-1])
        with self.assertRaises(ff.FFError) as cm:
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                encoder.run_with_fallback(self._builder(), "h264_videotoolbox", run)
        msg = str(cm.exception)
        self.assertIn("tail-h264_videotoolbox", msg)
        self.assertIn("tail-libx264", msg)

    def test_success_first_try_runs_once(self):
        calls = []
        encoder.run_with_fallback(self._builder(), "h264_videotoolbox", lambda c: calls.append(c))
        self.assertEqual(len(calls), 1)


class HeartbeatTest(unittest.TestCase):
    def _run(self, code, **kw):
        import contextlib, sys
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                res = ff.run([sys.executable, "-c", code], **kw)
                err = None
            except ff.FFError as exc:
                res, err = None, exc
        return res, err, out.getvalue()

    def test_beats_while_child_runs(self):
        res, err, text = self._run("import time; time.sleep(1.2)", heartbeat_s=0.5)
        self.assertIsNone(err)
        lines = [ln for ln in text.splitlines() if ln.startswith("still running: ")]
        self.assertGreaterEqual(len(lines), 2, text)
        self.assertRegex(lines[0], r"^still running: \S.* \d+(\.\d+)?s$")

    def test_child_stdout_still_returned(self):
        res, err, _ = self._run("print('hello')", heartbeat_s=0.5)
        self.assertEqual(res.strip(), "hello")

    def test_capture_stderr_returns_stderr(self):
        res, _, _ = self._run("import sys; sys.stderr.write('measured')", heartbeat_s=0.5,
                              capture_stderr=True)
        self.assertEqual(res, "measured")

    def test_failing_child_propagates_rc_and_stderr_tail(self):
        _, err, _ = self._run("import sys; sys.stderr.write('bad thing'); sys.exit(3)", heartbeat_s=0.5)
        self.assertIsNotNone(err)
        self.assertIn("(3)", str(err))
        self.assertIn("bad thing", str(err))

    def test_heartbeat_longer_than_process_prints_nothing(self):
        _, err, text = self._run("print('x')", heartbeat_s=30)
        self.assertIsNone(err)
        self.assertNotIn("still running", text)

    def test_default_has_no_heartbeat(self):
        _, _, text = self._run("import time; time.sleep(0.3)")
        self.assertEqual(text, "")


class LoudnessProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def write(self, text):
        p = self.d / "profiles.json"
        p.write_text(text)
        return p

    def prof(self, name="x", **fields):
        base = {"lufs": -14, "true_peak": -1.0, "source": "Some Document, 2026"}
        base.update(fields)
        return self.write(json.dumps({"profiles": {name: base}}))

    def test_default_is_minus_14_and_minus_1(self):
        self.assertEqual(loudness.profile("default"), {"lufs": -14.0, "true_peak": -1.0})

    def test_shipped_file_has_only_sourced_default(self):
        data = json.loads(Path(loudness.PROFILES_PATH).read_text())
        self.assertEqual(list(data["profiles"]), ["default"])
        self.assertTrue(data["profiles"]["default"]["source"].strip())

    def test_unknown_name_raises(self):
        with self.assertRaises(loudness.ProfileError):
            loudness.profile("nope")

    def test_valid_temp_profile_loads(self):
        self.assertEqual(loudness.profile("x", path=self.prof(lufs=-11)), {"lufs": -11.0, "true_peak": -1.0})

    def test_missing_source_raises(self):
        p = self.write(json.dumps({"profiles": {"x": {"lufs": -14, "true_peak": -1.0}}}))
        with self.assertRaisesRegex(loudness.ProfileError, "source"):
            loudness.profile("x", path=p)

    def test_empty_or_blank_source_raises(self):
        for src in ("", "   ", None, 5):
            with self.assertRaises(loudness.ProfileError, msg=repr(src)):
                loudness.profile("x", path=self.prof(source=src))

    def test_lufs_out_of_range_raises(self):
        for v in (-3, -30, -5.99, -24.01):
            with self.assertRaises(loudness.ProfileError, msg=str(v)):
                loudness.profile("x", path=self.prof(lufs=v))

    def test_lufs_range_edges_accepted(self):
        for v in (-24, -6):
            self.assertEqual(loudness.profile("x", path=self.prof(lufs=v))["lufs"], float(v))

    def test_true_peak_out_of_range_raises(self):
        for v in (1.0, 0.1, -9.5, -20):
            with self.assertRaises(loudness.ProfileError, msg=str(v)):
                loudness.profile("x", path=self.prof(true_peak=v))

    def test_non_numeric_values_raise(self):
        for field in ("lufs", "true_peak"):
            for v in ("-14", None, True):
                with self.assertRaises(loudness.ProfileError, msg=f"{field}={v!r}"):
                    loudness.profile("x", path=self.prof(**{field: v}))

    def test_duplicate_profile_names_raise(self):
        one = '{"lufs": -14, "true_peak": -1.0, "source": "doc"}'
        two = '{"lufs": -12, "true_peak": -1.0, "source": "doc"}'
        p = self.write('{"profiles": {"x": %s, "x": %s}}' % (one, two))
        with self.assertRaisesRegex(loudness.ProfileError, "duplicate"):
            loudness.profile("x", path=p)

    def test_malformed_json_raises(self):
        with self.assertRaises(loudness.ProfileError):
            loudness.profile("x", path=self.write("{not json"))

    def test_wrong_shape_raises(self):
        for text in ("[]", '{"profiles": []}', '{"nope": 1}', '{"profiles": {"x": 3}}'):
            with self.assertRaises(loudness.ProfileError, msg=text):
                loudness.profile("x", path=self.write(text))

    def test_missing_file_falls_back_to_default_with_warning(self):
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            got = loudness.profile("default", path=self.d / "absent.json")
        self.assertEqual(got, {"lufs": -14.0, "true_peak": -1.0})
        self.assertEqual(len(w), 1)
        self.assertIn("absent.json", str(w[0].message))

    def test_missing_file_other_name_still_raises(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaises(loudness.ProfileError):
                loudness.profile("short", path=self.d / "absent.json")

    def test_env_override_selects_file(self):
        import os
        p = self.prof(lufs=-12)
        old = os.environ.get("GASPOL_LOUDNESS_PROFILES")
        os.environ["GASPOL_LOUDNESS_PROFILES"] = str(p)
        try:
            self.assertEqual(loudness.profile("x")["lufs"], -12.0)
        finally:
            if old is None:
                del os.environ["GASPOL_LOUDNESS_PROFILES"]
            else:
                os.environ["GASPOL_LOUDNESS_PROFILES"] = old


class NormalizeProfileCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def run_cli(self, *argv):
        import contextlib
        from tools.vidkit.__main__ import main
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = main(["normalize", *argv])
        return rc, buf.getvalue(), err.getvalue()

    @requires_ffmpeg
    def test_profile_default_matches_no_profile_and_hits_minus_14(self):
        src = make_clip(self.d / "a.mp4", seconds=3.0)
        rc, out, _ = self.run_cli(str(src), str(self.d / "p.mp4"), "--profile", "default")
        self.assertEqual(rc, 0)
        self.assertIn("default", out)
        self.assertIn("-14", out)
        rc2, _, _ = self.run_cli(str(src), str(self.d / "q.mp4"))
        self.assertEqual(rc2, 0)
        a = mixdown.measure_lufs(str(self.d / "p.mp4"))
        b = mixdown.measure_lufs(str(self.d / "q.mp4"))
        self.assertAlmostEqual(a, -14.0, delta=0.5)
        self.assertAlmostEqual(a, b, delta=0.05)

    @requires_ffmpeg
    def test_explicit_lufs_wins_over_profile(self):
        src = make_clip(self.d / "a.mp4", seconds=3.0)
        rc, _, _ = self.run_cli(str(src), str(self.d / "w.mp4"), "--profile", "default", "--lufs", "-18")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(mixdown.measure_lufs(str(self.d / "w.mp4")), -18.0, delta=0.7)

    def test_unknown_profile_exits_2_with_message_and_writes_nothing(self):
        src = self.d / "a.mp4"
        src.write_bytes(b"x")
        rc, out, err = self.run_cli(str(src), str(self.d / "o.mp4"), "--profile", "nope")
        self.assertEqual(rc, 2)
        self.assertIn("nope", err)
        self.assertFalse((self.d / "o.mp4").exists())

    def test_invalid_profile_file_exits_2(self):
        import os
        bad = self.d / "bad.json"
        bad.write_text(json.dumps({"profiles": {"x": {"lufs": -14, "true_peak": -1.0}}}))
        src = self.d / "a.mp4"
        src.write_bytes(b"x")
        old = os.environ.get("GASPOL_LOUDNESS_PROFILES")
        os.environ["GASPOL_LOUDNESS_PROFILES"] = str(bad)
        try:
            rc, _, err = self.run_cli(str(src), str(self.d / "o.mp4"), "--profile", "x")
        finally:
            if old is None:
                del os.environ["GASPOL_LOUDNESS_PROFILES"]
            else:
                os.environ["GASPOL_LOUDNESS_PROFILES"] = old
        self.assertEqual(rc, 2)
        self.assertIn("source", err)


class MixdownProfileTest(unittest.TestCase):
    @requires_ffmpeg
    def test_default_profile_same_loudness_as_absent(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            v = d / "v.mp4"
            make_clip(str(v), 3.0)
            res = {}
            for name, extra in (("none", {}), ("def", {"loudness_profile": "default"})):
                r = mixdown.run({"video": str(v), "out": str(d / f"{name}.mp4"), **extra}, workdir=d / f"w-{name}")
                res[name] = r["gain_db"]
            self.assertAlmostEqual(res["none"], res["def"], places=6)

    def test_unknown_loudness_profile_raises_before_work(self):
        with self.assertRaises(loudness.ProfileError):
            mixdown.run({"video": "/nonexistent.mp4", "out": "/tmp/x.mp4", "loudness_profile": "nope"})

    @requires_ffmpeg
    def test_explicit_lufs_wins_over_profile_key(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            v = d / "v.mp4"
            make_clip(str(v), 3.0)
            r0 = mixdown.run({"video": str(v), "out": str(d / "a.mp4"), "lufs": -18.0}, workdir=d / "wa")
            r1 = mixdown.run({"video": str(v), "out": str(d / "b.mp4"), "lufs": -18.0,
                              "loudness_profile": "default"}, workdir=d / "wb")
            self.assertAlmostEqual(r0["gain_db"], r1["gain_db"], places=6)


def _bt601_clip(path, seconds=1.5):
    """A testsrc clip explicitly tagged smpte170m (BT.601), with audio."""
    import subprocess
    tag = "setparams=colorspace=smpte170m:color_primaries=smpte170m:color_trc=smpte170m:range=tv"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"testsrc=size=320x240:rate=30:duration={seconds}", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={seconds}", "-vf", tag, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-colorspace", "smpte170m", "-color_primaries",
                    "smpte170m", "-color_trc", "smpte170m", "-c:a", "aac", "-t", str(seconds),
                    str(path)], check=True, capture_output=True)
    return str(path)


def _mean_rgb_of(path, vf):
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", vf, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return [sum(raw[c::3]) / (len(raw) / 3) for c in range(3)]


@requires_ffmpeg
class Bt601StampedOutputsTest(unittest.TestCase):
    """colormatch.apply and mixdown.run must convert a bt601 input, not just relabel it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.src = _bt601_clip(self.d / "sd.mp4")
        self.want = _mean_rgb_of(self.src, "colorspace=all=bt709:iall=bt601-6-525")

    def _check(self, out):
        self.assertEqual(color.probe_color(str(out))["color_space"], "bt709")
        got = _mean_rgb_of(out, "null")
        for w, g in zip(self.want, got):
            self.assertAlmostEqual(w, g, delta=3.0, msg=f"want {self.want} got {got}")

    def test_colormatch_apply_converts_a_bt601_input(self):
        self._check(colormatch.apply(self.src, self.d / "o" / "m.mp4", (1.0, 1.0, 1.0)))

    def test_mixdown_converts_a_bt601_input(self):
        out = self.d / "mix.mp4"
        mixdown.run({"video": self.src, "out": str(out)}, workdir=self.d / "w")
        self._check(out)



class StageCacheSafetyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def test_record_does_not_follow_a_planted_symlink_at_a_predictable_name(self):
        import os
        from tools.vidkit import stages
        victim = self.d / "victim.txt"
        victim.write_text("precious")
        cache = stages.StageCache(self.d / "stages.json")
        for name in (f"stages.json.{os.getpid()}.tmp", "stages.json.tmp"):
            (self.d / name).symlink_to(victim)
        cache.record("seg-1", "fp", [self.d / "a.mp4"])
        self.assertEqual(victim.read_text(), "precious")
        self.assertEqual(json.loads((self.d / "stages.json").read_text())["seg-1"]["fp"], "fp")

    def test_drop_removes_one_entry_and_keeps_the_rest(self):
        from tools.vidkit import stages
        out = self.d / "a.mp4"
        out.write_bytes(b"x")
        cache = stages.StageCache(self.d / "stages.json")
        cache.record("seg-1", "fp1", [out])
        cache.record("seg-2", "fp2", [out])
        cache.drop("seg-1")
        self.assertFalse(cache.is_fresh("seg-1", "fp1", [out]))
        self.assertTrue(cache.is_fresh("seg-2", "fp2", [out]))
        cache.drop("never-there")


@requires_ffmpeg
class ColorMatchGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / "src").mkdir()
        self.clips = [_solid(self.d / "src" / f"{n}.mp4", c)
                      for n, c in (("grey", (120, 120, 120)), ("warm", (135, 120, 105)),
                                   ("cool", (105, 120, 135)))]

    def run_cli(self, *argv):
        import contextlib
        from tools.vidkit.__main__ import main
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = main(["colormatch", *argv])
        return rc, buf.getvalue(), err.getvalue()

    def test_target_equal_to_the_reference_is_refused(self):
        (self.d / "out").mkdir()
        ref = _solid(self.d / "out" / "grey.mp4", (120, 120, 120))
        sha = _sha(ref)
        rc, _, err = self.run_cli(*self.clips, "--reference", ref, "--apply", str(self.d / "out"),
                                  "--force")
        self.assertEqual(rc, 1)
        self.assertIn("reference", err)
        self.assertEqual(_sha(ref), sha)

    def test_existing_target_is_refused_without_force(self):
        out = self.d / "out"
        out.mkdir()
        prior = out / "warm.mp4"
        prior.write_bytes(b"earlier result")
        sha = _sha(prior)
        rc, _, err = self.run_cli(*self.clips, "--apply", str(out))
        self.assertEqual(rc, 1)
        self.assertIn("warm.mp4", err)
        self.assertIn("--force", err)
        self.assertEqual(_sha(prior), sha)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["warm.mp4"],
                         "refusal happens before anything is written")

    def test_force_overwrites_an_existing_target(self):
        out = self.d / "out"
        out.mkdir()
        (out / "warm.mp4").write_bytes(b"earlier result")
        rc, _, err = self.run_cli(*self.clips, "--apply", str(out), "--force")
        self.assertEqual(rc, 0, err)
        self.assertNotEqual((out / "warm.mp4").read_bytes(), b"earlier result")

    def test_force_never_allows_overwriting_a_source(self):
        shas = [_sha(c) for c in self.clips]
        rc, _, err = self.run_cli(*self.clips, "--apply", str(self.d / "src"), "--force")
        self.assertEqual(rc, 1)
        self.assertEqual([_sha(c) for c in self.clips], shas)


@requires_ffmpeg
class MeanRgbDecodeCountTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clip = _solid(Path(self.tmp.name) / "a.mp4", (120, 120, 120))

    def _flaky(self, ok):
        from unittest import mock
        real = colormatch._frame_rgb
        calls = []

        def fake(path, t):
            calls.append(t)
            return real(path, t) if len(calls) <= ok else None
        return mock.patch.object(colormatch, "_frame_rgb", side_effect=fake)

    def test_fewer_than_half_decoded_raises_naming_the_file(self):
        with self._flaky(2), self.assertRaises(colormatch.ColorMatchError) as cm:
            colormatch.mean_rgb(self.clip)
        self.assertIn("a.mp4", str(cm.exception))
        self.assertIn("2 of 5", str(cm.exception))

    def test_report_shows_how_many_frames_decoded(self):
        with self._flaky(3):
            text = colormatch.report([self.clip])
        self.assertIn("3/5", text)

    def test_report_shows_full_count_when_all_decode(self):
        self.assertIn("5/5", colormatch.report([self.clip]))


class TidyScanTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)

    def w(self, rel, data=b"x"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def keys(self, report):
        return {k: v for k, v in report.items() if v}

    def test_unknown_top_level_dir_reported(self):
        (self.root / "_up").mkdir()
        (self.root / "keyframes").mkdir()
        self.assertEqual(tidy.scan(self.root)["unknown_dirs"], ["_up"])

    def test_dotted_dir_and_contract_dirs_ignored(self):
        for d in (".git", "keyframes", ".tmp", "screens", "packaging", "shots"):
            (self.root / d).mkdir()
        self.assertEqual(tidy.scan(self.root)["unknown_dirs"], [])

    def test_top_level_dir_symlink_listed_not_followed(self):
        with tempfile.TemporaryDirectory() as other:
            Path(other, "a.png").write_bytes(b"zz")
            os.symlink(other, self.root / "linked")
            r = tidy.scan(self.root)
        self.assertEqual(r["unknown_dirs"], ["linked"])

    def test_unknown_subdirs(self):
        for d in ("keyframes/_up", "clips/_ov", "output/old", "output/stems",
                  "shots/src", "work/x", "ref"):
            (self.root / d).mkdir(parents=True)
        self.w("keyframes/scene-01.png")
        r = tidy.scan(self.root)
        self.assertEqual(r["unknown_subdirs"], ["clips/_ov", "keyframes/_up", "output/old"])

    def test_symlinked_subdir_listed(self):
        (self.root / "keyframes").mkdir()
        with tempfile.TemporaryDirectory() as other:
            os.symlink(other, self.root / "keyframes" / "_gen")
            r = tidy.scan(self.root)
        self.assertEqual(r["unknown_subdirs"], ["keyframes/_gen"])

    def test_empty_project_is_clean(self):
        r = tidy.scan(self.root)
        self.assertEqual(self.keys(r), {})
        self.assertEqual(set(r), {"unknown_dirs", "unknown_subdirs", "duplicates", "stale_ledger",
                                  "old_tmp", "unmoved_mcp", "mcp_already_home", "unreadable"})
        self.assertEqual(tidy.format_report(r).strip(), "clean")

    def test_not_a_directory_raises(self):
        with self.assertRaises(ValueError):
            tidy.scan(self.root / "missing")
        f = self.w("file.txt")
        with self.assertRaises(ValueError):
            tidy.scan(f)

    def test_duplicates_pair(self):
        self.w("keyframes/a.png", b"same")
        self.w("ref/b.png", b"same")
        self.w("clips/c.mp4", b"other")
        self.assertEqual(tidy.scan(self.root)["duplicates"], [["keyframes/a.png", "ref/b.png"]])

    def test_duplicates_group_of_three(self):
        for rel in ("keyframes/a.png", "ref/b.png", "_arsip/c.png"):
            self.w(rel, b"same")
        groups = tidy.scan(self.root)["duplicates"]
        self.assertEqual(groups, [["_arsip/c.png", "keyframes/a.png", "ref/b.png"]])

    def test_same_size_different_bytes_no_group(self):
        self.w("keyframes/a.png", b"aaaa")
        self.w("ref/b.png", b"bbbb")
        self.assertEqual(tidy.scan(self.root)["duplicates"], [])

    def test_zero_byte_files_ignored(self):
        self.w("keyframes/a.png", b"")
        self.w("ref/b.png", b"")
        self.assertEqual(tidy.scan(self.root)["duplicates"], [])

    def test_shots_never_walked(self):
        self.w("shots/node_modules/p/a.js", b"dupe")
        self.w("shots/node_modules/q/b.js", b"dupe")
        self.w("shots/out/x.mp4", b"dupe")
        self.w("keyframes/a.png", b"dupe")
        self.assertEqual(tidy.scan(self.root)["duplicates"], [])

    def test_symlinked_file_not_followed(self):
        self.w("keyframes/a.png", b"same")
        os.symlink(self.root / "keyframes" / "a.png", self.root / "ref_link.png")
        (self.root / "ref").mkdir()
        os.symlink(self.root / "keyframes" / "a.png", self.root / "ref" / "l.png")
        self.assertEqual(tidy.scan(self.root)["duplicates"], [])

    def test_stale_ledger(self):
        self.w("keyframes/there.png")
        ledger = {"renders": [
            {"file": "keyframes/gone.png", "status": "done"},
            {"file": "keyframes/failed.png", "status": "failed"},
            {"file": "keyframes/there.png", "status": "done"},
        ]}
        self.w("renders.json", json.dumps(ledger))
        self.assertEqual(tidy.scan(self.root)["stale_ledger"], ["keyframes/gone.png"])

    def test_invalid_ledger_reported_not_raised(self):
        self.w("renders.json", "{not json")
        r = tidy.scan(self.root)
        self.assertEqual(len(r["stale_ledger"]), 1)
        self.assertTrue(r["stale_ledger"][0].startswith("renders.json: "))

    def test_old_tmp_boundary(self):
        now = 1_000_000_000.0
        day = 86400
        exact = self.w(".tmp/exact.txt")
        older = self.w(".tmp/sub/older.txt")
        os.utime(exact, (now - 7 * day, now - 7 * day))
        os.utime(older, (now - 7 * day - 1, now - 7 * day - 1))
        r = tidy.scan(self.root, tmp_days=7, now=now)
        self.assertEqual(r["old_tmp"], [".tmp/sub/older.txt"])

    def test_old_tmp_defaults_to_real_clock(self):
        p = self.w(".tmp/fresh.txt")
        os.utime(p, (time.time() - 30 * 86400,) * 2)
        self.assertEqual(tidy.scan(self.root)["old_tmp"], [".tmp/fresh.txt"])

    def test_unmoved_mcp(self):
        self.w(".tmp/image/a.png", b"paid")
        self.w(".tmp/a.png", b"paid2")
        self.w(".tmp/image/notes.txt", b"note")
        self.w(".tmp/video/v.mp4", b"clip")
        r = tidy.scan(self.root)
        self.assertEqual(r["unmoved_mcp"],
                         [".tmp/image/a.png", ".tmp/image/notes.txt", ".tmp/video/v.mp4"])
        self.assertEqual(r["mcp_already_home"], [])

    def test_mcp_already_home(self):
        self.w("keyframes/scene-01.png", b"paid")
        self.w(".tmp/image/a.png", b"paid")
        r = tidy.scan(self.root)
        self.assertEqual(r["mcp_already_home"], [".tmp/image/a.png = keyframes/scene-01.png"])
        self.assertEqual(r["unmoved_mcp"], [])
        self.assertEqual(r["duplicates"], [])

    def test_mcp_same_name_different_bytes_is_unmoved(self):
        self.w("keyframes/scene-01.png", b"old")
        self.w(".tmp/image/scene-01.png", b"new")
        r = tidy.scan(self.root)
        self.assertEqual(r["unmoved_mcp"], [".tmp/image/scene-01.png"])
        self.assertEqual(r["mcp_already_home"], [])

    def test_tmp_symlink_raises(self):
        with tempfile.TemporaryDirectory() as other:
            os.symlink(other, self.root / ".tmp")
            with self.assertRaises(ValueError):
                tidy.scan(self.root)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads everything")
    def test_unreadable_file(self):
        self.w("keyframes/a.png", b"same")
        bad = self.w("ref/b.png", b"same")
        os.chmod(bad, 0)
        self.addCleanup(os.chmod, bad, 0o644)
        r = tidy.scan(self.root)
        self.assertEqual(r["unreadable"], ["ref/b.png"])
        self.assertEqual(r["duplicates"], [])

    def snapshot(self):
        out = {}
        for dp, dn, fn in os.walk(self.root):
            for n in dn + fn:
                p = os.path.join(dp, n)
                st = os.lstat(p)
                out[p] = (st.st_mtime_ns, st.st_size, os.path.isdir(p))
        return out

    def test_scan_makes_no_writes(self):
        self.w("keyframes/a.png", b"same")
        self.w("ref/b.png", b"same")
        self.w(".tmp/image/x.png", b"same")
        self.w("renders.json", json.dumps({"renders": [{"file": "z.png", "status": "done"}]}))
        (self.root / "_up").mkdir()
        (self.root / "keyframes" / "_gen").mkdir()
        before = self.snapshot()
        tidy.scan(self.root)
        self.assertEqual(before, self.snapshot())

    def test_format_report_names_paths_and_counts(self):
        self.w("keyframes/a.png", b"same")
        self.w("ref/b.png", b"same")
        (self.root / "_up").mkdir()
        text = tidy.format_report(tidy.scan(self.root))
        self.assertIn("_up", text)
        self.assertIn("keyframes/a.png", text)
        self.assertIn("ref/b.png", text)
        self.assertNotIn("clean", text)
        self.assertIn("1", text)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _tree_hashes(base):
    out = {}
    for dp, dn, fn in os.walk(base):
        for n in fn:
            p = os.path.join(dp, n)
            out[os.path.relpath(p, base)] = _sha(p)
    return out


class TidyApplyTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name) / "proj"
        self.root.mkdir()

    def w(self, rel, data=b"x"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def apply(self):
        return tidy.apply_unknown_dirs(self.root, tidy.scan(self.root))

    def test_unknown_dir_moves_to_arsip(self):
        self.w("_up/a.png", b"AAA")
        moved = self.apply()
        self.assertEqual(moved, [("_up", "_arsip/folder-_up")])
        self.assertFalse((self.root / "_up").exists())
        self.assertEqual((self.root / "_arsip/folder-_up/a.png").read_bytes(), b"AAA")

    def test_subdir_moves_with_parent_in_name_and_keeps_bytes(self):
        self.w("keyframes/_up/a.png", b"AAA")
        moved = self.apply()
        self.assertEqual(moved, [("keyframes/_up", "_arsip/folder-keyframes-_up")])
        self.assertEqual((self.root / "_arsip/folder-keyframes-_up/a.png").read_bytes(), b"AAA")

    def test_same_subdir_name_in_two_parents_gets_two_destinations(self):
        self.w("keyframes/_up/a.png", b"1")
        self.w("clips/_up/b.mp4", b"2")
        moved = dict(self.apply())
        self.assertEqual(moved["keyframes/_up"], "_arsip/folder-keyframes-_up")
        self.assertEqual(moved["clips/_up"], "_arsip/folder-clips-_up")

    def test_existing_destination_gets_suffix_and_is_not_overwritten(self):
        self.w("_arsip/folder-_up/old.png", b"OLD")
        self.w("_up/new.png", b"NEW")
        moved = self.apply()
        self.assertEqual(moved, [("_up", "_arsip/folder-_up-2")])
        self.assertEqual((self.root / "_arsip/folder-_up/old.png").read_bytes(), b"OLD")
        self.assertEqual((self.root / "_arsip/folder-_up-2/new.png").read_bytes(), b"NEW")
        self.w("_up/third.png", b"3")
        self.assertEqual(self.apply(), [("_up", "_arsip/folder-_up-3")])

    def test_nothing_to_move_returns_empty(self):
        self.assertEqual(self.apply(), [])
        self.assertFalse((self.root / "_arsip").exists())

    def test_apply_is_idempotent_and_does_not_reflag_archived_folders(self):
        self.w("_up/a.png", b"A")
        self.apply()
        self.assertEqual(tidy.scan(self.root)["unknown_subdirs"], [])
        self.assertEqual(self.apply(), [])

    def test_symlinked_subdir_moved_as_link_target_untouched(self):
        with tempfile.TemporaryDirectory() as other:
            Path(other, "keep.png").write_bytes(b"KEEP")
            (self.root / "keyframes").mkdir()
            os.symlink(other, self.root / "keyframes" / "_gen")
            moved = self.apply()
            dst = self.root / "_arsip/folder-keyframes-_gen"
            self.assertEqual(moved, [("keyframes/_gen", "_arsip/folder-keyframes-_gen")])
            self.assertTrue(dst.is_symlink())
            self.assertFalse(os.path.lexists(self.root / "keyframes/_gen"))
            self.assertEqual(Path(other, "keep.png").read_bytes(), b"KEEP")

    def test_arsip_content_untouched_by_apply(self):
        self.w("_arsip/keyframe-scene-01-v1-x.png", b"PAID")
        self.w("_up/a.png")
        before = _tree_hashes(self.root / "_arsip")
        self.apply()
        after = _tree_hashes(self.root / "_arsip")
        self.assertEqual(before["keyframe-scene-01-v1-x.png"], after["keyframe-scene-01-v1-x.png"])

    # --- empty_tmp ---
    def test_empty_tmp_deletes_file_nested_dir_and_keeps_tmp(self):
        self.w(".tmp/a.txt")
        self.w(".tmp/deep/er/b.txt")
        r = tidy.empty_tmp(self.root)
        self.assertEqual(sorted(r["deleted"]), [".tmp/a.txt", ".tmp/deep/er/b.txt"])
        self.assertEqual(r["kept_mcp"], [])
        self.assertTrue((self.root / ".tmp").is_dir())
        self.assertEqual(list((self.root / ".tmp").iterdir()), [])

    def test_empty_tmp_missing_tmp_is_empty_result(self):
        self.assertEqual(tidy.empty_tmp(self.root)["deleted"], [])
        self.assertFalse((self.root / ".tmp").exists())

    def test_empty_tmp_not_a_directory_raises(self):
        with self.assertRaises(ValueError):
            tidy.empty_tmp(self.root / "nope")

    def test_empty_tmp_symlinked_tmp_raises_and_target_survives(self):
        with tempfile.TemporaryDirectory() as other:
            Path(other, "a.png").write_bytes(b"AAA")
            Path(other, "sub").mkdir()
            Path(other, "sub", "b.png").write_bytes(b"BBB")
            before = _tree_hashes(other)
            os.symlink(other, self.root / ".tmp")
            with self.assertRaises(ValueError):
                tidy.empty_tmp(self.root)
            with self.assertRaises(ValueError):
                tidy.empty_tmp(self.root, include_mcp=True)
            self.assertEqual(before, _tree_hashes(other))

    def test_empty_tmp_symlink_inside_unlinked_target_survives(self):
        with tempfile.TemporaryDirectory() as other:
            Path(other, "f.png").write_bytes(b"F")
            Path(other, "d").mkdir()
            Path(other, "d", "g.png").write_bytes(b"G")
            before = _tree_hashes(other)
            (self.root / ".tmp").mkdir()
            os.symlink(Path(other, "f.png"), self.root / ".tmp" / "link-file")
            os.symlink(Path(other, "d"), self.root / ".tmp" / "link-dir")
            r = tidy.empty_tmp(self.root)
            self.assertEqual(sorted(r["deleted"]), [".tmp/link-dir", ".tmp/link-file"])
            self.assertEqual(list((self.root / ".tmp").iterdir()), [])
            self.assertEqual(before, _tree_hashes(other))

    def test_unmoved_mcp_kept_by_default_and_deleted_with_include(self):
        # Changed in the safety fix: every file in the MCP area is kept by default,
        # notes.txt included (it used to be deleted).
        self.w(".tmp/image/a.png", b"PAID")
        self.w(".tmp/image/notes.txt", b"n")
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["kept_mcp"], [".tmp/image/a.png", ".tmp/image/notes.txt"])
        self.assertEqual(r["deleted"], [])
        self.assertTrue((self.root / ".tmp/image/a.png").exists())
        r2 = tidy.empty_tmp(self.root, include_mcp=True)
        self.assertEqual(r2["deleted"], [".tmp/image/a.png", ".tmp/image/notes.txt"])
        self.assertEqual(r2["kept_mcp"], [])
        self.assertEqual(list((self.root / ".tmp").iterdir()), [])

    def test_already_home_copy_deleted_home_untouched(self):
        self.w("keyframes/scene-01.png", b"PAID")
        self.w(".tmp/image/scene-01.png", b"PAID")
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["deleted"], [".tmp/image/scene-01.png"])
        self.assertEqual(r["home_of"], {".tmp/image/scene-01.png": "keyframes/scene-01.png"})
        self.assertEqual((self.root / "keyframes/scene-01.png").read_bytes(), b"PAID")

    def test_arsip_and_shots_out_untouched(self):
        self.w("_arsip/keyframe-scene-01-v1-x.png", b"PAID1")
        self.w("_arsip/folder-_up/z.png", b"PAID2")
        self.w("shots/out/s.mp4", b"RENDER")
        self.w(".tmp/junk.txt")
        before_a = _tree_hashes(self.root / "_arsip")
        before_s = _tree_hashes(self.root / "shots/out")
        tidy.empty_tmp(self.root, include_mcp=True)
        self.assertEqual(before_a, _tree_hashes(self.root / "_arsip"))
        self.assertEqual(before_s, _tree_hashes(self.root / "shots/out"))

    def test_second_empty_tmp_is_noop(self):
        self.w(".tmp/a.txt")
        self.w(".tmp/image/keep.png", b"PAID")
        tidy.empty_tmp(self.root)
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["deleted"], [])
        self.assertEqual(r["kept_mcp"], [".tmp/image/keep.png"])

    def test_apply_then_empty_tmp_sees_final_layout(self):
        self.w("keyframes/_up/scene-01.png", b"PAID")
        self.w(".tmp/image/scene-01.png", b"PAID")
        self.apply()
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["deleted"], [".tmp/image/scene-01.png"])
        self.assertTrue((self.root / "_arsip/folder-keyframes-_up/scene-01.png").exists())

    def test_scan_prefers_clean_home_over_stray_or_arsip(self):
        self.w("_arsip/old.png", b"PAID")
        self.w("keyframes/_up/x.png", b"PAID")
        self.w("keyframes/scene-02.png", b"PAID")
        self.w(".tmp/image/x.png", b"PAID")
        r = tidy.scan(self.root)
        self.assertEqual(r["mcp_already_home"], [".tmp/image/x.png = keyframes/scene-02.png"])

    def test_scan_falls_back_to_first_match_when_all_homes_are_stray(self):
        self.w("keyframes/_up/x.png", b"PAID")
        self.w("_arsip/old.png", b"PAID")
        self.w(".tmp/image/x.png", b"PAID")
        r = tidy.scan(self.root)
        self.assertEqual(r["mcp_already_home"], [".tmp/image/x.png = _arsip/old.png"])
        self.assertEqual(r["unmoved_mcp"], [])


class TidyCliTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name) / "proj"
        self.root.mkdir()

    def w(self, rel, data=b"x"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = vcli.main(["tidy", str(self.root), *argv])
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def snapshot(self):
        return sorted(os.path.relpath(os.path.join(dp, n), self.root)
                      for dp, dn, fn in os.walk(self.root) for n in dn + fn)

    def test_dry_run_changes_nothing_and_reports(self):
        self.w("_up/a.png")
        self.w("keyframes/_gen/b.png")
        self.w(".tmp/image/c.png", b"PAID")
        before = self.snapshot()
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("_up", out)
        self.assertIn("keyframes/_gen", out)
        self.assertEqual(before, self.snapshot())

    def test_clean_project_prints_clean(self):
        code, out, _ = self.run_cli()
        self.assertEqual((code, out.strip()), (0, "clean"))

    def test_apply_prints_each_move(self):
        self.w("_up/a.png")
        code, out, _ = self.run_cli("--apply")
        self.assertEqual(code, 0)
        self.assertIn("moved _up -> _arsip/folder-_up", out)
        self.assertTrue((self.root / "_arsip/folder-_up/a.png").exists())

    def test_apply_nothing_to_move(self):
        code, out, _ = self.run_cli("--apply")
        self.assertEqual(code, 0)
        self.assertIn("nothing to move", out)

    def test_empty_tmp_prints_count_copy_and_kept(self):
        self.w("keyframes/scene-01.png", b"PAID")
        self.w(".tmp/image/scene-01.png", b"PAID")
        self.w(".tmp/image/new.png", b"UNIQUE")
        code, out, _ = self.run_cli("--empty-tmp")
        self.assertEqual(code, 0)
        self.assertIn("deleted .tmp/image/scene-01.png (copy of keyframes/scene-01.png)", out)
        self.assertIn("paid render not moved yet, kept", out)
        self.assertIn(".tmp/image/new.png", out)
        self.assertIn("1 deleted", out)
        self.assertTrue((self.root / ".tmp/image/new.png").exists())
        self.assertFalse((self.root / ".tmp/image/scene-01.png").exists())

    def test_empty_tmp_include_mcp_deletes_unmoved(self):
        self.w(".tmp/image/new.png", b"UNIQUE")
        code, out, _ = self.run_cli("--empty-tmp", "--include-mcp")
        self.assertEqual(code, 0)
        self.assertFalse((self.root / ".tmp/image/new.png").exists())

    def test_include_mcp_without_empty_tmp_is_usage_error(self):
        self.w(".tmp/image/new.png", b"UNIQUE")
        code, _, err = self.run_cli("--include-mcp")
        self.assertEqual(code, 2)
        self.assertIn("--include-mcp", err)
        self.assertTrue((self.root / ".tmp/image/new.png").exists())

    def test_apply_and_empty_tmp_together_in_order(self):
        self.w("keyframes/_up/scene-01.png", b"PAID")
        self.w(".tmp/image/scene-01.png", b"PAID")
        code, out, _ = self.run_cli("--apply", "--empty-tmp")
        self.assertEqual(code, 0)
        self.assertLess(out.index("moved keyframes/_up"), out.index("deleted .tmp/image/scene-01.png"))
        self.assertIn("(copy of _arsip/folder-keyframes-_up/scene-01.png)", out)

    def test_not_a_directory_fails_with_exit_1(self):
        import shutil
        shutil.rmtree(self.root)
        code, _, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: not a directory", err)

    def test_symlinked_tmp_fails_with_exit_1_target_survives(self):
        with tempfile.TemporaryDirectory() as other:
            Path(other, "a.png").write_bytes(b"A")
            os.symlink(other, self.root / ".tmp")
            code, _, err = self.run_cli("--empty-tmp")
            self.assertEqual(code, 1)
            self.assertIn("FAIL: .tmp is a symlink", err)
            self.assertEqual(Path(other, "a.png").read_bytes(), b"A")

    def test_tmp_days_flag_controls_old_tmp(self):
        p = self.w(".tmp/old.txt")
        old = time.time() - 3 * 86400
        os.utime(p, (old, old))
        _, out, _ = self.run_cli("--tmp-days", "1")
        self.assertIn(".tmp/old.txt", out)
        _, out2, _ = self.run_cli("--tmp-days", "10")
        self.assertNotIn(".tmp/old.txt", out2)

    def test_help_lists_flags_and_warning(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                vcli.main(["tidy", "--help"])
        text = " ".join(out.getvalue().split())
        for flag in ("--tmp-days", "--apply", "--empty-tmp", "--include-mcp"):
            self.assertIn(flag, text)
        self.assertIn("do not run while a render is writing to .tmp/", text)



class TidySafetyTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name) / "proj"
        self.root.mkdir()

    def w(self, rel, data=b"x"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = vcli.main(["tidy", str(self.root), *argv])
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def _chmod(self, path, mode):
        os.chmod(path, mode)
        self.addCleanup(os.chmod, path, 0o755)

    # --- H1/H2/L4: MCP area ---
    def test_mixed_case_image_dir_is_mcp_area(self):
        self.w(".tmp/Image/render.png", b"UNIQUE PAID")
        r = tidy.empty_tmp(self.root)
        self.assertTrue((self.root / ".tmp/Image/render.png").exists())
        self.assertEqual(r["deleted"], [])
        self.assertEqual(r["kept_mcp"], [".tmp/Image/render.png"])

    def test_filename_with_separator_and_unique_bytes_survives(self):
        self.w(".tmp/image/a = keyframes/x.png", b"UNIQUE PAID")
        self.w("keyframes/x.png", b"OTHER")
        tidy.empty_tmp(self.root)
        self.assertTrue((self.root / ".tmp/image/a = keyframes/x.png").exists())

    def test_non_png_mcp_files_kept_by_default_and_deleted_with_include(self):
        for rel in (".tmp/image/r.gif", ".tmp/video/c.webm", ".tmp/image/notes.txt"):
            self.w(rel, b"PAID " + rel.encode())
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["deleted"], [])
        self.assertEqual(len(r["kept_mcp"]), 3)
        r2 = tidy.empty_tmp(self.root, include_mcp=True)
        self.assertEqual(len(r2["deleted"]), 3)
        self.assertEqual(list((self.root / ".tmp").iterdir()), [])

    def test_zero_byte_and_unreadable_mcp_files_kept(self):
        self.w(".tmp/image/empty.png", b"")
        locked = self.w(".tmp/video/locked.mp4", b"PAID")
        self._chmod(locked, 0o000)
        tidy.empty_tmp(self.root)
        self.assertTrue((self.root / ".tmp/image/empty.png").exists())
        self.assertTrue(os.path.lexists(locked))

    def test_true_copy_still_deleted_with_home_of(self):
        self.w("keyframes/s.png", b"PAID")
        self.w(".tmp/image/s.png", b"PAID")
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["deleted"], [".tmp/image/s.png"])
        self.assertEqual(r["home_of"], {".tmp/image/s.png": "keyframes/s.png"})

    def test_toctou_changed_home_and_new_render_survive(self):
        self.w("keyframes/a.png", b"PAID A")
        self.w(".tmp/image/a.png", b"PAID A")
        orig = tidy._HomeFiles.same_size
        root = self.root

        def racing(self_, size):
            found = list(orig(self_, size))
            (root / "keyframes/a.png").write_bytes(b"HOME REWRITTEN")
            (root / ".tmp/image/b.png").write_bytes(b"NEW PAID RENDER")
            return found
        tidy._HomeFiles.same_size = racing
        self.addCleanup(setattr, tidy._HomeFiles, "same_size", orig)
        r = tidy.empty_tmp(self.root)
        self.assertTrue((self.root / ".tmp/image/a.png").exists())
        self.assertTrue((self.root / ".tmp/image/b.png").exists())
        self.assertEqual(r["deleted"], [])

    def test_toctou_tmp_file_rewritten_after_index_survives(self):
        self.w("keyframes/a.png", b"PAID A")
        self.w(".tmp/image/a.png", b"PAID A")
        orig = tidy._HomeFiles.same_size
        root = self.root

        def racing(self_, size):
            found = list(orig(self_, size))
            (root / ".tmp/image/a.png").write_bytes(b"NEW PAID RENDER")
            return found
        tidy._HomeFiles.same_size = racing
        self.addCleanup(setattr, tidy._HomeFiles, "same_size", orig)
        tidy.empty_tmp(self.root)
        self.assertEqual((self.root / ".tmp/image/a.png").read_bytes(), b"NEW PAID RENDER")

    # --- M1 ---
    def test_vocache_kept_and_listed(self):
        self.w(".tmp/vocache-abc.mp3", b"PAID TTS")
        self.w(".tmp/junk.txt")
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["kept_tts"], [".tmp/vocache-abc.mp3"])
        self.assertEqual(r["deleted"], [".tmp/junk.txt"])
        r2 = tidy.empty_tmp(self.root, include_mcp=True)
        self.assertTrue((self.root / ".tmp/vocache-abc.mp3").exists())
        self.assertEqual(r2["kept_tts"], [".tmp/vocache-abc.mp3"])

    def test_cli_vocache_words(self):
        self.w(".tmp/vocache-abc.mp3", b"PAID TTS")
        code, out, _ = self.run_cli("--empty-tmp")
        self.assertEqual(code, 0)
        self.assertIn("paid TTS cache, kept: .tmp/vocache-abc.mp3", out)

    # --- M2 ---
    @unittest.skipIf(os.geteuid() == 0, "root ignores permissions")
    def test_empty_tmp_failed_file_is_reported_and_others_deleted(self):
        self.w(".tmp/locked/a.txt")
        self.w(".tmp/free.txt")
        self._chmod(self.root / ".tmp/locked", 0o500)
        r = tidy.empty_tmp(self.root)
        self.assertEqual([p for p, _ in r["failed"]], [".tmp/locked/a.txt"])
        self.assertEqual(r["deleted"], [".tmp/free.txt"])
        self.assertTrue((self.root / ".tmp/locked/a.txt").exists())

    @unittest.skipIf(os.geteuid() == 0, "root ignores permissions")
    def test_empty_tmp_folder_that_cannot_be_removed_is_failed(self):
        (self.root / ".tmp/outer/inner").mkdir(parents=True)
        self._chmod(self.root / ".tmp/outer", 0o500)
        r = tidy.empty_tmp(self.root)
        self.assertEqual([p for p, _ in r["failed"]], [".tmp/outer/inner"])

    @unittest.skipIf(os.geteuid() == 0, "root ignores permissions")
    def test_cli_failure_exit_1_and_all_actions_printed(self):
        self.w(".tmp/locked/a.txt")
        self.w(".tmp/free.txt")
        self._chmod(self.root / ".tmp/locked", 0o500)
        code, out, err = self.run_cli("--empty-tmp")
        self.assertEqual(code, 1)
        self.assertIn("deleted .tmp/free.txt", out)
        self.assertIn(".tmp/locked/a.txt", err)

    def test_apply_failure_reported_and_continues(self):
        self.w("_a/x.png", b"1")
        self.w("_b/y.png", b"2")
        arsip = self.root / "_arsip"
        arsip.mkdir()
        real_replace = os.replace

        def flaky(src, dst):
            if str(src).endswith("_a"):
                raise PermissionError(13, "denied")
            return real_replace(src, dst)
        orig = os.replace
        os.replace = flaky
        self.addCleanup(setattr, os, "replace", orig)
        moved = tidy.apply_unknown_dirs(self.root, tidy.scan(self.root))
        self.assertEqual([m[0] for m in moved], ["_b"])
        self.assertEqual([p for p, _ in moved.failed], ["_a"])
        self.assertTrue((self.root / "_a/x.png").exists())

    # --- L5 ---
    @unittest.skipIf(os.geteuid() == 0, "root ignores permissions")
    def test_unlistable_directory_is_reported_unreadable(self):
        self.w("keyframes/sub/a.png", b"1")
        self._chmod(self.root / "keyframes/sub", 0o000)
        r = tidy.scan(self.root)
        self.assertIn("keyframes/sub", r["unreadable"])

    # --- L7 ---
    def test_arsip_is_never_an_unknown_subdir_and_apply_leaves_it(self):
        self.w("_arsip/weird/z.png", b"PAID")
        self.w("_arsip/keyframe-a-v1-x.png", b"PAID2")
        r = tidy.scan(self.root)
        self.assertEqual(r["unknown_subdirs"], [])
        self.assertEqual(tidy.apply_unknown_dirs(self.root, r), [])
        self.assertTrue((self.root / "_arsip/weird/z.png").exists())


class TidyReviewFixesTest(unittest.TestCase):
    """GV-21 review: tool-made subfolders, case, .render-tmp, lazy home index."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)

    def w(self, rel, data=b"x"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def test_every_tool_made_subfolder_is_allowed(self):
        # ref/sumber(/scenes): vidkit ingest + scenes; vo/native: cast_voice.mjs;
        # vo/master: check_vo_duration.py convention; output/stems: make_stems.py.
        self.w("ref/sumber/source.mp4", b"a")
        self.w("ref/sumber/scenes/s1.png", b"b")
        self.w("vo/native/S03.mp3", b"c")
        self.w("vo/master/scene-19-narr.mp3", b"d")
        self.w("output/stems/voice.wav", b"e")
        r = tidy.scan(self.root)
        self.assertEqual(r["unknown_subdirs"], [])
        self.assertEqual(tidy.apply_unknown_dirs(self.root, r), [])
        self.assertTrue((self.root / "ref/sumber/scenes/s1.png").exists())

    def test_allowed_subdirs_do_not_hide_a_stray_beside_them(self):
        self.w("ref/sumber/a.png", b"a")
        self.w("keyframes/_up/b.png", b"b")
        self.w("vo/_old/c.mp3", b"c")
        self.assertEqual(tidy.scan(self.root)["unknown_subdirs"], ["keyframes/_up", "vo/_old"])

    def test_allowed_names_are_scoped_to_their_parent(self):
        self.w("clips/stems/a.mp4", b"a")
        self.w("keyframes/sumber/a.png", b"b")
        self.assertEqual(tidy.scan(self.root)["unknown_subdirs"],
                         ["clips/stems", "keyframes/sumber"])

    def test_top_level_names_compare_case_insensitively(self):
        for d in ("Clips", "KEYFRAMES", "Ref"):
            (self.root / d).mkdir()
        (self.root / "Fotos").mkdir()
        self.assertEqual(tidy.scan(self.root)["unknown_dirs"], ["Fotos"])

    def test_render_tmp_is_reported_and_apply_moves_it(self):
        self.w(".render-tmp/image/a.png", b"PAID")
        (self.root / ".git").mkdir()
        (self.root / ".cache").mkdir()
        r = tidy.scan(self.root)
        self.assertEqual(r["unknown_dirs"], [".render-tmp"])
        moved = tidy.apply_unknown_dirs(self.root, r)
        self.assertEqual(list(moved), [(".render-tmp", "_arsip/folder-.render-tmp")])
        self.assertEqual((self.root / "_arsip/folder-.render-tmp/image/a.png").read_bytes(), b"PAID")

    def test_unmoved_mcp_lists_every_file_empty_tmp_keeps(self):
        self.w(".tmp/image/a.png", b"1")
        self.w(".tmp/Video/notes.txt", b"2")
        self.w(".tmp/image/sub/data.json", b"3")
        self.w(".tmp/other.txt", b"4")
        listed = tidy.scan(self.root)["unmoved_mcp"]
        kept = tidy.empty_tmp(self.root)["kept_mcp"]
        self.assertEqual(sorted(listed), sorted(kept))
        self.assertEqual(len(kept), 3)

    def test_empty_tmp_hashes_no_home_file_when_mcp_area_is_empty(self):
        self.w("keyframes/a.png", b"home-a")
        self.w("clips/b.mp4", b"home-b")
        self.w(".tmp/scratch.txt", b"s")
        calls = []
        real = tidy._sha256
        tidy._sha256 = lambda p: (calls.append(str(p)), real(p))[1]
        self.addCleanup(setattr, tidy, "_sha256", real)
        r = tidy.empty_tmp(self.root)
        self.assertEqual(calls, [])
        self.assertEqual(r["deleted"], [".tmp/scratch.txt"])

    def test_empty_tmp_hashes_only_home_files_of_equal_size(self):
        self.w("keyframes/same.png", b"PAID-1")
        self.w("keyframes/other-size.png", b"much longer content here")
        self.w(".tmp/image/a.png", b"PAID-1")
        calls = []
        real = tidy._sha256
        tidy._sha256 = lambda p: (calls.append(Path(p).name), real(p))[1]
        self.addCleanup(setattr, tidy, "_sha256", real)
        r = tidy.empty_tmp(self.root)
        self.assertEqual(r["home_of"], {".tmp/image/a.png": "keyframes/same.png"})
        self.assertNotIn("other-size.png", calls)
        self.assertIn("same.png", calls)


def _png(path, size, drawbox=None, color="black"):
    vf = "null" if not drawbox else "drawbox=x=%d:y=%d:w=%d:h=%d:color=white:t=fill" % drawbox
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color={color}:s={size}",
            "-vf", vf, "-frames:v", "1", str(path)])


@requires_ffmpeg
class TextBoxTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)

    def test_exact_box_of_a_drawn_rectangle(self):
        p = Path(self.d.name) / "a.png"
        _png(p, "200x100", (20, 30, 50, 10))
        self.assertEqual(layout.text_box(p), [20, 30, 70, 40])

    def test_all_black_is_none(self):
        p = Path(self.d.name) / "b.png"
        _png(p, "64x64")
        self.assertIsNone(layout.text_box(p))

    def test_grey_background_finds_dark_and_light_marks(self):
        p = Path(self.d.name) / "g.png"
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=0x808080:s=100x60",
                "-vf", "drawbox=x=10:y=10:w=5:h=5:color=black:t=fill,"
                       "drawbox=x=60:y=40:w=5:h=5:color=white:t=fill", "-frames:v", "1", str(p)])
        self.assertEqual(layout.text_box(p, background=0x80), [10, 10, 65, 45])
        self.assertEqual(layout.text_box(p), [0, 0, 100, 60])

    def test_flat_grey_is_none_on_grey_background(self):
        p = Path(self.d.name) / "h.png"
        _png(p, "64x64", color="0x808080")
        self.assertIsNone(layout.text_box(p, background=0x80))

    def test_near_black_below_threshold_is_none(self):
        p = Path(self.d.name) / "c.png"
        _png(p, "64x64", color="0x101010")
        self.assertIsNone(layout.text_box(p))


@requires_ffmpeg
class TitleTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.img = Path(self.d.name) / "in.png"
        self.out = Path(self.d.name) / "out.png"
        _png(self.img, "1080x1920", color="white")

    def test_stamp_writes_output_and_box_inside_safe_area(self):
        box = title.stamp(self.img, "rumah 70 miliar", self.out, profile="short-organic")
        self.assertTrue(self.out.exists())
        self.assertEqual(ff.probe(self.out)["video"]["width"], 1080)
        sx0, sy0, sx1, sy1 = layout.safe_box(layout.load("short-organic"))
        self.assertGreaterEqual(box[0], sx0)
        self.assertGreaterEqual(box[1], sy0)
        self.assertLessEqual(box[2], sx1)
        self.assertLessEqual(box[3], sy1)
        self.assertNotEqual(self.img.read_bytes(), self.out.read_bytes())

    def test_box_json_has_uppercase_text_and_font(self):
        box = title.stamp(self.img, "rumah 70 miliar", self.out)
        doc = json.loads(Path(str(self.out) + ".box.json").read_text())
        self.assertEqual(doc["box"], box)
        self.assertEqual(doc["text"], "RUMAH 70 MILIAR")
        self.assertEqual(doc["profile"], "short-organic")
        self.assertTrue(Path(doc["font"]).exists())
        self.assertEqual(doc["source"], str(self.img.resolve()))
        self.assertTrue(os.path.isabs(doc["source"]))

    def test_box_is_centred_on_x_and_near_center_y(self):
        box = title.stamp(self.img, "RUMAH 70 MILIAR", self.out)
        sx0, _, sx1, _ = layout.safe_box(layout.load("short-organic"))
        self.assertAlmostEqual((box[0] + box[2]) / 2, (sx0 + sx1) / 2, delta=3)
        self.assertAlmostEqual((box[1] + box[3]) / 2, 0.38 * 1920, delta=6)

    def test_real_titles_that_were_refused_now_fit_inside_the_safe_area(self):
        sx0, sy0, sx1, sy1 = layout.safe_box(layout.load("short-organic"))
        for t in ("Alisha Superstar Sekolah", "Alisha Superstar Cilik", "Alisha Jadi Superstar",
                  "Alisha Si Superstar", "Alisha Jadi Bintang"):
            box = title.stamp(self.img, t, self.out)
            self.assertTrue(sx0 <= box[0] and box[2] <= sx1 and sy0 <= box[1] and box[3] <= sy1, (t, box))

    def test_five_words_can_use_three_lines(self):
        box = title.stamp(self.img, "ALISHA JADI SUPERSTAR SEKOLAH HARI", self.out)
        doc = json.loads(Path(str(self.out) + ".box.json").read_text())
        self.assertEqual(doc["box"], box)
        self.assertLessEqual(len(doc.get("lines", [])), 3)

    def test_split_lines_balances_up_to_three_lines(self):
        self.assertEqual(len(title.split_lines(["ALISHA", "SUPERSTAR", "SEKOLAH"])), 3)
        self.assertEqual(title.split_lines(["A", "B"]), ["A", "B"])
        self.assertLessEqual(len(title.split_lines(["HARI", "INI", "ALISHA", "JADI", "BINTANG"])), 3)

    def test_y_pct_override_moves_the_box(self):
        box = title.stamp(self.img, "RUMAH 70 MILIAR", self.out, y_pct=0.45)
        self.assertAlmostEqual((box[1] + box[3]) / 2, 0.45 * 1920, delta=6)

    def test_refuses_more_than_max_words(self):
        with self.assertRaisesRegex(ValueError, "words"):
            title.stamp(self.img, "satu dua tiga empat lima enam", self.out)
        self.assertFalse(self.out.exists())

    def test_refuses_empty_text(self):
        for t in ("", "   "):
            with self.assertRaisesRegex(ValueError, "empty"):
                title.stamp(self.img, t, self.out)

    def test_refuses_line_too_wide_at_min_font(self):
        with self.assertRaisesRegex(ValueError, r"usable width \d+ px.*widest line \d+ px at min font"):
            title.stamp(self.img, "ABCDEFGHIJKLMNOPQRST", self.out)
        self.assertFalse(self.out.exists())

    def test_refuses_non_9_16_input(self):
        wide = Path(self.d.name) / "wide.png"
        _png(wide, "1920x1080", color="white")
        with self.assertRaisesRegex(ValueError, "9:16"):
            title.stamp(wide, "HALO", self.out)

    def test_refuses_when_fc_match_is_missing(self):
        with mock.patch("tools.vidkit.title.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "fc-match"):
                title.stamp(self.img, "HALO", self.out)

    def test_refuses_when_no_font_resolves(self):
        fake = mock.Mock(returncode=0, stdout="Nonsense\n/no/such/font.ttf")
        real = title.subprocess.run

        def fake_run(argv, *a, **k):
            return fake if argv[0] == "fc-match" else real(argv, *a, **k)

        with mock.patch("tools.vidkit.title.subprocess.run", side_effect=fake_run):
            with self.assertRaisesRegex(ValueError, "font"):
                title.stamp(self.img, "HALO", self.out)

    def test_cli_prints_box_json_and_exit_0(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vcli.main(["title", str(self.img), "halo dunia", str(self.out)])
        self.assertEqual(rc, 0)
        self.assertIn(str(self.out) + ".box.json", Path(str(self.out) + ".box.json").as_posix())
        self.assertIn('"box"', buf.getvalue())

    def test_cli_maps_every_refusal_to_exit_2(self):
        wide = Path(self.d.name) / "wide.png"
        _png(wide, "1920x1080", color="white")
        cases = [(self.img, "a b c d e f"), (self.img, " "),
                 (self.img, "ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEF"), (wide, "HALO")]
        for img, text in cases:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = vcli.main(["title", str(img), text, str(self.out)])
            self.assertEqual(rc, 2, text)
            self.assertIn("FAIL", err.getvalue())

    def test_percent_and_brace_text_draws_every_line(self):
        # drawtext expands % sequences in textfile by default: "DISKON 50%" vanished (GV-23 review)
        for text, control in (("DISKON 50% HARI INI", "DISKON 50X HARI INI"), ("A %{pts} B", "A X{PTS} B")):
            got = title.stamp(self.img, text, self.out)
            want = title.stamp(self.img, control, self.out)
            self.assertAlmostEqual(got[1], want[1], delta=4, msg=(text, got, want))
            self.assertAlmostEqual(got[3], want[3], delta=4, msg=(text, got, want))
            self.assertGreaterEqual(got[2] - got[0], 0.8 * (want[2] - want[0]), (text, got, want))

    def test_cli_stdout_is_pure_json(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = vcli.main(["title", str(self.img), "halo dunia", str(self.out)])
        self.assertEqual(rc, 0)
        doc = json.loads(out.getvalue())
        self.assertEqual(doc["out"], str(self.out))
        self.assertIn("title font:", err.getvalue())

    def test_cli_unknown_profile_exit_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = vcli.main(["title", str(self.img), "HALO", str(self.out), "--profile", "nope"])
        self.assertEqual(rc, 2)
