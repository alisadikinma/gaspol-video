#!/usr/bin/env python3
"""Verify the rendered narration against the script with a second ASR pass (P6).

    python3 tools/verify_render.py <project-dir> [--master PATH] [--asr-json PATH]

`gen_subs.py` writes captions from the SCRIPT — a recognizer only ever supplied timing. This
tool closes the loop the other way: it transcribes the actual rendered master and diffs that
transcript against the intended narration/dialogue, so a dropped word, a stray ghost syllable,
or a scene that quietly went out of sync gets caught before anyone watches the video.

Everything here is advisory except the pass/fail line: the report says WHERE to listen, the
user's ear still decides whether a "heard differently" or a low-confidence flag matters.

Stdlib only. AssemblyAI over HTTP for the live path; `--asr-json` replays a saved transcript so
tests and re-runs never re-bill.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.gen_subs import derive_keyterms, transcribe_assemblyai  # noqa: E402

FFMPEG = shutil.which("ffmpeg")

GAP_S = 0.40
LOW_CONFIDENCE = 0.70
DRIFT_S = 0.25


class VerifyError(Exception):
    """The render cannot be verified as asked. Message names the offending file."""


def norm(text):
    """Lowercase, strip punctuation except apostrophes, split into words. Digits are kept
    as-is — Indonesian scripts write numbers as digits ("42"), not words."""
    t = (text or "").lower()
    t = re.sub(r"[^\w'\s]", " ", t, flags=re.UNICODE)
    return [w for w in t.split() if w]


def _read_json(path, required=True):
    path = Path(path)
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        if required:
            raise VerifyError(f"{path} not found") from exc
        return None
    except json.JSONDecodeError as exc:
        raise VerifyError(f"{path.name} is not valid JSON: {exc.msg}") from exc


def scene_starts(edit_plan):
    """{scene_number: start_s on the master}. The n-th segment IS scene n (P2 guarantees one
    segment per scene), so this is purely positional cumulative length, pad_end_s included."""
    starts = {}
    cum = 0.0
    for i, seg in enumerate(edit_plan.get("segments", []), start=1):
        starts[i] = cum
        cum += (float(seg["out_s"]) - float(seg["in_s"])) + float(seg.get("pad_end_s", 0.0) or 0.0)
    return starts


def build_intended(audio_plan, edit_plan):
    """Flatten every narration/dialogue layer, in scene then at_s order, into one word list.
    Each word carries its planned master-clock time (None when the plan has fewer edit
    segments than scenes — the diff still runs, drift just skips that layer)."""
    starts = scene_starts(edit_plan)
    entries = []
    layer_id = 0
    scenes = sorted(audio_plan.get("scenes", []), key=lambda s: s.get("scene", 0))
    for scene in scenes:
        layers = [l for l in scene.get("layers", []) if l.get("kind") in ("narration", "dialogue")]
        layers = sorted(layers, key=lambda l: float(l.get("at_s", 0.0)))
        for layer in layers:
            layer_id += 1
            words = norm(layer.get("text", ""))
            if not words:
                continue
            scene_start = starts.get(scene.get("scene"))
            at_s = float(layer.get("at_s", 0.0))
            dur_s = float(layer.get("dur_s", 0.0) or 0.0)
            planned_layer_s = (scene_start + at_s) if scene_start is not None else None
            n = len(words)
            for i, word in enumerate(words):
                if planned_layer_s is not None and dur_s > 0:
                    planned_word_s = planned_layer_s + dur_s * (i / n)
                else:
                    planned_word_s = planned_layer_s
                entries.append({
                    "scene": scene.get("scene"), "layer_id": layer_id, "word": word,
                    "planned_word_s": planned_word_s, "planned_layer_s": planned_layer_s,
                })
    return entries


def flatten_rendered(words):
    """Token list -> (normalised word list, index back to the source ASR word)."""
    out, idx = [], []
    for i, w in enumerate(words):
        for piece in norm(w.get("text", "")):
            out.append(piece)
            idx.append(i)
    return out, idx


def analyze(intended, rendered, gap_s=GAP_S, low_confidence=LOW_CONFIDENCE, drift_s=DRIFT_S):
    """Diff the intended script words against the rendered ASR words. A word-swap ("replace")
    is reported as "heard differently", never counted toward missing/inserted — those two are
    reserved for content that is truly absent or truly extra, which is what P6 fails on."""
    a_words = [e["word"] for e in intended]
    b_words, b_idx = flatten_rendered(rendered)

    matched = [False] * len(rendered)
    render_layer = [None] * len(rendered)
    inserted, missing, replaced = [], [], []

    matcher = SequenceMatcher(None, a_words, b_words, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k, j in enumerate(range(j1, j2)):
                ridx = b_idx[j]
                matched[ridx] = True
                render_layer[ridx] = intended[i1 + k]["layer_id"]
        elif tag == "insert":
            for j in range(j1, j2):
                ridx = b_idx[j]
                w = rendered[ridx]
                inserted.append({"start_ms": w.get("start_ms"), "text": w.get("text")})
        elif tag == "delete":
            for i in range(i1, i2):
                missing.append(intended[i])
        elif tag == "replace":
            len_i, len_j = i2 - i1, j2 - j1
            for k in range(max(len_i, len_j)):
                exp = intended[i1 + k] if k < len_i else None
                ridx = b_idx[j1 + k] if k < len_j else None
                if exp is not None and ridx is not None:
                    w = rendered[ridx]
                    replaced.append({"start_ms": w.get("start_ms"), "heard": w.get("text"),
                                      "expected": exp["word"]})
                    matched[ridx] = True
                    render_layer[ridx] = exp["layer_id"]
                elif ridx is not None:
                    w = rendered[ridx]
                    inserted.append({"start_ms": w.get("start_ms"), "text": w.get("text")})
                elif exp is not None:
                    missing.append(exp)

    # Interior gaps: consecutive MATCHED rendered words from the same layer, paused too long.
    gaps = []
    for x in range(len(rendered) - 1):
        y = x + 1
        if not (matched[x] and matched[y]):
            continue
        if render_layer[x] is None or render_layer[x] != render_layer[y]:
            continue
        gap = (rendered[y].get("start_ms", 0) - rendered[x].get("end_ms", 0)) / 1000.0
        if gap >= gap_s:
            gaps.append({"start_ms": rendered[x].get("end_ms"), "gap_s": gap,
                        "before": rendered[x].get("text"), "after": rendered[y].get("text")})

    lowconf = [{"start_ms": w.get("start_ms"), "text": w.get("text"),
               "confidence": w.get("confidence")}
               for w in rendered
               if w.get("confidence") is not None and w["confidence"] < low_confidence]

    # Drift: per layer, the FIRST matched rendered word vs that layer's planned start.
    layer_planned = {e["layer_id"]: e["planned_layer_s"] for e in intended}
    drift_rows = []
    drift_flags = 0
    seen_layers = set()
    for ridx, layer_id in enumerate(render_layer):
        if layer_id is None or not matched[ridx] or layer_id in seen_layers:
            continue
        seen_layers.add(layer_id)
        planned = layer_planned.get(layer_id)
        if planned is None:
            continue
        actual = rendered[ridx].get("start_ms", 0) / 1000.0
        delta = actual - planned
        flagged = abs(delta) > drift_s
        if flagged:
            drift_flags += 1
        drift_rows.append({"layer_id": layer_id, "delta_s": delta,
                           "start_ms": rendered[ridx].get("start_ms"),
                           "text": rendered[ridx].get("text"), "flagged": flagged})

    exit_code = 1 if (missing or inserted) else 0

    return {
        "inserted": inserted, "missing": missing, "replaced": replaced,
        "gaps": gaps, "lowconf": lowconf, "drift_rows": drift_rows, "drift_flags": drift_flags,
        "exit_code": exit_code,
    }


def _clock(seconds):
    if seconds is None:
        return "?:??"
    seconds = max(0.0, seconds)
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def build_report(result):
    header = (f"Extra: {len(result['inserted'])} · missing: {len(result['missing'])} · "
              f"heard differently: {len(result['replaced'])} · gaps: {len(result['gaps'])} · "
              f"low-confidence: {len(result['lowconf'])} · drift flags: {result['drift_flags']}")
    lines = [header, ""]

    if result["inserted"]:
        lines.append("## Extra words in the render (ghost speech that rode along)")
        for r in result["inserted"]:
            t = (r["start_ms"] or 0) / 1000.0
            lines.append(f"{_clock(t)} ({t:.2f} s) · \"{r['text']}\"")
        lines.append("")

    if result["missing"]:
        lines.append("## Missing words (intended but never rendered)")
        for r in result["missing"]:
            t = r["planned_word_s"]
            ts = f"{_clock(t)} ({t:.2f} s)" if t is not None else "?:??"
            lines.append(f"{ts} · \"{r['word']}\"")
        lines.append("")

    if result["replaced"]:
        lines.append("## Heard differently (possible mangled join, or ASR variance)")
        for r in result["replaced"]:
            t = (r["start_ms"] or 0) / 1000.0
            lines.append(f"{_clock(t)} ({t:.2f} s) · expected \"{r['expected']}\", "
                        f"heard \"{r['heard']}\"")
        lines.append("")

    if result["gaps"]:
        lines.append(f"## Interior pauses >= {GAP_S:.2f}s inside a spoken line")
        for r in result["gaps"]:
            t = (r["start_ms"] or 0) / 1000.0
            lines.append(f"{_clock(t)} ({r['gap_s']:.2f} s gap) · …{r['before']} ⟂ {r['after']}…")
        lines.append("")

    if result["lowconf"]:
        lines.append(f"## Low-confidence rendered words (< {LOW_CONFIDENCE:.2f})")
        for r in result["lowconf"]:
            t = (r["start_ms"] or 0) / 1000.0
            lines.append(f"{_clock(t)} · conf {r['confidence']:.2f} · \"{r['text']}\"")
        lines.append("")

    if result["drift_rows"]:
        flagged = [r for r in result["drift_rows"] if r["flagged"]]
        rows = flagged or result["drift_rows"]
        title = (f"## A/V drift — {len(flagged)} line(s) beyond ±{DRIFT_S:.2f}s"
                if flagged else "## A/V drift: OK (within budget)")
        lines.append(title)
        for r in rows:
            t = (r["start_ms"] or 0) / 1000.0
            mark = " <<<" if r["flagged"] else ""
            lines.append(f"{_clock(t)} · {r['delta_s']:+.3f}s vs planned · \"{r['text']}\"{mark}")
        lines.append("")

    if not any([result["inserted"], result["missing"], result["replaced"], result["gaps"],
               result["lowconf"], result["drift_flags"]]):
        lines.append("Clean — the render matches the script word-for-word, no anomalies.")

    return "\n".join(lines).rstrip() + "\n"


def default_master(project):
    project = Path(project)
    mixed = project / "output" / "master-mixed.mp4"
    return mixed if mixed.exists() else project / "output" / "master.mp4"


def _extract_audio(master, out_wav):
    if FFMPEG is None:
        raise VerifyError("ffmpeg not available to extract audio from the master")
    proc = subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-i", str(master), "-vn", "-ac", "1", "-ar", "16000",
         str(out_wav)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise VerifyError(f"ffmpeg failed extracting audio: {proc.stderr.strip()[-300:]}")


def verify(project, master=None, asr_json=None, env=None, log=print):
    """Run P6 end to end. Returns {"exit_code", "report_path", "result"?}."""
    project = Path(project)
    audio_plan = _read_json(project / "work" / "audio-plan.json")
    edit_plan = _read_json(project / "work" / "edit-plan.json")
    intended = build_intended(audio_plan, edit_plan)

    report_path = project / "work" / "verify-report.md"

    if not intended:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        msg = "nothing to verify — no narration/dialogue layers in audio-plan.json\n"
        report_path.write_text(msg)
        log(msg.strip())
        return {"exit_code": 0, "report_path": str(report_path)}

    if asr_json:
        payload = _read_json(Path(asr_json))
        rendered = payload.get("words", [])
    else:
        env = env if env is not None else {}
        api_key = (env.get("ASSEMBLYAI_API_KEY") or "").strip()
        if not api_key:
            msg = "ASSEMBLYAI_API_KEY not set — P6 skipped, not passed"
            log(msg)
            return {"exit_code": 3, "report_path": None}

        master_path = Path(master) if master else default_master(project)
        if not master_path.exists():
            raise VerifyError(f"master not found: {master_path}")

        keyterms = derive_keyterms(project)
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "master.wav"
            _extract_audio(master_path, wav)
            asr_result = transcribe_assemblyai(str(wav), api_key, keyterms=keyterms, log=log)
        rendered = asr_result.get("words", [])
        (project / "work" / "verify-asr.json").write_text(
            json.dumps(asr_result, indent=2, ensure_ascii=False) + "\n"
        )

    result = analyze(intended, rendered)
    report_text = build_report(result)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text)
    log(report_text.splitlines()[0])
    return {"exit_code": result["exit_code"], "report_path": str(report_path), "result": result}


def _load_env():
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
    return env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--master", help="default: output/master-mixed.mp4, else output/master.mp4")
    ap.add_argument("--asr-json", help="replay a saved {\"words\": [...]} instead of AssemblyAI")
    args = ap.parse_args(argv)

    env = _load_env()
    try:
        outcome = verify(args.project, master=args.master, asr_json=args.asr_json, env=env)
        if outcome["report_path"]:
            print(f"wrote {outcome['report_path']}")
        return outcome["exit_code"]
    except VerifyError as exc:
        print(f"verify_render: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
