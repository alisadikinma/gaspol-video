"""Synthesize short UI / alert sounds with ffmpeg alone: no paid files, rebuildable anywhere.

Layers are described as data and mixed by :func:`render`. Two presets are included:
:func:`notification` (two-tone phone ping) and :func:`alarm` (rising hiss, sub hit, tension
drone, three high pulses).

Level warning: ffmpeg's ``sine`` source is far below full scale. ``sine`` + ``volume=0.30``
measures about -28.5 dBFS peak, not -10.5. The gains here are already corrected for that, so
they are NOT plain 0..1 gains. Always read the measured peak printed by :func:`measure`.

Why the alarm has four layers: a single high pulse sounds like an alarm clock, not a warning.
The sub hit (58/116 Hz) sits below the human voice band so narration stays clear; the pulses
(1.4-1.9 kHz) sit above it so they stay audible while someone talks.
"""
import re

from .ff import ensure_parent, ffmpeg

SR = 48000


def sine(freq, gain, at=0.0, length=0.3, fade_in=0.004, fade_out=0.2, curve="exp"):
    return {"src": f"sine=frequency={freq}:sample_rate={SR}", "len": length + fade_out,
            "chain": f"volume={gain},afade=t=in:st=0:d={fade_in},"
                     f"afade=t=out:st={length}:d={fade_out}:curve={curve}", "at": at}


def noise(color, gain_expr, length, at=0.0, chain=""):
    return {"src": f"anoisesrc=color={color}:sample_rate={SR}:amplitude=0.9", "len": length,
            "chain": (chain + "," if chain else "") + f"volume='{gain_expr}':eval=frame", "at": at}


def render(layers, out, length, limit=None):
    """Mix ``layers`` (dicts from :func:`sine` / :func:`noise`) into a stereo 48 kHz wav of
    exactly ``length`` seconds. ``limit`` adds an alimiter (level handling disabled, otherwise
    it re-amplifies to full scale and clips)."""
    ensure_parent(out)
    args, filt, names = [], [], []
    for n, layer in enumerate(layers):
        args += ["-f", "lavfi", "-t", f"{layer['len']:.3f}", "-i", layer["src"]]
        ms = int(round(layer.get("at", 0.0) * 1000))
        delay = f",adelay={ms}|{ms}" if ms else ""
        filt.append(f"[{n}:a]{layer['chain']}{delay}[l{n}]")
        names.append(f"[l{n}]")
    # A silent bed of the full length keeps the mix exactly `length` long. apad after amix was
    # tried first and truncated to the longest layer on some runs (filtergraph race).
    args += ["-f", "lavfi", "-t", f"{length:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
    filt.append(f"[{len(layers)}:a]anull[bed]")
    names.append("[bed]")
    tail = f"alimiter=limit={limit}:level=disabled," if limit else ""
    filt.append("".join(names) + f"amix=inputs={len(names)}:normalize=0,{tail}"
                f"aformat=sample_rates={SR}:channel_layouts=stereo,"
                f"atrim=0:{length}[out]")
    ffmpeg(*args, "-filter_complex", ";".join(filt), "-map", "[out]", out)
    return out


def measure(path):
    """(peak_dB, rms_dB) of a file, from ffmpeg astats."""
    err = ffmpeg("-i", path, "-af", "astats=measure_overall=RMS_level+Peak_level", "-f", "null", "-",
                 capture_stderr=True)
    peak = re.findall(r"Peak level dB: (-?[\d.]+)", err)[-1]
    rms = re.findall(r"RMS level dB: (-?[\d.]+)", err)[-1]
    return float(peak), float(rms)


def notification(out, notes=((880.0, 0.00), (1318.5, 0.11)), note_len=0.09, tail=0.22):
    """Two rising tones (A5, E6) with a quiet octave harmonic so it sounds like a phone speaker."""
    layers = []
    for hz, at in notes:
        layers.append(sine(hz, 1.60, at, note_len, 0.006, tail))
        layers.append(sine(hz * 2, 0.45, at, note_len * 0.7, 0.006, tail))
    return render(layers, out, 0.6)


def alarm(out, length=2.2, hit=0.50, pulses=(1380.0, 1860.0, 1380.0), pulse_gain=(2.4, 2.2, 1.6)):
    """Danger alarm. The sub hit lands at ``hit`` seconds: align it with the visual beat."""
    layers = [noise("brown", f"3.2*pow(min(1,t/{hit}),2.2)", length,
                    chain=f"highpass=f=260,lowpass=f=3800")]
    layers[0]["chain"] += f",afade=t=out:st={hit}:d=0.28:curve=exp"
    for hz, g in ((58.0, 5.2), (116.0, 2.6)):
        layers.append(sine(hz, g, hit, 0.05, 0.004, 0.9))
    for hz, g in ((82.0, 1.5), (123.0, 0.9)):
        layers.append({"src": f"sine=frequency={hz}:sample_rate={SR}", "len": length - hit,
                       "chain": f"volume={g},afade=t=in:st=0:d=0.30,afade=t=out:st=0.9:d=0.75:curve=tri",
                       "at": hit})
    for i, hz in enumerate(pulses):
        at = hit + 0.10 + i * 0.28
        layers.append(sine(hz, pulse_gain[i % len(pulse_gain)], at, 0.17, 0.006, 0.12))
        layers.append(sine(hz * 2, pulse_gain[i % len(pulse_gain)] * 0.35, at, 0.17, 0.006, 0.12))
    return render(layers, out, length, limit=0.34)
