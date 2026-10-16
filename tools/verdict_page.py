#!/usr/bin/env python3
"""Stills-first verdict page and gate for keyframes, before any clip is rendered.

    python3 tools/verdict_page.py page  <project> [--keyframes keyframes] [--out output/verdict.html] [--max-mb 16]
    python3 tools/verdict_page.py check <project> [--allow-maybe]

`page` builds ONE self-contained HTML file: a card per `keyframes/scene-*.png` with the image
inlined as a downscaled JPEG data URI, PASS / MAYBE / NO buttons (keys 1/2/3), a note field and
a "Download verdict.json" button. The owner opens it in a browser and saves the file into
`work/verdict.json`: {"scenes": {"<id>": {"verdict": "PASS|MAYBE|NO", "note": str}}}.

`check` exits 0 only when every keyframe has PASS (or MAYBE with --allow-maybe); 1 listing each
missing / NO / MAYBE scene; 2 when the file is missing, malformed or holds a bad verdict value.

Stdlib only. Needs ffmpeg (no Pillow, no venv).
"""

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
VERDICTS = ("PASS", "MAYBE", "NO")
# (long side px, jpeg quality as ffmpeg -q:v). Level 0 is the default.
LEVELS = [(900, 4), (700, 6), (560, 9), (420, 12), (320, 16), (240, 20), (160, 28)]


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def scene_ids(project, keyframes="keyframes"):
    d = Path(project) / keyframes
    ids = []
    for p in d.glob("scene-*.png"):
        ids.append(p.stem[len("scene-"):])
    return sorted(ids, key=natural_key)


def to_jpeg(src, level):
    side, q = LEVELS[level]
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "o.jpg"
        vf = f"scale='if(gt(iw,ih),min({side},iw),-2)':'if(gt(iw,ih),-2,min({side},ih))'"
        r = subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-vf", vf,
                            "-frames:v", "1", "-q:v", str(q), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"ffmpeg could not read {src}: {r.stderr.strip()[-200:]}")
        return base64.b64encode(out.read_bytes()).decode("ascii")


CSS = """
:root{--bg:#fafafa;--fg:#1a1a1a;--card:#fff;--line:#c8c8c8;--accent:#0b5fff;--pass:#12803c;--maybe:#a15c00;--no:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#121212;--fg:#ececec;--card:#1e1e1e;--line:#444;--accent:#6ea0ff;--pass:#4cc17a;--maybe:#e0a040;--no:#ff7b72}}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0;padding:12px}
h1{font-size:1.25rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,360px),1fr));gap:12px}
.card{background:var(--card);border:2px solid var(--line);border-radius:8px;padding:10px}
.card:focus,.card:focus-within{outline:3px solid var(--accent);outline-offset:2px}
.card img{width:100%;height:auto;display:block;border-radius:4px}
.id{font-weight:700;margin:6px 0}
.btns{display:flex;gap:6px;margin:6px 0}
button{flex:1;min-height:44px;font:inherit;color:var(--fg);background:var(--card);border:2px solid var(--line);border-radius:6px;cursor:pointer}
button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
button[aria-pressed=true]{color:#fff;border-color:transparent}
button[data-v=PASS][aria-pressed=true]{background:var(--pass)}
button[data-v=MAYBE][aria-pressed=true]{background:var(--maybe)}
button[data-v=NO][aria-pressed=true]{background:var(--no)}
textarea{width:100%;min-height:56px;font:inherit;color:var(--fg);background:var(--bg);border:2px solid var(--line);border-radius:6px}
.bar{position:sticky;top:0;background:var(--bg);padding:8px 0;margin-bottom:8px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.bar button{flex:none;padding:0 14px}
"""

JS = """
(function(){
  var cards=document.querySelectorAll('.card');
  var state={};
  var count=document.getElementById('count');
  function paint(card){
    var id=card.getAttribute('data-scene');
    card.querySelectorAll('button[data-v]').forEach(function(b){
      b.setAttribute('aria-pressed',String(state[id]===b.getAttribute('data-v')));
    });
    count.textContent=Object.keys(state).length+' dari '+cards.length+' sudah dinilai';
  }
  function setV(card,v){state[card.getAttribute('data-scene')]=v;paint(card);}
  cards.forEach(function(card){
    card.querySelectorAll('button[data-v]').forEach(function(b){
      b.addEventListener('click',function(){setV(card,b.getAttribute('data-v'));});
    });
    card.addEventListener('keydown',function(e){
      if(e.target.tagName==='TEXTAREA')return;
      var m={'1':'PASS','2':'MAYBE','3':'NO'};
      if(m[e.key]){setV(card,m[e.key]);e.preventDefault();}
    });
  });
  document.getElementById('dl').addEventListener('click',function(){
    var out={scenes:{}};
    cards.forEach(function(card){
      var id=card.getAttribute('data-scene');
      if(state[id]){out.scenes[id]={verdict:state[id],note:card.querySelector('textarea').value};}
    });
    var blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});
    var a=document.createElement('a');
    a.href=URL.createObjectURL(blob);a.download='verdict.json';
    document.body.appendChild(a);a.click();document.body.removeChild(a);
  });
  paint(cards[0]);
})();
"""


def build_html(entries):
    cards = []
    for sid, b64 in entries:
        e = html.escape(sid, quote=True)
        cards.append(
            f'<section class="card" data-scene="{e}" tabindex="0" aria-label="Scene {e}">'
            f'<img alt="Keyframe scene {e}" src="data:image/jpeg;base64,{b64}">'
            f'<div class="id">Scene {e}</div>'
            f'<div class="btns">'
            f'<button type="button" data-v="PASS" aria-pressed="false">1 PASS</button>'
            f'<button type="button" data-v="MAYBE" aria-pressed="false">2 MAYBE</button>'
            f'<button type="button" data-v="NO" aria-pressed="false">3 NO</button></div>'
            f'<label>Catatan<textarea aria-label="Catatan scene {e}"></textarea></label>'
            f'</section>')
    return (
        '<!doctype html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Verdict keyframe</title>'
        f'<style>{CSS}</style></head><body>'
        '<h1>Nilai keyframe sebelum render klip</h1>'
        '<p>Klik kartu, lalu tekan 1 (PASS), 2 (MAYBE) atau 3 (NO). '
        'Di akhir, tekan Download. Simpan file ke work/verdict.json.</p>'
        '<div class="bar"><button type="button" id="dl">Download verdict.json</button>'
        '<span id="count" aria-live="polite"></span></div>'
        f'<div class="grid">{"".join(cards)}</div>'
        f'<script>{JS}</script></body></html>')


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".verdict-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_page(a):
    if not FFMPEG:
        print("ffmpeg not on PATH", file=sys.stderr)
        return 2
    project = Path(a.project)
    ids = scene_ids(project, a.keyframes)
    if not ids:
        print(f"no keyframes/scene-*.png under {project / a.keyframes}", file=sys.stderr)
        return 2
    cap = int(a.max_mb * 1024 * 1024)
    level = 0
    while True:
        try:
            entries = [(i, to_jpeg(project / a.keyframes / f"scene-{i}.png", level)) for i in ids]
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 2
        page = build_html(entries)
        size = len(page.encode("utf-8"))
        if size <= cap or level == len(LEVELS) - 1:
            break
        level += 1
    out = Path(a.out)
    if not out.is_absolute():
        out = project / out
    write_atomic(out, page)
    side = LEVELS[level][0]
    print(f"{out}: {len(ids)} scenes, {size / 1024 / 1024:.2f} MB, level {level} (long side {side}px)")
    if size > cap:
        print(f"WARNING: still above {a.max_mb} MB at the lowest level", file=sys.stderr)
        return 1
    return 0


def cmd_check(a):
    project = Path(a.project)
    vf = project / "work" / "verdict.json"
    try:
        data = json.loads(vf.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"{vf} not found", file=sys.stderr)
        return 2
    except (ValueError, OSError) as e:
        print(f"{vf} unreadable: {e}", file=sys.stderr)
        return 2
    scenes = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(scenes, dict):
        print(f'{vf}: expected {{"scenes": {{...}}}}', file=sys.stderr)
        return 2
    for sid, v in scenes.items():
        if not isinstance(v, dict) or v.get("verdict") not in VERDICTS:
            print(f"{vf}: scene {sid}: verdict must be one of {'/'.join(VERDICTS)}", file=sys.stderr)
            return 2
    ids = scene_ids(project)
    if not ids:
        print("no keyframes/scene-*.png to check", file=sys.stderr)
        return 2
    bad = []
    for i in ids:
        v = scenes.get(i, {}).get("verdict")
        if v == "PASS" or (v == "MAYBE" and a.allow_maybe):
            continue
        bad.append(f"{i}: {v or 'MISSING'}")
    if bad:
        print("FAIL verdict gate:")
        for b in bad:
            print("  " + b)
        return 1
    print(f"OK {len(ids)} scenes passed")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pg = sub.add_parser("page")
    pg.add_argument("project")
    pg.add_argument("--keyframes", default="keyframes")
    pg.add_argument("--out", default="output/verdict.html")
    pg.add_argument("--max-mb", type=float, default=16)
    ck = sub.add_parser("check")
    ck.add_argument("project")
    ck.add_argument("--allow-maybe", action="store_true")
    a = p.parse_args(argv)
    return cmd_page(a) if a.cmd == "page" else cmd_check(a)


if __name__ == "__main__":
    sys.exit(main())
