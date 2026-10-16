"""Join clips into one: hard cuts (stream copy) or cross-dissolves.

Cross-dissolve rules that took real time to find:

* ``xfade`` OVERLAPS two clips for the length of the transition, it does not insert time. Clips
  of 8 + 4 + 4 s with 0.6 s and 0.4 s transitions total 15.0 s, not 16.0. Every later time point
  (clip starts, SFX cues) must come from :func:`clip_starts`, never typed by hand.
* Audio is NOT cross-faded. Each clip's audio stays whole, is delayed to its clip start and the
  tracks are mixed. Cross-fading would cut the tail of a room tone right when it is needed.
* ``xfade`` with duration 0 breaks the filter chain (video ends up shorter than the audio). A
  cut inside a dissolve chain is therefore given :data:`MIN_TRANSITION_S`, one frame at 25 fps.
"""
from pathlib import Path

from .ff import duration, ensure_parent, ffmpeg, probe
from .gates import gate_uniform

MIN_TRANSITION_S = 0.04


def clip_starts(durations, transitions):
    """Start time of each clip on the joined timeline. ``transitions[i]`` is the overlap
    between clip i and clip i+1, so ``len(transitions) == len(durations) - 1``."""
    if len(transitions) != len(durations) - 1:
        raise ValueError("need exactly one transition per seam")
    starts, t = [0.0], 0.0
    for d, tr in zip(durations, transitions):
        t += d - tr
        starts.append(t)
    return starts[:len(durations)]


def total_length(durations, transitions):
    return clip_starts(durations, transitions)[-1] + durations[-1]


def concat_copy(clips, out):
    """Hard cuts without re-encoding. Refuses non-uniform audio (see gates.gate_uniform)."""
    gate_uniform(clips)
    ensure_parent(out)
    listing = Path(str(out) + ".concat.txt")
    listing.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
    try:
        ffmpeg("-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", out)
    finally:
        listing.unlink(missing_ok=True)
    return out


def join_xfade(clips, out, transitions, effect="fade", crf=17):
    """Re-encode ``clips`` into one file with video dissolves and un-faded, mixed audio.

    All clips must share size and fps (xfade requirement); sample rate and channels are forced
    to 48 kHz stereo so mixed sources cannot corrupt each other.
    """
    if len(clips) < 2:
        raise ValueError("need at least two clips")
    infos = [probe(c) for c in clips]
    if any(i["video"] is None for i in infos):
        raise ValueError("every clip needs a video stream")
    sizes = {(i["video"]["width"], i["video"]["height"]) for i in infos}
    if len(sizes) > 1:
        raise ValueError(f"clips differ in size: {sorted(sizes)}")
    durs = [duration(c) for c in clips]
    trans = [max(t, MIN_TRANSITION_S) for t in transitions]
    starts = clip_starts(durs, trans)
    length = total_length(durs, trans)

    cmd, parts = [], []
    for i, c in enumerate(clips):
        cmd += ["-i", c]
    prev = "[0:v]"
    for i in range(1, len(clips)):
        label = f"[v{i}]"
        parts.append(f"{prev}[{i}:v]xfade=transition={effect}:duration={trans[i - 1]:.3f}"
                     f":offset={starts[i]:.3f}{label}")
        prev = label
    audio_labels = []
    for i, info in enumerate(infos):
        if info["audio"] is None:
            continue
        ms = int(round(starts[i] * 1000))
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{i}]")
        audio_labels.append(f"[a{i}]")
    maps = ["-map", prev]
    if audio_labels:
        # Silent bed of the full length: apad after amix truncated to the longest input on some
        # runs (see synth.render), a bed makes the length deterministic.
        cmd += ["-f", "lavfi", "-t", f"{length:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        parts.append(f"[{len(clips)}:a]anull[bed]")
        parts.append("".join(audio_labels) + f"[bed]amix=inputs={len(audio_labels) + 1}:normalize=0:"
                     f"duration=longest,atrim=0:{length:.3f}[aout]")
        maps += ["-map", "[aout]"]
    ensure_parent(out)
    ffmpeg(*cmd, "-filter_complex", ";".join(parts), *maps, "-c:v", "libx264", "-crf", str(crf),
           "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
           "-ar", "48000", "-t", f"{length:.3f}", out)
    return {"out": str(out), "length": length, "starts": starts}
