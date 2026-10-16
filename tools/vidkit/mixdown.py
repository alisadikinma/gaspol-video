"""One-command final mix: voice + SFX cues + ducked music, loudness to a target, subtitles burned,
optional thumbnail on the first frames and as cover.

Everything project-specific lives in a plan json (see `run`). Cue times are absolute seconds in
the final timeline; the caller turns scene offsets into seconds.
"""
import os
import re
import shutil
import tempfile
from pathlib import Path

from . import color, cover, ff


def sfx_path(name):
    """A cue's `sfx` is either a file path or a library clip name (no extension)."""
    if os.path.exists(name):
        return name
    home = os.environ.get("GASPOL_VIDEO_HOME", os.path.expanduser("~/.gaspol-video"))
    p = Path(home) / "library" / "sfx" / "clips" / f"{name}.mp3"
    if not p.exists():
        raise FileNotFoundError(f"sfx '{name}' not found as a file or at {p}")
    return str(p)


def measure_lufs(path):
    err = ff.run(["ffmpeg", "-i", path, "-af", "ebur128", "-f", "null", "-"], capture_stderr=True)
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    if not found:
        raise ff.FFError("could not read loudness")
    return float(found[-1])


def build_sfx(cues, total, out):
    """Mix all cues into one stereo bed `total` seconds long."""
    if not cues:
        ff.ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", total, out)
        return out
    cmd, fc = [], []
    for i, c in enumerate(cues):
        cmd += ["-i", sfx_path(c["sfx"])]
        ms = int(round(float(c["at"]) * 1000))
        fc.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,volume={c.get('gain', 1.0)},adelay={ms}|{ms}[s{i}]")
    fc.append("".join(f"[s{i}]" for i in range(len(cues))) +
              f"amix=inputs={len(cues)}:normalize=0:duration=longest,apad=whole_dur={total},atrim=0:{total}[o]")
    ff.ffmpeg(*cmd, "-filter_complex", ";".join(fc), "-map", "[o]", out)
    return out


def build_music(music, total, out):
    """Loop the track, delay it to `start`, fade in/out, scale to `gain`; ends at `total`."""
    start = float(music.get("start", 0.0))
    fin, fout = float(music.get("fade_in", 1.5)), float(music.get("fade_out", 1.5))
    ms = int(round(start * 1000))
    length = total - start
    if length <= fin + fout:
        raise ValueError("music window is shorter than its fades")
    ff.ffmpeg("-stream_loop", -1, "-i", music["file"], "-t", length, "-af",
              f"aresample=44100,aformat=channel_layouts=stereo,afade=t=in:st=0:d={fin},"
              f"afade=t=out:st={length - fout}:d={fout},volume={music.get('gain', 0.55)},adelay={ms}|{ms},apad=whole_dur={total}",
              out)
    return out


def run(plan, workdir=None):
    """plan keys: video, out, total (optional), ass (optional), thumb (optional), hold (0.12),
    cues [{at, sfx, gain}], music {file, start, gain, fade_in, fade_out} (optional),
    lufs (-14), limit (0.78). Returns {'out', 'lufs_before', 'gain_db'}."""
    video, out = plan["video"], plan["out"]
    total = plan.get("total") or ff.probe(video)["duration"]
    work = Path(workdir or tempfile.mkdtemp(prefix="vidkit-mix-"))
    work.mkdir(parents=True, exist_ok=True)
    voice, sfx, mus, raw, fin = (str(work / n) for n in ("voice.wav", "sfx.wav", "music.wav", "raw.wav", "mix.wav"))
    ff.ffmpeg("-i", video, "-vn", "-ar", 44100, "-ac", 2, voice)
    build_sfx(plan.get("cues", []), total, sfx)
    if plan.get("music"):
        build_music(plan["music"], total, mus)
        fc = ("[0:a]asplit=2[v1][v2];[2:a][v2]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[md];"
              "[v1][1:a][md]amix=inputs=3:normalize=0:duration=first,aresample=44100[m]")
        ff.ffmpeg("-i", voice, "-i", sfx, "-i", mus, "-filter_complex", fc, "-map", "[m]", raw)
    else:
        ff.ffmpeg("-i", voice, "-i", sfx, "-filter_complex",
                  "[0:a][1:a]amix=inputs=2:normalize=0:duration=first,aresample=44100[m]", "-map", "[m]", raw)
    before = measure_lufs(raw)
    gain = plan.get("lufs", -14.0) - before
    # two steps: gain first, then a limiter, because AAC encoding overshoots a one-step peak
    ff.ffmpeg("-i", raw, "-af", f"volume={gain}dB,alimiter=limit={plan.get('limit', 0.78)}:level=false", fin)
    muxed = str(work / "muxed.mp4")
    chain = ([f"ass={plan['ass']}"] if plan.get("ass") else []) + [color.TAG_FILTER]
    vf = ["-vf", ",".join(chain)]
    ff.ffmpeg("-i", video, "-i", fin, *vf, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", 17,
              "-preset", "medium", "-pix_fmt", "yuv420p", *color.ENCODE_FLAGS, "-c:a", "aac", "-b:a", "192k",
              "-movflags", "+faststart", "-shortest", muxed)
    if plan.get("thumb"):
        cover.apply(muxed, plan["thumb"], out, None, plan.get("hold", 0.12))
    else:
        shutil.move(muxed, out)
    return {"out": out, "lufs_before": before, "gain_db": gain}
