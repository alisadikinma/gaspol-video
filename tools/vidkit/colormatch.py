"""Cross-clip colour match: measure each clip's mean RGB and nudge the outliers toward the
reference with a per-channel gain. Report first; applying is a separate, owner-approved step."""
import shutil
import statistics
import subprocess
from pathlib import Path

from . import color, ff


class ColorMatchError(RuntimeError):
    """A clip could not be measured or rewritten. The message names the file."""


NEAR_BLACK = 8.0


def _frame_rgb(path, t):
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
         "-vf", "scale=1:1:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    if proc.returncode != 0 or len(proc.stdout) < 3:
        return None
    return tuple(float(b) for b in proc.stdout[:3])


def mean_rgb(path, samples=5):
    """Mean (r, g, b), 0-255, over ``samples`` evenly spaced frames."""
    try:
        info = ff.probe(path)
    except (ff.FFError, OSError, ValueError) as exc:
        raise ColorMatchError(f"{path}: cannot read ({exc})") from exc
    if not info["video"] or not info["duration"]:
        raise ColorMatchError(f"{path}: no decodable video stream")
    frames = []
    for i in range(samples):
        f = _frame_rgb(path, info["duration"] * (i + 0.5) / samples)
        if f is not None:
            frames.append(f)
    if not frames:
        raise ColorMatchError(f"{path}: no frame could be decoded")
    return tuple(sum(f[c] for f in frames) / len(frames) for c in range(3))


def plan(paths, reference=None, max_gain=0.15):
    """Per-clip gain toward the reference (a clip path, or the per-channel median)."""
    paths = [str(p) for p in paths]
    means = {p: mean_rgb(p) for p in paths}
    if reference is not None:
        if not Path(reference).exists():
            raise ColorMatchError(f"{reference}: reference file missing")
        ref = mean_rgb(reference)
    else:
        ref = tuple(statistics.median(m[c] for m in means.values()) for c in range(3))
    lo, hi = 1 - max_gain, 1 + max_gain
    rows = []
    for p in paths:
        m = means[p]
        row = {"file": p, "mean": m}
        near_black = sum(m) / 3 < NEAR_BLACK
        if near_black:
            row["suspect"] = "near-black"
        if near_black or (len(paths) == 1 and reference is None):
            gain = (1.0, 1.0, 1.0)
        else:
            gain = tuple(min(hi, max(lo, ref[c] / m[c])) if m[c] > 0 else 1.0 for c in range(3))
        row["gain"] = gain
        row["delta"] = max(abs(g - 1) for g in gain)
        rows.append(row)
    return rows


def apply(path, out, gain):
    """Rewrite ``path`` into ``out`` with the channel gain; audio is stream-copied."""
    if Path(path).resolve() == Path(out).resolve():
        raise ColorMatchError(f"{path}: refusing to overwrite the source")
    gr, gg, gb = gain
    ff.ensure_parent(out)
    vf = f"colorchannelmixer=rr={gr:.5f}:gg={gg:.5f}:bb={gb:.5f},{color.TAG_FILTER}"
    try:
        ff.ffmpeg("-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-vf", vf,
                  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", *color.ENCODE_FLAGS,
                  "-c:a", "copy", str(out))
    except ff.FFError as exc:
        raise ColorMatchError(f"{path}: {exc}") from exc
    return str(out)


def spread(means):
    """Largest per-channel max-min across the given mean triples."""
    return max(max(m[c] for m in means) - min(m[c] for m in means) for c in range(3))


def _fmt(v):
    return "%5.1f,%5.1f,%5.1f" % tuple(v)


def report(paths, reference=None, max_gain=0.15, min_delta=0.03, apply_dir=None):
    """Plan, optionally write into ``apply_dir``; returns the printable report.

    Only clips with delta >= min_delta are rewritten; the rest are copied untouched.
    The sources are never written."""
    paths = [str(p) for p in paths]
    out_paths = {}
    if apply_dir is not None:
        outdir = Path(apply_dir).resolve()
        for p in paths:
            target = outdir / Path(p).name
            if target == Path(p).resolve():
                raise ColorMatchError(f"{p}: --apply folder would overwrite the source")
            out_paths[p] = target
        if len(set(out_paths.values())) != len(paths):
            raise ColorMatchError("two clips share a file name; --apply would overwrite one")
    rows = plan(paths, reference, max_gain)
    lines = [f"{'file':<28} {'mean R,G,B':<20} {'gain R,G,B':<20} {'delta':>6}  note"]
    for r in rows:
        if apply_dir is None:
            note = ""
        elif r["delta"] >= min_delta:
            note = "rewritten"
        else:
            note = "copied"
        if r.get("suspect"):
            note = (note + " " if note else "") + "suspect: " + r["suspect"]
        lines.append(f"{Path(r['file']).name:<28} {_fmt(r['mean']):<20} "
                     f"{'%.3f,%.3f,%.3f' % r['gain']:<20} {r['delta']:>6.3f}  {note}".rstrip())
    summary = f"spread before: {spread([r['mean'] for r in rows]):.1f}"
    if apply_dir is not None:
        Path(apply_dir).mkdir(parents=True, exist_ok=True)
        for r in rows:
            target = out_paths[r["file"]]
            if r["delta"] >= min_delta:
                apply(r["file"], target, r["gain"])
            else:
                shutil.copyfile(r["file"], target)
        after = spread([mean_rgb(str(out_paths[r["file"]])) for r in rows])
        summary += f"  after: {after:.1f}"
    else:
        summary += "  (report only, nothing written)"
    return "\n".join(lines + [summary])
