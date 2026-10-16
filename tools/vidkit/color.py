"""BT.709 colour tagging for the final encodes."""
import json
import os
import shutil
import sys

from . import ff

ENCODE_FLAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                "-color_range", "tv"]
TAG_FILTER = "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"

FFPROBE = shutil.which("ffprobe") or "ffprobe"


def probe_color(path):
    """color_space / color_primaries / color_transfer / color_range / pix_fmt of the first
    video stream, 'unknown' for a missing tag. Raises ff.FFError when there is no video stream."""
    out = ff.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                  "stream=color_space,color_primaries,color_transfer,color_range,pix_fmt",
                  "-of", "json", path])
    streams = json.loads(out).get("streams", [])
    if not streams:
        raise ff.FFError(f"no video stream in {path}")
    s = streams[0]
    return {k: s.get(k) or "unknown"
            for k in ("color_space", "color_primaries", "color_transfer", "color_range", "pix_fmt")}


_BT601 = {"smpte170m": "bt601-6-525", "bt470bg": "bt601-6-625"}
_HDR_TRC = {"smpte2084", "arib-std-b67"}
FULL_TO_LIMITED = "scale=in_range=full:out_range=tv"


def _bt601_variant(probe):
    """'bt601-6-525' / 'bt601-6-625' when the probe says BT.601, else None. The matrix
    tag wins; with no matrix, primaries or transfer of SMPTE 170M / BT.470BG decide."""
    space = probe.get("color_space", "unknown")
    if space in _BT601:
        return _BT601[space]
    if space != "unknown":
        return None
    prim = probe.get("color_primaries", "unknown")
    if prim in _BT601:
        return _BT601[prim]
    if probe.get("color_transfer", "unknown") == "smpte170m":
        return _BT601["smpte170m"]
    return None


def convert_filter(probe, warnings=None, source=""):
    """ffmpeg filter that converts the source to BT.709, or '' when none is needed.

    '' for bt709 and for untagged sources (HD players assume bt709; a warning says so
    when nothing at all is tagged). A bt601 matrix gets a colorspace filter, found from the
    matrix tag or, when that is missing, from the primaries or transfer. HDR and any matrix
    we do not know are NOT converted: '' plus a line appended to `warnings` naming `source`
    and the value, never a silent guess."""
    space = probe.get("color_space", "unknown")
    trc = probe.get("color_transfer", "unknown")
    prim = probe.get("color_primaries", "unknown")
    where = f"{source}: " if source else ""

    def warn(msg):
        if warnings is not None:
            warnings.append(where + msg)

    if trc in _HDR_TRC:
        warn(f"HDR transfer {trc} left unconverted (out of scope)")
        return ""
    variant = _bt601_variant(probe)
    if variant:
        return f"colorspace=all=bt709:iall={variant}"
    if space == "bt709":
        return ""
    if space == "unknown":
        if prim == "unknown" and trc == "unknown":
            warn("no colour tags, assuming bt709")
        return ""
    warn(f"unknown colour matrix {space} left unconverted")
    return ""


def is_full_range(probe):
    return probe.get("color_range") == "pc" or str(probe.get("pix_fmt", "")).startswith("yuvj")


def source_filters(path, warn=None):
    """Ordered ffmpeg filters a source needs BEFORE the bt709/tv tag: full->limited range
    when the source is full range (pc / yuvj*), then the bt601->bt709 matrix conversion.

    `warn(msg)` receives each problem (default: one line on stderr). A probe that fails on a
    file that exists is warned about, naming the error. A file that does not exist yet stays
    silent and unconverted: ffmpeg itself fails on it later."""
    if warn is None:
        def warn(msg):
            print(f"warning: {msg}", file=sys.stderr)
    try:
        probe = probe_color(str(path))
    except (ff.FFError, OSError, ValueError) as exc:
        if os.path.exists(str(path)):
            warn(f"{path}: colour probe failed ({' '.join(str(exc).split())[-200:]}); tagged bt709 anyway")
        return []
    found = []
    filters = []
    if is_full_range(probe):
        filters.append(FULL_TO_LIMITED)
    flt = convert_filter(probe, found, str(path))
    if flt:
        filters.append(flt)
    for w in found:
        warn(w)
    return filters
