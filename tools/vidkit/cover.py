"""Burn subtitles, put a thumbnail on the first frames, and attach it as the mp4 cover."""
from . import ff


def apply(video, thumb, out, ass=None, hold_s=0.12, width=1080, height=1920, crf=17):
    """Write `out` = `video` with `ass` burned in, then `thumb` over the first `hold_s` seconds
    (placed AFTER the subtitles so no subtitle shows on the thumbnail frame), and `thumb` attached
    as cover art. Audio is copied from `video`. Returns `out`."""
    if hold_s <= 0:
        raise ValueError("hold_s must be positive")
    base = "[0:v]" + (f"ass={ass}[b];[b]" if ass else "")
    fc = (f"[1:v]scale={width}:{height},format=yuv420p[th];"
          f"{base}[th]overlay=0:0:enable='lt(t,{hold_s})'[v]")
    tmp = f"{out}.nocover.mp4"
    ff.ffmpeg("-i", video, "-loop", "1", "-framerate", 30, "-t", 1, "-i", thumb, "-filter_complex", fc,
              "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", crf, "-preset", "medium",
              "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-shortest", tmp)
    ff.ffmpeg("-i", tmp, "-i", thumb, "-map", "0", "-map", "1", "-c", "copy",
              "-disposition:v:1", "attached_pic", "-movflags", "+faststart", out)
    import os
    os.remove(tmp)
    return out
