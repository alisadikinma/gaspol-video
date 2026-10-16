"""Video encoder choice for the final-path encodes.

``GASPOL_VIDEO_ENCODER``: ``libx264`` (default when unset), ``auto`` or ``h264_videotoolbox``.
libx264 stays the default because a hardware encoder's quality per bitrate differs; the
hardware path is opt-in.
"""
import re

from . import ff

DEFAULT = "libx264"
HARDWARE = "h264_videotoolbox"
VALID = (DEFAULT, "auto", HARDWARE)

# Hardware encoders take a bitrate, not a CRF. Looked up by output height.
BITRATE_BY_HEIGHT = {1080: "12M", 720: "6M"}
BITRATE_OTHER = "8M"


class EncoderError(ValueError):
    """Unknown GASPOL_VIDEO_ENCODER value, or an encode that failed on every encoder."""


def available(ffmpeg_encoders_text):
    """Encoder names listed by `ffmpeg -hide_banner -encoders`."""
    names = set()
    for line in (ffmpeg_encoders_text or "").splitlines():
        m = re.match(r"^\s*[VASFXBD.]{6}\s+(\S+)\s", line + " ")
        if m:
            names.add(m.group(1))
    return names


def choose(env_value, avail):
    """(encoder name, warning or None)."""
    value = (env_value or DEFAULT).strip() or DEFAULT
    if value not in VALID:
        raise EncoderError(f"unknown GASPOL_VIDEO_ENCODER {value!r}, expected one of {', '.join(VALID)}")
    if value == "auto":
        return (HARDWARE if HARDWARE in avail else DEFAULT), None
    if value == HARDWARE and HARDWARE not in avail:
        return DEFAULT, f"encoder {HARDWARE} is not available in this ffmpeg; using {DEFAULT}"
    return value, None


def video_args(name, crf=20, height=1080):
    """The video-encoder part of an ffmpeg command."""
    if name == DEFAULT:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if name == HARDWARE:
        rate = BITRATE_BY_HEIGHT.get(height, BITRATE_OTHER)
        return ["-c:v", HARDWARE, "-b:v", rate, "-pix_fmt", "yuv420p"]
    raise EncoderError(f"no argument recipe for encoder {name!r}")


def run_with_fallback(build_cmd, chosen, run):
    """Run `build_cmd(chosen)` through `run` (which raises ff.FFError on a non-zero exit).
    A failed hardware encode is retried ONCE with libx264; a failed libx264 is not retried.
    When the retry fails too, the error carries both stderr tails."""
    try:
        return run(build_cmd(chosen))
    except ff.FFError as first:
        if chosen == DEFAULT:
            raise
        print(f"encoder {chosen} failed, retried with {DEFAULT}")
        try:
            return run(build_cmd(DEFAULT))
        except ff.FFError as second:
            raise ff.FFError(f"{chosen} failed:\n{first}\n{DEFAULT} retry failed:\n{second}") from first
