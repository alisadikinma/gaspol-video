"""Karaoke subtitles (ASS) from a word list, plus an optional centre watermark line.

Input is plain data: [(word, start_s, end_s), ...]. Where the times come from (ElevenLabs word
timings, whisper) is the caller's business. Nothing here knows a project.
"""
import re

ACCENT_TEAL = "&H00D0D14F"  # #4fd1d0 in ASS BGR


def clock(t):
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def group_words(words, per_group=2):
    """Group words, closing a group early at sentence-ending punctuation."""
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) == per_group or re.search(r"[.!?]$", w[0]):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def merge_sharp(words):
    """'C' 'Sharp' -> 'C#' (a speech engine spells it out, the screen should not)."""
    out, i = [], 0
    while i < len(words):
        if i + 1 < len(words) and words[i][0] == "C" and words[i + 1][0].lower().startswith("sharp"):
            out.append(("C#", words[i][1], words[i + 1][2]))
            i += 2
        else:
            out.append(words[i])
            i += 1
    return out


def events(groups, tail=0.12, min_len=0.35, max_tail=0.9):
    """One ASS Dialogue line per group; \\kf fills each word over its own duration."""
    lines = []
    for i, g in enumerate(groups):
        st, en = g[0][1], g[-1][2]
        nxt = groups[i + 1][0][1] if i + 1 < len(groups) else en + 0.5
        en = min(max(en + tail, st + min_len), nxt - 0.02, en + max_tail)
        parts = []
        for j, w in enumerate(g):
            nxt_t = g[j + 1][1] if j + 1 < len(g) else max(w[2], en - tail)
            parts.append(f"{{\\kf{max(int(round((nxt_t - w[1]) * 100)), 8)}}}{w[0]}")
        lines.append(f"Dialogue: 0,{clock(st)},{clock(en)},Sub,,0,0,0,,"
                     f"{{\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)}}{' '.join(parts)}")
    return lines


def watermark_event(text, total_s, width=1080, height=1920, opacity=0.12, font_size=84):
    """A centre watermark for the whole video. `opacity` 0.12 = 12% visible."""
    if not 0 < opacity <= 1:
        raise ValueError("opacity must be in (0, 1]")
    alpha = f"&H{int(round((1 - opacity) * 255)):02X}&"
    return (f"Dialogue: 0,0:00:00.00,{clock(total_s)},Sub,,0,0,0,,"
            f"{{\\an5\\pos({width // 2},{height // 2})\\fs{font_size}\\1c&HFFFFFF&\\1a{alpha}"
            f"\\3a&HFF&\\4a&HFF&\\bord0\\shad0}}{text}")


def build_ass(words, total_s, watermark=None, watermark_opacity=0.12, font="Helvetica Neue",
              font_size=86, margin_v=360, accent=ACCENT_TEAL, per_group=2, width=1080, height=1920):
    """Full .ass text. `watermark` is the text, or None for no watermark."""
    ev = events(group_words(merge_sharp(words), per_group))
    if watermark:
        ev.insert(0, watermark_event(watermark, total_s, width, height, watermark_opacity))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},{font_size},{accent},&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,2,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return head + "\n".join(ev) + "\n"
