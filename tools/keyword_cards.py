#!/usr/bin/env python3
"""Animated highlighted keyword text over a clip: stacked lines, no box, big gold serif-italic
keyword, small white sans for plain words, soft shadow, fly-in/out. Optional red flash behind a
person. Pillow PNG cards + ffmpeg overlay, no Remotion needed.

    python3 tools/keyword_cards.py render clip.mp4 out.mp4 spec.json

spec.json:
{
  "workdir": ".tmp/cards",                       # PNG cache, must be an existing project folder
  "cards": {"j1": {"lines": [["Barang baru","w",62], ["keluar duluan","g",106]]}},
  "cues":  [{"card":"j1","in":0.16,"out":2.75,"x":20,"y":380,"side":"left"}],
  "flash": {"t0":3.0,"t1":3.95,"mask":"mask.png","alpha":0.45,"period":0.3}   # optional
}
Line = [text, style, size_px]. Styles: w white sans, g gold serif italic (keyword),
r red serif italic (danger word: expired, rugi, telat), gs gold sans.
`side` = edge the card flies in from ("left"|"right"); `x`,`y` = resting top-left in px (1920x1080).
Cue times are seconds inside the clip, taken from word timestamps of the voice, not guessed.
Flash mask: grayscale PNG, 255 = may turn red (background), 0 = stays untouched (people, table).
Card is drawn above the flash. Card width is printed so a right-side card can use x = 1920 - w - 10.
"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import _venv  # noqa: E402

PIL = _venv.require("PIL")
from PIL import Image, ImageDraw, ImageFont, ImageFilter  # noqa: E402

SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold Italic.ttf"
GOLD, RED, WHITE = (226, 160, 48, 255), (232, 72, 60, 255), (255, 255, 255, 255)
STYLE = {"w": (SANS, WHITE), "g": (SERIF, GOLD), "r": (SERIF, RED), "gs": (SANS, GOLD)}


def block(path, lines, gap=-6, pad=40):
    S = 2
    fonts = [ImageFont.truetype(STYLE[st][0], size * S) for _, st, size in lines]
    ws = [f.getlength(t) for f, (t, _, _) in zip(fonts, lines)]
    hs = [sum(f.getmetrics()) for f in fonts]
    W = int(max(ws)) + 2 * pad * S
    H = int(sum(hs) + gap * S * (len(lines) - 1)) + 2 * pad * S
    sh, tx = Image.new("RGBA", (W, H), (0, 0, 0, 0)), Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dt = ImageDraw.Draw(sh), ImageDraw.Draw(tx)
    y = pad * S
    for f, (t, st, _), h in zip(fonts, lines, hs):
        ds.text((pad * S + 4 * S, y + 5 * S), t, font=f, fill=(0, 0, 0, 215))
        dt.text((pad * S, y), t, font=f, fill=STYLE[st][1])
        y += h + gap * S
    sh = sh.filter(ImageFilter.GaussianBlur(7 * S))
    img = Image.alpha_composite(sh, tx).resize((W // S, H // S), Image.LANCZOS)
    img.save(path)
    return img.width, img.height


def run(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, a)], check=True)


def render(src, out, spec):
    work = Path(spec.get("workdir", ".tmp/cards")); work.mkdir(parents=True, exist_ok=True)
    pngs = {}
    for name, c in spec["cards"].items():
        p = work / f"{name}.png"
        w, h = block(p, c["lines"])
        pngs[name] = p
        print(f"card {name}: {w}x{h}")
    cmd, fc, last, n = ["-i", src], [], "0:v", 1
    fl = spec.get("flash")
    if fl:
        a, per = fl.get("alpha", 0.45), fl.get("period", 0.3)
        cmd += ["-loop", "1", "-framerate", "24", "-i", fl["mask"]]
        fc += [f"[1:v]format=gray,lutyuv=y='clip((val-16)*{a}*255/219,0,255)'[m]",
               "color=c=red:s=1920x1080:r=24,format=rgba[r]", "[r][m]alphamerge[ra]",
               f"[0:v][ra]overlay=shortest=1:enable='between(t,{fl['t0']},{fl['t1']})*lt(mod(t-{fl['t0']},{per}),{per/2})'[f]"]
        last, n = "f", 2
    for cue in spec.get("cues", []):
        cmd += ["-loop", "1", "-framerate", "24", "-i", pngs[cue["card"]]]
        tin, tout, xf, y = cue["in"], cue["out"], cue["x"], cue["y"]
        far = "W" if cue.get("side", "left") == "right" else "-w"
        x = (f"if(lt(t,{tin}+0.35),{xf}+({far}-({xf}))*pow(1-(t-{tin})/0.35,3),"
             f"if(gt(t,{tout}-0.25),{xf}+({far}-({xf}))*pow((t-({tout}-0.25))/0.25,2),{xf}))")
        fc.append(f"[{last}][{n}:v]overlay=x='{x}':y={y}:enable='between(t,{tin},{tout})':shortest=1[v{n}]")
        last, n = f"v{n}", n + 1
    run(*cmd, "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "0:a?", "-c:v", "libx264", "-crf", "16",
        "-c:a", "copy", "-pix_fmt", "yuv420p", out)
    print(f"ok {out}")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) != 5 or sys.argv[1] != "render":
        sys.exit(__doc__)
    render(sys.argv[2], sys.argv[3], json.loads(Path(sys.argv[4]).read_text()))
