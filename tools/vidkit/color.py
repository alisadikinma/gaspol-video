"""BT.709 colour tagging for the final encodes."""
import json

from . import ff

ENCODE_FLAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                "-color_range", "tv"]
TAG_FILTER = "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"


def probe_color(path):
    """color_space / color_primaries / color_transfer / color_range of the first video
    stream, 'unknown' for a missing tag. Raises ff.FFError when there is no video stream."""
    out = ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                  "stream=color_space,color_primaries,color_transfer,color_range",
                  "-of", "json", path])
    streams = json.loads(out).get("streams", [])
    if not streams:
        raise ff.FFError(f"no video stream in {path}")
    s = streams[0]
    return {k: s.get(k) or "unknown"
            for k in ("color_space", "color_primaries", "color_transfer", "color_range")}


_BT601 = {"smpte170m": "bt601-6-525", "bt470bg": "bt601-6-625"}
_HDR_TRC = {"smpte2084", "arib-std-b67"}


def convert_filter(probe, warnings=None, source=""):
    """ffmpeg filter that converts the source to BT.709, or '' when none is needed.

    '' for bt709 and for untagged sources (HD players assume bt709). A bt601 matrix gets a
    colorspace filter. HDR and any matrix we do not know are NOT converted: '' plus a line
    appended to `warnings` naming `source` and the value, never a silent guess."""
    space = probe.get("color_space", "unknown")
    trc = probe.get("color_transfer", "unknown")
    where = f"{source}: " if source else ""

    def warn(msg):
        if warnings is not None:
            warnings.append(where + msg)

    if trc in _HDR_TRC:
        warn(f"HDR transfer {trc} left unconverted (out of scope)")
        return ""
    if space in ("bt709", "unknown"):
        return ""
    if space in _BT601:
        return f"colorspace=all=bt709:iall={_BT601[space]}"
    warn(f"unknown colour matrix {space} left unconverted")
    return ""
