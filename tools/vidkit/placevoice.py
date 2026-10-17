"""Seat a converted (dry, studio-clean) voice back into its scene so it does not sound pasted on.

Speech-to-speech returns a voice with no room and no background: on an outdoor clip it reads as a
dub. This puts the scene back under it:
  1. ambience bed, two ways (`bed=`):
     - "gaps" (default, owner-approved by ear): the clip's own audio from the gaps where nobody speaks, looped (pink noise at a low
       level when there is no usable gap). A gap counts only where it is also QUIET: video models
       add laughs and breaths that ASR has no word for, and looping a laugh in the old voice under
       the new one is worse than no bed,
     - "stems" (opt-in, NOT the default): Demucs splits the clip's audio and its background stem
       runs under the whole clip. Field case: on a 4 s VEO line this sounded WORSE than a 0.38 s
       looped gap, so it stays an experiment the owner must hear before it is kept,
  2. space: body EQ + light compression, then a faint early reflection,
  3. level: match the PROCESSED voice's RMS to the original voice inside the speech spans.
Video is copied untouched; the output audio is cut to the picture.
"""
import re
import shutil
import statistics
import tempfile
from pathlib import Path

from . import ff, speech

# Body EQ (low-mid warmth, presence) + light compression so a converted voice keeps its weight
# ("kempes" = deflated was the first field complaint), then early reflections. Echo gains are 1.0:
# an out_gain under 1 silently drops the level ~5 dB. Level is matched AFTER this chain anyway.
_BODY = ("highpass=f=60,equalizer=f=160:t=q:w=1:g=3,equalizer=f=3000:t=q:w=1.2:g=2,"
         "acompressor=threshold=-24dB:ratio=3:attack=3:release=60:makeup=2")
SPACES = {
    "outdoor": _BODY + ",aecho=1.0:1.0:45|90:0.08|0.03",   # one faint slap, no tail
    "room": _BODY + ",aecho=1.0:1.0:18|32|51:0.18|0.11|0.06",
    "dry": _BODY,
}


def voice_chain(space):
    if space not in SPACES:
        raise ValueError(f"space must be one of {sorted(SPACES)}, got {space!r}")
    return SPACES[space]


def ambience_gaps(words, duration, min_gap=0.3, pad=0.05):
    """Spans with no speech (padded away from words), each at least `min_gap` long."""
    gaps, t = [], 0.0
    for _, s, e in sorted(words, key=lambda w: w[1]):
        a, b = t, s - pad
        if b - a >= min_gap:
            gaps.append((round(a, 3), round(b, 3)))
        t = max(t, e + pad)
    if duration - t >= min_gap:
        gaps.append((round(t, 3), round(duration, 3)))
    return gaps


def quiet_runs(env, max_db, min_len=0.3, smooth=5):
    """[(t, db)] at a fixed hop -> spans where the envelope is <= max_db, each >= min_len.

    The envelope is median-smoothed over `smooth` frames first: real ambience flickers, and one
    10 ms spike must not split a usable quiet stretch. smooth=1 = raw frames.
    """
    if smooth > 1:
        half = smooth // 2
        env = [(t, statistics.median(d for _, d in env[max(0, i - half): i + half + 1]))
               for i, (t, _) in enumerate(env)]
    runs, start, hop = [], None, (env[1][0] - env[0][0]) if len(env) > 1 else 0.01
    for t, db in env:
        if db <= max_db:
            start = t if start is None else start
        elif start is not None:
            if t - start >= min_len:
                runs.append((round(start, 3), round(t, 3)))
            start = None
    if start is not None and env[-1][0] + hop - start >= min_len:
        runs.append((round(start, 3), round(env[-1][0] + hop, 3)))
    return runs


def intersect(a_spans, b_spans, min_len=0.3):
    out = []
    for a0, a1 in a_spans:
        for b0, b1 in b_spans:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo >= min_len:
                out.append((round(lo, 3), round(hi, 3)))
    return out


def _rms_db(path, a, b):
    err = ff.run(["ffmpeg", "-v", "info", "-i", path, "-af",
                  f"atrim={a}:{b},astats=measure_overall=RMS_level:measure_perchannel=none",
                  "-f", "null", "-"], capture_stderr=True)
    vals = [float(v) for v in re.findall(r"RMS level dB:\s*(-?[\d.]+)", err)]
    return vals[-1] if vals else None


BEDS = ("gaps", "stems")


def separate(clip, work_dir, model="htdemucs"):
    """Demucs two-stem split of `clip`'s audio. Returns the path of the background stem
    (`no_vocals.wav`). Install once: `uv tool install --python 3.11 demucs --with soundfile`."""
    exe = shutil.which("demucs")
    if exe is None:
        raise ff.FFMissing("demucs is not on PATH (uv tool install --python 3.11 demucs --with soundfile)")
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "mix.wav"
    ff.ffmpeg("-i", clip, "-vn", "-ac", "2", "-ar", "44100", wav)
    ff.run([exe, "--two-stems", "vocals", "-n", model, "-o", str(work), str(wav)])
    bg = work / model / "mix" / "no_vocals.wav"
    if not bg.exists():
        raise ff.FFError(f"demucs finished but {bg} does not exist")
    return str(bg)


def place(clip, voice, words, out, space="outdoor", bed_db=None, min_gap=0.3, quiet_below_db=12.0,
          bed="gaps", separator=separate):
    """Write `out` = clip video + placed voice + ambience bed. `bed_db` is the bed level relative
    to its source (default 0 for stems, the real level; -6 for a looped gap); a gap frame joins the
    bed only when it is `quiet_below_db` under the median speech level.
    Returns {"gain_db", "bed_s", "space", "bed"}."""
    if bed not in BEDS:
        raise ValueError(f"bed must be one of {BEDS}, got {bed!r}")
    dur = ff.probe(clip)["duration"]
    spans = [(s, e) for _, s, e in words]
    a, b = min(s for s, _ in spans), max(e for _, e in spans)
    shaped = f"{out}.voice.wav"  # the chain changes level, so measure after it
    ff.ffmpeg("-i", voice, "-af", voice_chain(space), shaped)
    with tempfile.TemporaryDirectory() as work:
        try:
            before, after = _rms_db(clip, a, b), _rms_db(shaped, a, b)
            gain = round(before - after, 2) if before is not None and after is not None else 0.0
            if bed == "stems":
                stem = separator(clip, work)
                _mix(clip, shaped, out, None, dur, gain, 0.0 if bed_db is None else bed_db, stem=stem)
                bed_s = round(dur, 3)
            else:
                env = speech.energy_db(clip, 0, dur)
                loud = [db for t, db in env if any(s <= t <= e for s, e in spans)]
                max_db = (statistics.median(loud) if loud else max(db for _, db in env)) - quiet_below_db
                gaps = intersect(ambience_gaps(words, dur, min_gap), quiet_runs(env, max_db, min_gap), min_gap)
                _mix(clip, shaped, out, gaps, dur, gain, -6.0 if bed_db is None else bed_db)
                bed_s = round(sum(y - x for x, y in gaps), 3)
        finally:
            Path(shaped).unlink(missing_ok=True)
    return {"gain_db": gain, "bed_s": bed_s, "space": space, "bed": bed}


def _mix(clip, shaped, out, gaps, dur, gain, bed_db, stem=None):
    if stem is not None:
        graph = (f"[2:a]aformat=channel_layouts=mono,atrim=0:{dur},volume={bed_db}dB[bed];"
                 f"[1:a]volume={gain}dB[v];"
                 f"[v][bed]amix=inputs=2:duration=first:normalize=0,atrim=0:{dur}[a]")
        ff.ffmpeg("-i", clip, "-i", shaped, "-i", stem, "-filter_complex", graph,
                  "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", out)
        return
    if gaps:
        parts = "".join(f"[0:a]atrim={x}:{y},asetpts=N/SR/TB[g{i}];" for i, (x, y) in enumerate(gaps))
        bed = (parts + "".join(f"[g{i}]" for i in range(len(gaps)))
               + f"concat=n={len(gaps)}:v=0:a=1,aloop=loop=-1:size=2e9,atrim=0:{dur},volume={bed_db}dB[bed];")
    else:
        bed = f"anoisesrc=d={dur}:c=pink:a=0.003,aformat=channel_layouts=mono[bed];"
    graph = (bed + f"[1:a]volume={gain}dB[v];"
             f"[v][bed]amix=inputs=2:duration=first:normalize=0,atrim=0:{dur}[a]")
    ff.ffmpeg("-i", clip, "-i", shaped, "-filter_complex", graph,
              "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", out)
