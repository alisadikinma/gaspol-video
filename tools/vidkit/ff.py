"""ffmpeg / ffprobe plumbing shared by every vidkit module."""
import json
import subprocess
from pathlib import Path


class FFError(RuntimeError):
    """ffmpeg or ffprobe exited non-zero. The message carries the tail of stderr."""


def run(cmd, capture_stderr=False):
    """Run a command list. Raises FFError on failure. Returns stdout, or stderr when asked
    (ffmpeg prints loudnorm / astats measurements on stderr)."""
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFError(f"{cmd[0]} failed ({proc.returncode}):\n{proc.stderr.strip()[-900:]}")
    return proc.stderr if capture_stderr else proc.stdout


def ffmpeg(*args, capture_stderr=False):
    return run(["ffmpeg", "-y", "-v", "error" if not capture_stderr else "info", *args],
               capture_stderr=capture_stderr)


def probe(path):
    """Everything the other modules need to know about a file, in one ffprobe call.

    Keys: duration (container), video {duration, fps, width, height} or None,
    audio {duration, sample_rate, channels} or None.
    """
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration:stream=codec_type,duration,r_frame_rate,width,height,"
               "sample_rate,channels", "-of", "json", path])
    data = json.loads(out)
    info = {"duration": _num(data.get("format", {}).get("duration")), "video": None, "audio": None}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["video"] is None:
            info["video"] = {"duration": _num(s.get("duration")), "fps": _fps(s.get("r_frame_rate")),
                             "width": s.get("width"), "height": s.get("height")}
        elif s.get("codec_type") == "audio" and info["audio"] is None:
            info["audio"] = {"duration": _num(s.get("duration")),
                             "sample_rate": int(s["sample_rate"]) if s.get("sample_rate") else None,
                             "channels": s.get("channels")}
    return info


def duration(path):
    """Container duration in seconds."""
    d = probe(path)["duration"]
    if d is None:
        raise FFError(f"no duration for {path}")
    return d


def has_audio(path):
    return probe(path)["audio"] is not None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fps(rate):
    try:
        a, b = rate.split("/")
        return float(a) / float(b) if float(b) else None
    except (AttributeError, ValueError):
        return None


def ensure_parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return Path(path)
