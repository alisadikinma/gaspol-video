#!/usr/bin/env python3
"""Build subtitle cues from text this plugin already owns.

    python3 tools/gen_subs.py <project-dir> [--master PATH] [--print]

The important property: **caption text always comes from the script**. Timing may come from
a recognizer, the text never does. That inverts the usual pipeline, which transcribes audio
and then tries to repair the transcript, and it is possible here only because the narration
was generated from a script this plugin wrote.

Timing sources, in order:
  1. word timings in vo/vo-manifest.json, free, for anything ElevenLabs spoke
  2. AssemblyAI, for dialogue the video platform generated
  3. nothing — the scene is listed as untimed. It is never guessed.

Stdlib only. No local model: ASR is AssemblyAI over HTTP, the same provider the editor uses.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ASSEMBLY_BASE = "https://api.assemblyai.com/v2"

DEFAULT_STYLE = {
    "font": "Inter", "size_px": 54, "stroke_px": 3, "position": "bottom",
    "margin_v_pct": 8, "max_chars_per_line": 38, "max_lines": 2,
}

# Words that are never worth biasing a recognizer toward.
STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "yang", "dan", "untuk",
    "dengan", "dari", "pada", "adalah", "akan", "brief", "domain", "product", "location",
}


class SubtitleError(Exception):
    """The cue list cannot be built as asked."""


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        if default is None:
            raise
        return default
    except json.JSONDecodeError as exc:
        raise SubtitleError(f"{Path(path).name} is not valid JSON: {exc.msg}") from exc


def split_lines(text, max_chars):
    """Break on word boundaries at the reading width. Never clips, never exceeds max_chars."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def wrap(text, max_chars, max_lines):
    """The first max_lines lines of the wrapped text.

    Text longer than max_lines x max_chars does NOT get squeezed: build_plan splits it into
    consecutive cues instead. Squeezing would either clip words or blow past the reading
    width, and both are worse than showing the line in two takes.
    """
    return "\n".join(split_lines(text, max_chars)[:max_lines])


def derive_keyterms(project, limit=40):
    """Proper nouns and jargon the recognizer would otherwise mangle.

    The editor asks the user to draft this list per video. Everything in it is already in
    the brief and the cast profile, so it is derived and then written into the plan where a
    wrong term is visible and fixable.
    """
    text = ""
    for name in ("strategic-brief.md", "cast-profile.md"):
        try:
            text += (Path(project) / name).read_text() + "\n"
        except OSError:
            continue

    terms, seen = [], set()
    # ALLCAPS acronyms, then Capitalised multi-word names.
    for match in re.findall(r"\b[A-Z]{2,}\b", text):
        key = match.lower()
        if key not in seen and key not in STOPWORDS:
            seen.add(key)
            terms.append(match)
    for match in re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text):
        key = match.lower()
        if key in seen or key in STOPWORDS or len(key) < 4:
            continue
        seen.add(key)
        terms.append(match)
    return terms[:limit]


def _cues_from_words(words, script_text, offset_s, style):
    """One layer -> one or more cues, split when the line is longer than a screenful."""
    if not words:
        return []
    start = offset_s + words[0]["start_ms"] / 1000.0
    end = offset_s + words[-1]["end_ms"] / 1000.0

    lines = split_lines(script_text, style["max_chars_per_line"])
    per_cue = style["max_lines"]
    groups = [lines[i:i + per_cue] for i in range(0, len(lines), per_cue)] or [[""]]

    total_chars = sum(len(" ".join(g)) for g in groups) or 1
    cues, cursor = [], start
    for group in groups:
        share = (end - start) * (len(" ".join(group)) / total_chars)
        cues.append({
            "at_s": round(cursor, 3),
            "end_s": round(cursor + share, 3),
            # Text is the SCRIPT, always. The recognizer only told us when.
            "text": "\n".join(group),
        })
        cursor += share
    return cues


def build_plan(project, asr_results=None, master_duration_s=None, style=None):
    project = Path(project)
    style = {**DEFAULT_STYLE, **(style or {})}
    asr_results = asr_results or {}

    audio_plan = _read_json(project / "work" / "audio-plan.json", {"scenes": []})
    manifest = _read_json(project / "vo" / "vo-manifest.json", {"items": []})
    words_by_id = {item["id"]: item.get("words", []) for item in manifest.get("items", [])}

    cues, untimed = [], []
    for scene in audio_plan.get("scenes", []):
        for layer in scene.get("layers", []):
            if layer.get("kind") not in ("narration", "dialogue"):
                continue
            script_text = (layer.get("text") or "").strip()
            if not script_text:
                continue
            item_id = Path(layer.get("out", "")).stem
            offset = float(layer.get("at_s", 0.0))

            words = words_by_id.get(item_id)
            source = "tts-timestamps"
            if not words:
                words = (asr_results.get(item_id) or {}).get("words")
                source = "assemblyai"
            if not words:
                untimed.append(scene["scene"])
                continue

            built = _cues_from_words(words, script_text, offset, style)
            if not built:
                untimed.append(scene["scene"])
                continue
            for cue in built:
                cue.update({"scene": scene["scene"], "from": source,
                            "script_line": f"av-script.md scene {scene['scene']}"})
            cues.extend(built)

    cues.sort(key=lambda c: c["at_s"])
    for i, cue in enumerate(cues, start=1):
        cue["index"] = i

    # Two speakers in one scene get sequential cues; overlap is trimmed, never allowed.
    for a, b in zip(cues, cues[1:]):
        if a["end_s"] > b["at_s"]:
            a["end_s"] = round(max(a["at_s"] + 0.2, b["at_s"] - 0.05), 3)

    if master_duration_s is not None:
        for cue in cues:
            if cue["end_s"] > master_duration_s + 0.05:
                raise SubtitleError(
                    f"cue {cue['index']} ends at {cue['end_s']}s, past the master "
                    f"({master_duration_s:.2f}s)"
                )

    return {
        "srt": "output/master.srt",
        "burn": True,
        "style": style,
        "cues": cues,
        "untimed": sorted(set(untimed)),
        "keyterms": derive_keyterms(project),
    }


def _ts(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues):
    blocks = []
    for cue in cues:
        blocks.append(f"{cue['index']}\n{_ts(cue['at_s'])} --> {_ts(cue['end_s'])}\n{cue['text']}\n")
    return "\n".join(blocks)


def transcribe_assemblyai(audio_path, api_key, keyterms=(), poll_s=3.0, log=print):
    """Upload, transcribe, return word timings. Text from here is used for TIMING only."""
    data = Path(audio_path).read_bytes()
    up = urllib.request.Request(f"{ASSEMBLY_BASE}/upload", data=data,
                                headers={"authorization": api_key}, method="POST")
    with urllib.request.urlopen(up, timeout=300) as resp:
        upload_url = json.loads(resp.read())["upload_url"]

    body = json.dumps({
        "audio_url": upload_url,
        "word_boost": list(keyterms)[:100],
        "boost_param": "high",
        "punctuate": True,
    }).encode()
    req = urllib.request.Request(f"{ASSEMBLY_BASE}/transcript", data=body,
                                 headers={"authorization": api_key,
                                          "content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        job_id = json.loads(resp.read())["id"]

    while True:
        poll = urllib.request.Request(f"{ASSEMBLY_BASE}/transcript/{job_id}",
                                      headers={"authorization": api_key})
        with urllib.request.urlopen(poll, timeout=60) as resp:
            payload = json.loads(resp.read())
        status = payload.get("status")
        if status == "completed":
            return {"words": [{"text": w["text"], "start_ms": w["start"], "end_ms": w["end"]}
                              for w in payload.get("words", [])]}
        if status == "error":
            raise SubtitleError(f"AssemblyAI failed: {payload.get('error')}")
        log(f"  transcription {status}...")
        time.sleep(poll_s)


def format_sheet(plan):
    lines = [f"{len(plan['cues'])} cue(s), style {plan['style']['font']} "
             f"{plan['style']['size_px']}px {plan['style']['position']}"]
    for cue in plan["cues"]:
        text = cue["text"].replace("\n", " / ")
        lines.append(f"  {cue['index']:>3}. {cue['at_s']:>7.2f} -> {cue['end_s']:>7.2f}  "
                     f"[{cue['from']:<15}] {text}")
    if plan["untimed"]:
        lines.append(f"  ! untimed scenes (no timing source): {plan['untimed']}")
    if plan["keyterms"]:
        lines.append(f"  keyterms: {', '.join(plan['keyterms'][:12])}"
                     + (" ..." if len(plan["keyterms"]) > 12 else ""))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--print", dest="show", action="store_true")
    args = ap.parse_args(argv)
    project = Path(args.project)

    env = dict(os.environ)
    try:
        for line in Path(".env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if v.strip():
                    env.setdefault(k.strip(), v.strip())
    except OSError:
        pass

    try:
        plan = build_plan(project)
        api_key = env.get("ASSEMBLYAI_API_KEY")
        if plan["untimed"] and not api_key:
            print("ASSEMBLYAI_API_KEY not set — scenes "
                  f"{plan['untimed']} have no timing source and were left out. "
                  "Set the key, or add those cues by hand with from: manual. "
                  "Timings are never guessed.", file=sys.stderr)

        print(format_sheet(plan))
        if args.show:
            return 0

        (project / "work").mkdir(parents=True, exist_ok=True)
        (project / "work" / "subtitle-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        (project / "output").mkdir(parents=True, exist_ok=True)
        (project / "output" / "master.srt").write_text(to_srt(plan["cues"]))
        print(f"\nwrote work/subtitle-plan.json and output/master.srt")
        return 0
    except SubtitleError as exc:
        print(f"gen_subs: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
