"""``python3 -m tools.vidkit <command>`` from the plugin root."""
import argparse
import json
import sys

from . import ff, gates, join, loudness, patch, sheet, speech, synth, track


def _json(p):
    with open(p) as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vidkit", description="Reusable video assembly helpers.")
    sub = ap.add_subparsers(dest="cmd", required=True)

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

    s = sub.add_parser("energy", help="dB envelope of a file between two times")
    s.add_argument("file")
    s.add_argument("start", type=float)
    s.add_argument("end", type=float)

    s = sub.add_parser("normalize", help="two-pass loudnorm, audio trimmed to picture")
    s.add_argument("src")
    s.add_argument("out")
    s.add_argument("--lufs", type=float, default=loudness.LUFS)

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
    try:
        if a.cmd == "probe":
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
        elif a.cmd == "energy":
            print(" ".join(f"{t:.2f}:{db:g}" for t, db in speech.energy_db(a.file, a.start, a.end)))
        elif a.cmd == "normalize":
            print(json.dumps(loudness.normalize(a.src, a.out, a.lufs), indent=1))
        elif a.cmd == "smooth-track":
            pts = _json(a.track_json)
            with open(a.track_json, "w") as fh:
                json.dump(track.smooth_track(pts, a.window, a.shrink), fh, indent=1)
            print(f"{a.track_json}: {len(pts)} points smoothed")
        elif a.cmd == "bond":
            from . import bond
            print(json.dumps(bond.bond_print(a.clip, a.out, a.print_png, a.cx, a.top, a.width, a.rot)))
    except (gates.GateError, ff.FFError, ValueError, RuntimeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
