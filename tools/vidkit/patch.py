"""Freeze a rectangle of a clip to one frame.

Use when a video model animates something that must stay still (a progress bar that must not
advance, a number that must not change). Free and deterministic, where a re-generation is
neither. Only valid when the camera is nearly static and the box sits on a flat surface; with
real camera motion the frozen box floats, so re-generate or track instead.
"""
from .ff import ensure_parent, ffmpeg


def freeze_box(src, out, x, y, w, h, frame=0, crf=17):
    ensure_parent(out)
    ffmpeg("-i", src, "-filter_complex",
           f"[0:v]select='eq(n\\,{int(frame)})',crop={int(w)}:{int(h)}:{int(x)}:{int(y)},"
           f"loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB[patch];"
           f"[0:v][patch]overlay={int(x)}:{int(y)}:eof_action=pass[v]",
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
           "-pix_fmt", "yuv420p", "-c:a", "copy", out)
    return out
