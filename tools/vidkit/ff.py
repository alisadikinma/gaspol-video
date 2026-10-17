"""ffmpeg / ffprobe plumbing shared by every vidkit module."""
import json
import shutil
import subprocess
import time
from pathlib import Path


class FFError(RuntimeError):
    """ffmpeg or ffprobe exited non-zero. The message carries the tail of stderr."""


class FFMissing(FFError):
    """The binary is not on PATH. The message names it."""


TOOLS = ("ffmpeg", "ffprobe")


def missing():
    """Names from TOOLS that are not on PATH."""
    return [t for t in TOOLS if shutil.which(t) is None]


def run(cmd, capture_stderr=False, heartbeat_s=None):
    """Run a command list. Raises FFError on failure. Returns stdout, or stderr when asked
    (ffmpeg prints loudnorm / astats measurements on stderr).

    With `heartbeat_s`, prints `still running: <label> <elapsed>s` to stdout every
    `heartbeat_s` seconds until the child exits, so a long silent encode is visibly alive.
    The label is the last argument's file name (the output of an ffmpeg command)."""
    argv = [str(c) for c in cmd]
    if heartbeat_s:
        stdout, stderr, rc = _run_with_heartbeat(argv, heartbeat_s)
    else:
        try:
            proc = subprocess.run(argv, capture_output=True, text=True)
        except FileNotFoundError:
            raise FFMissing(f"{argv[0]} not found on PATH") from None
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    if rc != 0:
        raise FFError(f"{cmd[0]} failed ({rc}):\n{stderr.strip()[-900:]}")
    return stderr if capture_stderr else stdout


def _run_with_heartbeat(argv, heartbeat_s):
    label = Path(argv[-1]).name if len(argv) > 1 else argv[0]
    start = time.monotonic()
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise FFMissing(f"{argv[0]} not found on PATH") from None
    while True:
        try:
            stdout, stderr = proc.communicate(timeout=heartbeat_s)
            return stdout, stderr, proc.returncode
        except subprocess.TimeoutExpired:
            print(f"still running: {label} {time.monotonic() - start:.0f}s", flush=True)
        except BaseException:
            proc.kill()
            proc.communicate()
            raise


def ffmpeg(*args, capture_stderr=False):
    return run(["ffmpeg", "-y", "-v", "error" if not capture_stderr else "info", *args],
               capture_stderr=capture_stderr)


def probe(path):
    """Everything the other modules need to know about a file, in one ffprobe call.

    Keys: duration (container), video {duration, fps, width, height, pix_fmt} or None,
    audio {duration, sample_rate, channels} or None.
    """
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration:stream=codec_type,duration,r_frame_rate,width,height,"
               "sample_rate,channels,pix_fmt", "-of", "json", path])
    data = json.loads(out)
    info = {"duration": _num(data.get("format", {}).get("duration")), "video": None, "audio": None}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["video"] is None:
            info["video"] = {"duration": _num(s.get("duration")), "fps": _fps(s.get("r_frame_rate")),
                             "width": s.get("width"), "height": s.get("height"),
                             "pix_fmt": s.get("pix_fmt")}
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
