"""``python3 -m tools.vidkit <command>`` from the plugin root."""
import argparse
import json
import sys

from . import audiostudy, beats, colormatch, cover, ff, gates, grain, ingest, join, karaoke, layout, mixdown, loudness, patch, placevoice, prosody, reframe, sheet, tighten, speech, synth, tidy, title, track, unwhite


def _json(p):
    with open(p) as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vidkit", description="Reusable video assembly helpers.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="download a video link with yt-dlp")
    s.add_argument("url")
    s.add_argument("out_dir")
    s.add_argument("--name", default="source")
    s.add_argument("--cookies-from-browser", default=None,
                   help="browser whose login cookies yt-dlp reads (chrome, safari, firefox); Instagram needs it")
    s.add_argument("--section", help="download only START-END seconds, e.g. 1362.5-1366")

    s = sub.add_parser("scenes", help="cut a video into scenes with first/mid/last stills + scenes.json")
    s.add_argument("video")
    s.add_argument("out_dir")
    s.add_argument("--threshold", type=float, default=0.3)
    s.add_argument("--min-len", type=float, default=0.6)

    s = sub.add_parser("prosody", help="delivery of a voice: pace per sentence, pauses, stressed words (mono wav + words json)")
    s.add_argument("wav")
    s.add_argument("words", help="AssemblyAI words json, [[word,start,end],...] or [{word,start,end}]")
    s.add_argument("--out", help="write the full report as JSON")
    s.add_argument("--min-range-st", type=float, help="gate: exit 1 if the pitch range is below this (flat take)")
    s.add_argument("--min-wps", type=float, help="gate: exit 1 if the pace is below this many words/s")
    s.add_argument("--max-pause", type=float, help="gate: exit 1 if the mean pause between sentences is above this")
    s.add_argument("--stress-z", type=float, default=1.0)

    s = sub.add_parser("grain", help="add fine moving film grain (generated skin looks less airbrushed)")
    s.add_argument("src")
    s.add_argument("out")
    s.add_argument("--strength", type=int, default=7, help="1-40; 6-8 subtle, 14 clearly visible")

    s = sub.add_parser("reframe", help="cut a 9:16 window from wide footage, panning to follow the subject")
    s.add_argument("src")
    s.add_argument("out")
    s.add_argument("--keys", help="T:CX,... subject centre as fraction of width, e.g. 0:0.4,2:0.7")
    s.add_argument("--fit", action="store_true", help="whole frame over a blurred copy (subject wider than a 9:16 window)")
    s.add_argument("--zoom", type=float, default=1.0, help=">= 1; tighter window")
    s.add_argument("--size", default="1080x1920")

    s = sub.add_parser("tighten", help="cut gaps between words longer than --max-gap down to --keep (word timings)")
    s.add_argument("audio")
    s.add_argument("words", help="AssemblyAI words json, [[word,start,end],...] or [{word,start,end}]")
    s.add_argument("out")
    s.add_argument("--max-gap", type=float, default=0.3)
    s.add_argument("--keep", type=float, default=0.2)

    s = sub.add_parser("placevoice", help="seat a converted voice into its clip: ambience bed from the gaps, mic space, level match")
    s.add_argument("clip")
    s.add_argument("voice")
    s.add_argument("words", help="word timings of the speech in the clip (json)")
    s.add_argument("out")
    s.add_argument("--space", default="outdoor", choices=sorted(placevoice.SPACES))
    s.add_argument("--bed", default="gaps", choices=placevoice.BEDS,
                   help="gaps = loop quiet gaps (default); stems = Demucs background stem, experimental")
    s.add_argument("--bed-db", type=float, default=None, help="bed level vs its source (default 0 stems, -6 gaps)")

    s = sub.add_parser("audiostudy", help="onsets, tempo, loudness, energy and word/cut relation of one clip")
    s.add_argument("clip")
    s.add_argument("--words", help="words json [[word,start,end],...]")
    s.add_argument("--out", help="write the full report as JSON")

    s = sub.add_parser("karaoke", help="words json [[word,start,end],...] -> karaoke .ass (+ centre watermark)")
    s.add_argument("words")
    s.add_argument("out")
    s.add_argument("--total", type=float, required=True, help="video length, seconds")
    s.add_argument("--watermark")
    s.add_argument("--opacity", type=float, default=0.12)
    s.add_argument("--font", default="Helvetica Neue")
    s.add_argument("--margin-v", type=int, default=None, help="overrides the profile (no profile: 360)")
    s.add_argument("--profile", default="short-organic",
                   help="layout profile from media/layout-profiles.json, or 'none' for the old fixed defaults")

    s = sub.add_parser("title", help="stamp a cover title on a 9:16 image inside the safe area; writes <out>.box.json")
    s.add_argument("img")
    s.add_argument("text")
    s.add_argument("out")
    s.add_argument("--profile", default="short-organic", help="layout profile from media/layout-profiles.json")
    s.add_argument("--y-pct", type=float, default=None, help="title centre Y as a share of the height (default: profile)")

    s = sub.add_parser("cover", help="burn .ass, thumbnail on the first frames, thumbnail as mp4 cover")
    s.add_argument("video")
    s.add_argument("thumb")
    s.add_argument("out")
    s.add_argument("--ass")
    s.add_argument("--hold", type=float, default=0.12)

    s = sub.add_parser("unwhite", help="key the white box out of a logo (for blending onto a surface)")
    s.add_argument("src")
    s.add_argument("out")

    s = sub.add_parser("mixdown", help="final mix from a plan json: voice + sfx cues + ducked music, -14 LUFS, subs, thumbnail")
    s.add_argument("plan")

    s = sub.add_parser("tidy", help="report stray folders, duplicates, stale entries, old .tmp; "
                                    "optionally move strays to _arsip/ and empty .tmp/ "
                                    "(do not run while a render is writing to .tmp/)",
                       description="With no flag this only reports and changes nothing. "
                                   "Warning: do not run while a render is writing to .tmp/.")
    s.add_argument("project")
    s.add_argument("--tmp-days", type=int, default=7, help="a .tmp file older than N days counts as old (default 7)")
    s.add_argument("--apply", action="store_true", help="move stray folders and subfolders into _arsip/folder-...")
    s.add_argument("--empty-tmp", action="store_true",
                   help="delete the content of .tmp/ (paid MCP renders with no home copy are kept)")
    s.add_argument("--include-mcp", action="store_true",
                   help="with --empty-tmp, also delete paid MCP renders that have no home copy")

    s = sub.add_parser("probe", help="print stream facts as JSON")
    s.add_argument("file")

    s = sub.add_parser("gate-av", help="fail if video and audio length differ")
    s.add_argument("file")
    s.add_argument("--tolerance", type=float, default=gates.AV_TOLERANCE_S)

    s = sub.add_parser("gate-uniform", help="fail if clips differ in sample rate or channels")
    s.add_argument("files", nargs="+")

    s = sub.add_parser("concat", help="hard-cut join, stream copy")
    s.add_argument("out")
    s.add_argument("clips", nargs="+")

    s = sub.add_parser("xfade", help="dissolve join; audio kept whole and mixed")
    s.add_argument("out")
    s.add_argument("clips", nargs="+")
    s.add_argument("--transitions", type=float, nargs="+", required=True, help="one overlap per seam, seconds")
    s.add_argument("--effect", default="fade")

    s = sub.add_parser("freeze", help="freeze a box of a clip to one frame")
    s.add_argument("src")
    s.add_argument("out")
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)
    s.add_argument("w", type=int)
    s.add_argument("h", type=int)
    s.add_argument("--frame", type=int, default=0)

    s = sub.add_parser("sheet", help="contact sheet of one clip")
    s.add_argument("clip")
    s.add_argument("out")
    s.add_argument("--frames", type=int, default=5)

    s = sub.add_parser("montage", help="tile image files")
    s.add_argument("out")
    s.add_argument("images", nargs="+")
    s.add_argument("--cols", type=int, default=2)

    s = sub.add_parser("synth", help="generate a notification or alarm wav")
    s.add_argument("kind", choices=["notification", "alarm"])
    s.add_argument("out")

    s = sub.add_parser("words", help="word timings from an ElevenLabs alignment json")
    s.add_argument("alignment")

    s = sub.add_parser("colormatch", help="report (or --apply) a per-channel gain that pulls clips toward one colour")
    s.add_argument("clips", nargs="+")
    s.add_argument("--reference", help="match to this clip; default is the median of all clips")
    s.add_argument("--max-gain", type=float, default=0.15)
    s.add_argument("--min-delta", type=float, default=0.03)
    s.add_argument("--apply", metavar="OUTDIR", help="write matched clips here; without it nothing is written")
    s.add_argument("--force", action="store_true", help="with --apply, overwrite files already in OUTDIR")

    s = sub.add_parser("beats", help="beat times of a music file, as JSON seconds")
    s.add_argument("file")
    s.add_argument("--min-gap", type=float, default=0.25)
    s.add_argument("--threshold", type=float, default=1.5)

    s = sub.add_parser("energy", help="dB envelope of a file between two times")
    s.add_argument("file")
    s.add_argument("start", type=float)
    s.add_argument("end", type=float)

    s = sub.add_parser("normalize", help="two-pass loudnorm, audio trimmed to picture")
    s.add_argument("src")
    s.add_argument("out")
    s.add_argument("--profile", default="default",
                   help="named target from media/loudness-profiles.json (default: default); exit 2 if unknown or unsourced")
    s.add_argument("--lufs", type=float, default=None,
                   help="explicit target; wins over --profile for the loudness (true peak still comes from the profile)")

    s = sub.add_parser("smooth-track", help="median-filter a tracked-box json in place")
    s.add_argument("track_json")
    s.add_argument("--window", type=int, default=9)
    s.add_argument("--shrink", type=float, default=1.0)

    s = sub.add_parser("bond", help="bond a transparent print onto cloth (needs cv2)")
    s.add_argument("clip")
    s.add_argument("out")
    s.add_argument("--print", dest="print_png", required=True)
    s.add_argument("--cx", type=float, required=True)
    s.add_argument("--top", type=float, required=True)
    s.add_argument("--width", type=float, required=True)
    s.add_argument("--rot", type=float, default=-1.2)

    a = ap.parse_args(argv)
    rc = 0
    if a.cmd == "tidy" and a.include_mcp and not a.empty_tmp:
        ap.error("--include-mcp needs --empty-tmp")
    try:
        if a.cmd == "ingest":
            print(ingest.download(a.url, a.out_dir, a.name, a.cookies_from_browser, a.section))
        elif a.cmd == "scenes":
            rows = ingest.split_scenes(a.video, a.out_dir, a.threshold, a.min_len)
            print(f"{len(rows)} scenes -> {a.out_dir}/scenes.json")
        elif a.cmd == "prosody":
            rep = prosody.report(a.wav, prosody.load_words(a.words), a.stress_z)
            if a.out:
                with open(a.out, "w") as fh:
                    json.dump(rep, fh, indent=1, ensure_ascii=False)
            o = rep["overall"]
            print(f"{a.wav} {o['words']} words {o['wps']} w/s, pause {o['pause_mean_s']} s, "
                  f"pitch {o['pitch_median_hz']} Hz range {o['pitch_range_st']} st, "
                  f"stressed: {' '.join(e['word'] for e in rep['emphasis'])}")
            for problem in prosody.gate(rep, a.min_range_st, a.min_wps, a.max_pause):
                print(f"FAIL: {problem}", file=sys.stderr)
                rc = 1
        elif a.cmd == "grain":
            grain.apply(a.src, a.out, a.strength)
            print(f"{a.out}: grain {a.strength}")
        elif a.cmd == "reframe":
            sw, sh = (int(v) for v in a.size.lower().split("x"))
            if a.fit:
                reframe.fit(a.src, a.out, (sw, sh))
                print(f"{a.out}: fit over blur")
            elif not a.keys:
                raise ValueError("reframe needs --keys or --fit")
            else:
                r = reframe.apply(a.src, a.out, reframe.parse_keys(a.keys), a.zoom, (sw, sh))
                print(f"{a.out}: window {r['window'][0]}x{r['window'][1]}, {len(r['keys'])} key(s)")
        elif a.cmd == "tighten":
            r = tighten.apply(a.audio, prosody.load_words(a.words), a.out, a.max_gap, a.keep)
            print(f"{a.out}: {r['cuts']} gap(s) cut, {r['removed_s']} s removed, {r['duration']} s")
        elif a.cmd == "placevoice":
            r = placevoice.place(a.clip, a.voice, prosody.load_words(a.words), a.out, a.space, a.bed_db, bed=a.bed)
            print(f"{a.out}: voice {r['gain_db']:+} dB, bed {r['bed']} ({r['bed_s']} s), space {r['space']}")
        elif a.cmd == "audiostudy":
            rep = audiostudy.study(a.clip, _json(a.words) if a.words else None)
            if a.out:
                with open(a.out, "w") as fh:
                    json.dump(rep, fh, indent=1)
            bpm = rep["tempo_bpm"]
            lufs = rep["loudness_lufs"]
            loud = "silent" if lufs is None else f"{lufs:.1f} LUFS"
            print(f"{a.clip} {rep['duration']:.1f}s {loud} "
                  f"{len(rep['onsets'])} onsets {'%.0f BPM' % bpm if bpm else 'no tempo'}")
        elif a.cmd == "karaoke":
            words = [tuple(w) for w in _json(a.words)]
            try:
                prof = None if a.profile == "none" else layout.load(a.profile)
            except KeyError as exc:
                print(str(exc.args[0]), file=sys.stderr)
                return 2
            ass = karaoke.build_ass(words, a.total, a.watermark, a.opacity, a.font,
                                    margin_v=a.margin_v, profile=prof)
            with open(a.out, "w") as fh:
                fh.write(ass)
            print(a.out)
        elif a.cmd == "title":
            try:
                box = title.stamp(a.img, a.text, a.out, a.profile, a.y_pct)
            except (KeyError, ValueError) as exc:
                print(f"FAIL: {exc.args[0] if isinstance(exc, KeyError) else exc}", file=sys.stderr)
                return 2
            print(json.dumps({"box": box, "out": a.out}))
        elif a.cmd == "cover":
            print(cover.apply(a.video, a.thumb, a.out, a.ass, a.hold))
        elif a.cmd == "unwhite":
            print(unwhite.unwhite(a.src, a.out))
        elif a.cmd == "mixdown":
            r = mixdown.run(_json(a.plan))
            print(f"ok {r['out']} (was {r['lufs_before']:.1f} LUFS, gain {r['gain_db']:+.1f} dB)")
        elif a.cmd == "tidy":
            if not (a.apply or a.empty_tmp):
                print(tidy.format_report(tidy.scan(a.project, a.tmp_days)))
            if a.apply:
                moved = tidy.apply_unknown_dirs(a.project, tidy.scan(a.project, a.tmp_days))
                for src, dst in moved:
                    print(f"moved {src} -> {dst}")
                for path, err in moved.failed:
                    print(f"failed {path}: {err}", file=sys.stderr)
                    rc = 1
                if not moved and not moved.failed:
                    print("nothing to move")
            if a.empty_tmp:
                r = tidy.empty_tmp(a.project, a.include_mcp)
                for path in r["deleted"]:
                    home = r["home_of"].get(path)
                    print(f"deleted {path} (copy of {home})" if home else f"deleted {path}")
                for path in r["kept_mcp"]:
                    print(f"paid render not moved yet, kept: {path}")
                for path in r["kept_tts"]:
                    print(f"paid TTS cache, kept: {path}")
                for path, err in r["failed"]:
                    print(f"failed {path}: {err}", file=sys.stderr)
                    rc = 1
                print(f"emptied .tmp: {len(r['deleted'])} deleted, "
                      f"{len(r['kept_mcp']) + len(r['kept_tts'])} kept, {len(r['failed'])} failed")
        elif a.cmd == "probe":
            print(json.dumps(ff.probe(a.file), indent=1))
        elif a.cmd == "gate-av":
            v, au = gates.gate_av(a.file, a.tolerance)
            print(f"ok video {v:.3f}s audio {au:.3f}s")
        elif a.cmd == "gate-uniform":
            sr, ch = gates.gate_uniform(a.files)
            print(f"ok {len(a.files)} files, {sr} Hz, {ch} ch")
        elif a.cmd == "concat":
            print(join.concat_copy(a.clips, a.out))
        elif a.cmd == "xfade":
            print(json.dumps(join.join_xfade(a.clips, a.out, a.transitions, a.effect), indent=1))
        elif a.cmd == "freeze":
            print(patch.freeze_box(a.src, a.out, a.x, a.y, a.w, a.h, a.frame))
        elif a.cmd == "sheet":
            print(sheet.contact_sheet(a.clip, a.out, a.frames))
        elif a.cmd == "montage":
            print(sheet.montage(a.images, a.out, a.cols))
        elif a.cmd == "synth":
            out = getattr(synth, a.kind)(a.out)
            print(out, "peak %.1f dB rms %.1f dB" % synth.measure(out))
        elif a.cmd == "words":
            for w in speech.words_from_alignment(_json(a.alignment)):
                print(f"{w['word']}@{w['start']:.2f}-{w['end']:.2f}")
        elif a.cmd == "colormatch":
            print(colormatch.report(a.clips, a.reference, a.max_gain, a.min_delta, a.apply, a.force))
        elif a.cmd == "beats":
            print(json.dumps(beats.detect(a.file, min_gap_s=a.min_gap, threshold=a.threshold)))
        elif a.cmd == "energy":
            print(" ".join(f"{t:.2f}:{db:g}" for t, db in speech.energy_db(a.file, a.start, a.end)))
        elif a.cmd == "normalize":
            prof = loudness.profile(a.profile)
            lufs = prof["lufs"] if a.lufs is None else a.lufs
            print(f"profile {a.profile}: {lufs:g} LUFS, {prof['true_peak']:g} dBTP"
                  + (" (--lufs overrides the profile)" if a.lufs is not None else ""))
            print(json.dumps(loudness.normalize(a.src, a.out, lufs, prof["true_peak"]), indent=1))
        elif a.cmd == "smooth-track":
            pts = _json(a.track_json)
            with open(a.track_json, "w") as fh:
                json.dump(track.smooth_track(pts, a.window, a.shrink), fh, indent=1)
            print(f"{a.track_json}: {len(pts)} points smoothed")
        elif a.cmd == "bond":
            from . import bond
            print(json.dumps(bond.bond_print(a.clip, a.out, a.print_png, a.cx, a.top, a.width, a.rot)))
    except loudness.ProfileError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    except (gates.GateError, ff.FFError, beats.BeatError, ValueError, RuntimeError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
