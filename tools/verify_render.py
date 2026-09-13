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
import urllib.error
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.gen_subs import SubtitleError, derive_keyterms, transcribe_assemblyai  # noqa: E402

FFMPEG = shutil.which("ffmpeg")

GAP_S = 0.40
LOW_CONFIDENCE = 0.70
DRIFT_S = 0.25


class VerifyError(Exception):
    """The render cannot be verified as asked. Message names the offending file."""


# -- Number-word collapsing ----------------------------------------------------------
#
# A script may spell a number in words ("empat puluh dua") while AssemblyAI's own
# transcript formatting collapses the spoken equivalent to digits ("42"), or vice versa.
# Left alone, the word-level diff sees a 3-word run replaced by a 1-word token and
# reports two of the three words as missing/inserted — a false P6 FAIL on a render that
# is actually correct. `collapse_numbers` normalises both sides to the same canonical
# digit token before the diff ever runs.

_ID_UNITS = {
    "nol": 0, "kosong": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
}
_ID_TERMINAL = {"sepuluh": 10, "sebelas": 11}
_ID_BIG_SCALES = [("miliar", 10 ** 9), ("milyar", 10 ** 9), ("juta", 10 ** 6), ("ribu", 10 ** 3)]
_ID_SE_PREFIXED = {
    "seratus": ("satu", "ratus"), "seribu": ("satu", "ribu"),
    "sejuta": ("satu", "juta"), "semiliar": ("satu", "miliar"), "semilyar": ("satu", "milyar"),
}
_ID_NUMBER_WORDS = (
    set(_ID_UNITS) | set(_ID_TERMINAL) | set(_ID_SE_PREFIXED)
    | {"puluh", "ratus", "belas", "ribu", "juta", "miliar", "milyar"}
)

_EN_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9,
}
_EN_TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_EN_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_EN_SCALES = {"hundred": 100, "thousand": 1000, "million": 1000000, "billion": 1000000000}
_EN_NUMBER_WORDS = set(_EN_UNITS) | set(_EN_TEENS) | set(_EN_TENS) | set(_EN_SCALES) | {"and"}

_THOUSANDS_RE = re.compile(r"\d{1,3}(?:[.,]\d{3})+")


def _id_parse_small(words):
    """Parse a run of Indonesian number words worth < 1000 (no ribu/juta/miliar)."""
    if not words:
        return 0
    if len(words) == 1:
        if words[0] in _ID_TERMINAL:
            return _ID_TERMINAL[words[0]]
        if words[0] in _ID_UNITS:
            return _ID_UNITS[words[0]]
    if "ratus" in words:
        i = words.index("ratus")
        prefix_val = _id_parse_small(words[:i]) if words[:i] else 1
        rest = _id_parse_small(words[i + 1:])
        return None if prefix_val is None or rest is None else prefix_val * 100 + rest
    if "belas" in words:
        i = words.index("belas")
        prefix_val = _id_parse_small(words[:i]) if words[:i] else 1
        return None if prefix_val is None else prefix_val + 10
    if "puluh" in words:
        i = words.index("puluh")
        prefix_val = _id_parse_small(words[:i]) if words[:i] else 1
        rest = _id_parse_small(words[i + 1:])
        return None if prefix_val is None or rest is None else prefix_val * 10 + rest
    return None


def parse_id_number_words(words):
    """Parse a maximal run of Indonesian number words into an int, or None."""
    if not words:
        return None
    expanded = []
    for w in words:
        expanded.extend(_ID_SE_PREFIXED.get(w, (w,)))
    for name, mult in _ID_BIG_SCALES:
        if name in expanded:
            i = expanded.index(name)
            prefix = expanded[:i]
            prefix_val = _id_parse_small(prefix) if prefix else 1
            tail = expanded[i + 1:]
            rest = parse_id_number_words(tail) if tail else 0
            if prefix_val is None or rest is None:
                return None
            return prefix_val * mult + rest
    return _id_parse_small(expanded)


def parse_en_number_words(words):
    """Parse a maximal run of English number words into an int, or None."""
    if not words:
        return None
    current = 0
    total = 0
    has_value = False
    for w in words:
        if w == "and":
            continue
        if w in _EN_UNITS:
            current += _EN_UNITS[w]
            has_value = True
        elif w in _EN_TEENS:
            current += _EN_TEENS[w]
            has_value = True
        elif w in _EN_TENS:
            current += _EN_TENS[w]
            has_value = True
        elif w == "hundred":
            current = (current or 1) * 100
            has_value = True
        elif w in _EN_SCALES:
            total += (current or 1) * _EN_SCALES[w]
            current = 0
            has_value = True
        else:
            return None
    return (total + current) if has_value else None


def collapse_number_runs(words):
    """[w0, w1, ...] -> [(token, span), ...]. A maximal run of number words (Indonesian
    or English) becomes one (canonical digit string, run length) pair; every other word
    passes through as (word, 1)."""
    out = []
    i, n = 0, len(words)
    while i < n:
        w = words[i]
        value, span = None, 0
        if w in _ID_NUMBER_WORDS:
            j = i
            while j < n and words[j] in _ID_NUMBER_WORDS:
                j += 1
            v = parse_id_number_words(words[i:j])
            if v is not None:
                value, span = v, j - i
        if value is None and w in _EN_NUMBER_WORDS:
            j = i
            while j < n and words[j] in _EN_NUMBER_WORDS:
                j += 1
            v = parse_en_number_words(words[i:j])
            if v is not None:
                value, span = v, j - i
        if value is not None:
            out.append((str(value), span))
            i += span
        else:
            out.append((w, 1))
            i += 1
    return out


def collapse_numbers(tokens):
    """Pure [word, ...] -> [word, ...] with every maximal number-word run replaced by
    one canonical digit token. Non-number words (and already-digit tokens) pass through
    unchanged."""
    return [tok for tok, _ in collapse_number_runs(tokens)]


def norm(text):
    """Lowercase, merge thousands-separated digit groups ("2.026"/"2,026" -> "2026"), map
    "%"/"percent" to the language-neutral token "persen", strip remaining punctuation
    except apostrophes, and split into words. Digits are otherwise kept as-is —
    Indonesian scripts write numbers as digits ("42"), not words."""
    t = (text or "").lower()
    t = _THOUSANDS_RE.sub(lambda m: m.group(0).replace(".", "").replace(",", ""), t)
    t = t.replace("%", " persen ")
    t = re.sub(r"\bpercent\b", "persen", t)
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
    segments than scenes — the diff still runs, drift just skips that layer). A maximal
    run of number words within a layer's text collapses into one canonical digit entry,
    whose planned time is taken from the FIRST word of that run — see collapse_number_runs."""
    starts = scene_starts(edit_plan)
    entries = []
    layer_id = 0
    scenes = sorted(audio_plan.get("scenes", []), key=lambda s: s.get("scene", 0))
    for scene in scenes:
        layers = [l for l in scene.get("layers", []) if l.get("kind") in ("narration", "dialogue")]
        layers = sorted(layers, key=lambda l: float(l.get("at_s", 0.0)))
        for layer in layers:
            layer_id += 1
            raw_words = norm(layer.get("text", ""))
            if not raw_words:
                continue
            scene_start = starts.get(scene.get("scene"))
            at_s = float(layer.get("at_s", 0.0))
            dur_s = float(layer.get("dur_s", 0.0) or 0.0)
            planned_layer_s = (scene_start + at_s) if scene_start is not None else None
            n = len(raw_words)
            pos = 0
            for word, span in collapse_number_runs(raw_words):
                if planned_layer_s is not None and dur_s > 0:
                    planned_word_s = planned_layer_s + dur_s * (pos / n)
                else:
                    planned_word_s = planned_layer_s
                entries.append({
                    "scene": scene.get("scene"), "layer_id": layer_id, "word": word,
                    "planned_word_s": planned_word_s, "planned_layer_s": planned_layer_s,
                })
                pos += span
    return entries


def flatten_rendered(words):
    """ASR word dicts -> (collapsed token list, parallel metadata list). Each metadata
    entry is {"start_ms", "end_ms", "text", "orig_idxs"} — one per token after per-word
    normalisation AND cross-word number-run collapsing. `orig_idxs` lists every index
    into `words` the token was built from: a single index normally, several when a
    number-word run spanning multiple ASR words collapsed into one digit token (the
    token then takes the start of its first source word and the end of its last)."""
    pieces, piece_idx = [], []
    for i, w in enumerate(words):
        for piece in norm(w.get("text", "")):
            pieces.append(piece)
            piece_idx.append(i)

    out, meta = [], []
    pos = 0
    for token, span in collapse_number_runs(pieces):
        idxs = sorted(set(piece_idx[pos:pos + span]))
        first, last = idxs[0], idxs[-1]
        out.append(token)
        meta.append({
            "start_ms": words[first].get("start_ms"),
            "end_ms": words[last].get("end_ms"),
            "text": token,
            "orig_idxs": idxs,
        })
        pos += span
    return out, meta


def analyze(intended, rendered, gap_s=GAP_S, low_confidence=LOW_CONFIDENCE, drift_s=DRIFT_S):
    """Diff the intended script words against the rendered ASR words. A word-swap ("replace")
    is reported as "heard differently", never counted toward missing/inserted — those two are
    reserved for content that is truly absent or truly extra, which is what P6 fails on."""
    a_words = [e["word"] for e in intended]
    b_words, b_meta = flatten_rendered(rendered)

    matched = [False] * len(rendered)
    render_layer = [None] * len(rendered)
    inserted, missing, replaced = [], [], []

    def _mark(meta_entry, layer_id):
        for ridx in meta_entry["orig_idxs"]:
            matched[ridx] = True
            render_layer[ridx] = layer_id

    matcher = SequenceMatcher(None, a_words, b_words, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k, j in enumerate(range(j1, j2)):
                _mark(b_meta[j], intended[i1 + k]["layer_id"])
        elif tag == "insert":
            for j in range(j1, j2):
                m = b_meta[j]
                inserted.append({"start_ms": m["start_ms"], "text": m["text"]})
        elif tag == "delete":
            for i in range(i1, i2):
                missing.append(intended[i])
        elif tag == "replace":
            len_i, len_j = i2 - i1, j2 - j1
            for k in range(max(len_i, len_j)):
                exp = intended[i1 + k] if k < len_i else None
                m = b_meta[j1 + k] if k < len_j else None
                if exp is not None and m is not None:
                    replaced.append({"start_ms": m["start_ms"], "heard": m["text"],
                                      "expected": exp["word"]})
                    _mark(m, exp["layer_id"])
                elif m is not None:
                    inserted.append({"start_ms": m["start_ms"], "text": m["text"]})
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
    header_line = report_text.splitlines()[0]

    scene_count = len(audio_plan.get("scenes", []))
    segment_count = len(edit_plan.get("segments", []))
    if segment_count < scene_count:
        note = f"drift check skipped: {segment_count} edit segments for {scene_count} scenes"
        log(note)
        report_text = note + "\n\n" + report_text

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text)
    log(header_line)
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
    except SubtitleError as exc:
        print(f"verify_render: {exc}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"verify_render: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
