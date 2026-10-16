#!/usr/bin/env python3
"""Retention gate: five measurable retention rules on a finished cut.

    python3 tools/retention_gate.py report <project> [--master FILE] [--words-file FILE]
                                    [--static-max-s S] [--hook-first-word-by-s S]
                                    [--foreshadow-by-s LO HI] [--bgm-headroom-db DB]
    python3 tools/retention_gate.py check <project>

`report` writes `work/retention-report.md` (one row per rule) and `work/retention-qa.md`
(one section per b-roll segment, with a Verdict cell to fill in-session). It exits 0 even
when a rule FAILS: the numbers are course advice (`source: course`), not platform data, and
the owner decides. Exit 2 means the tool could not run.

`check` reads only the Verdict cells of `work/retention-qa.md` and exits 1 on a missing,
empty, malformed or `FAIL:` cell, or a section judged against different clip bytes.

Stdlib only. Needs ffmpeg and ffprobe.
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import mix_music, qa_frames  # noqa: E402
from tools.vidkit import ff, sheet, speech  # noqa: E402

DEFAULTS = {
    "static_max_s": 3.0,
    "hook_first_word_by_s": 3.0,
    "foreshadow_by_s": (3.0, 6.0),
    "bgm_headroom_db": mix_music.MIN_HEADROOM_DB,
    "source": "course",
}

SOURCE_TAG = "source: course"
EPS = 1e-6


class GateError(RuntimeError):
    """The tool could not run (exit 2)."""


def row(rule, status, numbers, threshold):
    return {"rule": rule, "status": status, "numbers": numbers, "threshold": threshold}


# ---------------------------------------------------------------- R1 static frame

_FREEZE_RE = re.compile(r"freeze_(start|duration|end):\s*([0-9.]+)")


def parse_freezes(stderr, end_of_file):
    """[(start, end, length)] from freezedetect log text. A freeze with a start but no end
    ran to the end of the file."""
    out, start, length, end = [], None, None, None

    def flush():
        if start is None:
            return
        e = end if end is not None else end_of_file
        out.append((start, e, length if length is not None else round(e - start, 3)))

    for kind, value in _FREEZE_RE.findall(stderr):
        v = float(value)
        if kind == "start":
            flush()
            start, length, end = v, None, None
        elif kind == "duration":
            length = v
        else:
            end = v
    flush()
    return out


def static_row(freezes, limit):
    threshold = "no still >= %.1f s" % limit
    bad = [f for f in freezes if f[2] >= limit - EPS]
    if not bad:
        longest = max((f[2] for f in freezes), default=None)
        numbers = ("no still of %.1f s or longer" % limit if longest is None
                   else "longest still %.2f s" % longest)
        return row("R1 static frame", "PASS", numbers, threshold)
    detail = "; ".join("%.2f-%.2f s (%.2f s)" % f for f in bad)
    return row("R1 static frame", "FAIL", "%d freeze(s): %s" % (len(bad), detail), threshold)


def check_static(master, limit):
    total = ff.duration(master)
    log = ff.run(["ffmpeg", "-v", "info", "-nostats", "-i", master, "-vf",
                  "freezedetect=n=0.003:d=%s" % limit, "-an", "-f", "null", "-"],
                 capture_stderr=True)
    return static_row(parse_freezes(log, total), limit)


# ---------------------------------------------------------------- word source

def _norm_word(entry, offset=0.0):
    """(text, start_s, end_s) on the film timeline from either shape the project writes:
    {"text", "start_ms", "end_ms"} (vo-manifest) or {"word"|"text", "start", "end"} seconds."""
    text = entry.get("text", entry.get("word", ""))
    if "start_ms" in entry:
        return (text, offset + float(entry["start_ms"]) / 1000.0,
                offset + float(entry["end_ms"]) / 1000.0)
    return text, offset + float(entry["start"]), offset + float(entry["end"])


def _plan_offsets(project):
    """{vo item id: at_s} from work/audio-plan.json layers (id = stem of the layer's `out`,
    the same key gen_subs uses). Empty when the plan is absent."""
    path = Path(project) / "work" / "audio-plan.json"
    if not path.is_file():
        return {}
    out = {}
    for scene in json.loads(path.read_text(encoding="utf-8")).get("scenes", []):
        for layer in scene.get("layers", []):
            if "out" in layer and "at_s" in layer:
                out[Path(layer["out"]).stem] = float(layer["at_s"])
    return out


def load_words(project, words_file=None):
    """(words, reason). words = sorted [(text, start_s, end_s)] on the film timeline, or None
    with a reason why they are unknown. `--words-file` wins over the manifest. Manifest items
    are placed with their own `at_s`, else the `at_s` of the audio-plan.json layer whose `out`
    names the same file (gen_vo.mjs writes no offsets itself)."""
    project = Path(project)
    try:
        if words_file:
            data = json.loads(Path(words_file).read_text(encoding="utf-8"))
            words = sorted((_norm_word(w) for w in data), key=lambda w: w[1])
            return (words, "") if words else (None, "words file %s has no words" % words_file)
        path = project / "vo" / "vo-manifest.json"
        if not path.is_file():
            return None, "no vo/vo-manifest.json and no --words-file"
        items = [it for it in json.loads(path.read_text(encoding="utf-8")).get("items", [])
                 if it.get("words")]
        if not items:
            return None, "vo-manifest.json has no word timings"
        plan_at = _plan_offsets(project)
        words = []
        for it in items:
            if "at_s" in it:
                offset = float(it["at_s"])
            elif it.get("id") in plan_at:
                offset = plan_at[it["id"]]
            else:
                return None, ("no film offset for vo item %r (no at_s in vo-manifest.json and no "
                              "matching layer in work/audio-plan.json), so word times cannot be "
                              "placed on the film timeline; pass --words-file" % it.get("id"))
            words += [_norm_word(w, offset) for w in it["words"]]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise GateError("word source unreadable: %s" % exc)
    return sorted(words, key=lambda w: w[1]), ""


# ---------------------------------------------------------------- R2 hook

def hook_row(words, reason, limit):
    threshold = "first spoken word by %.1f s" % limit
    if not words:
        return row("R2 hook", "not measured", reason or "no word timings", threshold)
    first = words[0][1]
    return row("R2 hook", "PASS" if first <= limit + EPS else "FAIL",
               "first word %r at %.2f s" % (words[0][0], first), threshold)


# ---------------------------------------------------------------- R3 foreshadow

_TC_RE = re.compile(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)")


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _plain(cell):
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", cell)).strip().lower()


def foreshadow_row(av_text, window):
    lo, hi = window
    threshold = "Foreshadow starts %.1f-%.1f s" % (lo, hi)
    beat_col = None
    found = []
    for line in av_text.splitlines():
        if not line.lstrip().startswith("|"):
            beat_col = None  # table ended: the next one needs its own Beat header
            continue
        cells = _cells(line)
        plain = [_plain(c) for c in cells]
        if beat_col is None and "beat" in plain:
            beat_col = plain.index("beat")
            continue
        if beat_col is not None and beat_col < len(cells) and plain[beat_col].startswith("foreshadow"):
            found.append(cells[0])
    if not found:
        return row("R3 foreshadow", "FAIL", "no Foreshadow beat in av-script.md", threshold)
    m = _TC_RE.search(found[0])
    if not m:
        return row("R3 foreshadow", "not measured",
                   "cannot parse timecode %r" % found[0], threshold)
    start = int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    ok = lo - EPS <= start <= hi + EPS
    return row("R3 foreshadow", "PASS" if ok else "FAIL",
               "Foreshadow starts at %.2f s" % start, threshold)


# ---------------------------------------------------------------- R4 b-roll vs spoken word

QUESTION = "Picture matches the spoken words"
QA_HEADER = ("# Retention QA: b-roll against the spoken word\n\n"
             "Look at each segment's contact sheet and read the words beside it. Fill the Verdict "
             "cell: `PASS`, `FAIL: <what is on screen vs what is said>`, or "
             "`UNSURE: <why the frames cannot tell>`.\n\n")
CHANGED_NOTE = "- note: clip changed since last judged — verdict cleared"
BROLL_ROLES = ("b-roll", "broll")


def load_plan(project):
    """work/edit-plan.json as a dict, None when absent. GateError when it cannot be used."""
    path = Path(project) / "work" / "edit-plan.json"
    if not path.is_file():
        return None
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
        for seg in plan["segments"]:
            seg["src"], float(seg["in_s"]), float(seg["out_s"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise GateError("work/edit-plan.json is not a usable edit plan: %r" % (exc,))
    return plan


def broll_segments(plan):
    """B-roll = every `kind: shot` segment plus any segment with `role: b-roll`. Everything
    else is the main take. Each result carries its place on the film timeline (segment
    lengths include `pad_end_s`, as edit_render lays them out)."""
    out, t = [], 0.0
    for i, seg in enumerate(plan.get("segments", []), 1):
        try:
            length = ((float(seg["out_s"]) - float(seg["in_s"]))
                      + float(seg.get("pad_end_s", 0.0) or 0.0))
        except (TypeError, ValueError) as exc:
            raise GateError("work/edit-plan.json segment %d: non-numeric time (%s)" % (i, exc))
        if seg.get("kind") == "shot" or str(seg.get("role", "")).lower() in BROLL_ROLES:
            out.append({"id": str(seg.get("id") or "seg-%02d" % i), "src": seg["src"],
                        "start": round(t, 3), "end": round(t + length, 3),
                        "in_s": float(seg["in_s"]), "out_s": float(seg["out_s"])})
        t += length
    return out


def _spoken(words, start, end):
    return " ".join(w[0] for w in (words or []) if w[2] > start and w[1] < end)


def render_section(seg, sha, sheet_rel, spoken, verdict="", note=None):
    lines = ["## Segment %s" % seg["id"], "",
             "- src: %s" % seg["src"],
             "- src_sha256: %s" % sha,
             "- range: %.2f-%.2f s" % (seg["start"], seg["end"]),
             "- sheet: %s" % sheet_rel,
             "- spoken: %s" % (spoken or "(no words overlap this range)")]
    if note:
        lines.append(note)
    cell = "| %s | %s |" % (QUESTION, verdict) if verdict else "| %s | |" % QUESTION
    lines += ["", "| Question | Verdict |", "|---|---|", cell]
    return "\n".join(lines) + "\n"


_SPLIT_RE = re.compile(r"(?m)^(?=## Segment .+$)")
_ID_RE = re.compile(r"## Segment (.+?)[ \t]*$", re.M)
_SHA_RE = re.compile(r"(?m)^- src_sha256: (\S+)")
_CELL_RE = re.compile(r"(?m)^\|\s*%s\s*\|(.*)\|\s*$" % re.escape(QUESTION))


def _parse_qa(text):
    """{segment id: (chunk, src_sha256 or None, verdict cell)}"""
    found = {}
    for chunk in _SPLIT_RE.split(text):
        m = _ID_RE.match(chunk)
        if not m:
            continue
        sha, cell = _SHA_RE.search(chunk), _CELL_RE.search(chunk)
        found[m.group(1)] = (chunk.rstrip("\n") + "\n", sha.group(1) if sha else None,
                             cell.group(1).strip() if cell else "")
    return found


def _make_sheet(master, seg, project):
    tmp = project / ".tmp"
    tmp.mkdir(exist_ok=True)
    safe = re.sub(r"[^\w.-]", "_", seg["id"])
    cut, out = tmp / ("retention-seg-%s.mp4" % safe), tmp / ("retention-seg-%s.jpg" % safe)
    try:
        ff.ffmpeg("-ss", seg["start"], "-t", round(seg["end"] - seg["start"], 3), "-i", master,
                  "-an", "-c:v", "libx264", "-preset", "ultrafast", cut)
        sheet.contact_sheet(str(cut), str(out))
    finally:
        cut.unlink(missing_ok=True)
    return out.relative_to(project).as_posix()


def _fingerprint(seg, src):
    """What a verdict was judged against: the cut points and the clip bytes."""
    key = "%s|%s|%s" % (seg["in_s"], seg["out_s"], qa_frames._sha256(src))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def build_qa(project, master, plan, words):
    """Write work/retention-qa.md for the plan's b-roll. Verdicts survive for a src whose
    bytes did not change and are cleared, with a note, for one that did. Returns the segments."""
    project = Path(project)
    segs = broll_segments(plan)
    qa_path = project / "work" / "retention-qa.md"
    old = _parse_qa(qa_path.read_text(encoding="utf-8")) if qa_path.is_file() else {}
    merged = {k: v[0] for k, v in old.items()}
    for seg in segs:
        src = project / seg["src"]
        if not src.is_file():
            print("segment %s  skipped: %s is missing on disk" % (seg["id"], seg["src"]))
            continue
        sha, prev = _fingerprint(seg, src), old.get(seg["id"])
        sheet_rel = _make_sheet(master, seg, project)
        spoken = _spoken(words, seg["start"], seg["end"])
        if prev and prev[1] == sha:
            merged[seg["id"]] = render_section(seg, sha, sheet_rel, spoken, verdict=prev[2])
        elif prev and prev[1] is not None:
            merged[seg["id"]] = render_section(seg, sha, sheet_rel, spoken, note=CHANGED_NOTE)
        else:
            merged[seg["id"]] = render_section(seg, sha, sheet_rel, spoken)
    qa_path.parent.mkdir(exist_ok=True)
    tmp_path = qa_path.with_name(qa_path.name + ".tmp")
    tmp_path.write_text(QA_HEADER + "\n".join(merged[k] for k in sorted(merged)), encoding="utf-8")
    os.replace(tmp_path, qa_path)
    return segs


def check_qa(project, plan):
    """(problems, notes) over work/retention-qa.md. Only the Verdict cells are read."""
    project = Path(project)
    qa_path = project / "work" / "retention-qa.md"
    sections = _parse_qa(qa_path.read_text(encoding="utf-8")) if qa_path.is_file() else {}
    problems, notes = [], []
    for seg in broll_segments(plan):
        label = "segment %s" % seg["id"]
        if seg["id"] not in sections:
            problems.append("R4 FAIL %s: no section in work/retention-qa.md" % label)
            continue
        _chunk, sha, cell = sections[seg["id"]]
        src = project / seg["src"]
        if not src.is_file():
            problems.append("R4 FAIL %s: %s is missing on disk" % (label, seg["src"]))
        elif sha != _fingerprint(seg, src):
            problems.append("R4 FAIL %s: verdict was judged against a different clip "
                            "(src_sha256 does not match %s)" % (label, seg["src"]))
        m = qa_frames._VERDICT_RE.match(cell)
        if not cell:
            problems.append("R4 FAIL %s: no verdict" % label)
        elif not m:
            problems.append("R4 FAIL %s: verdict must start with PASS, FAIL: or UNSURE: (got %r)"
                            % (label, cell))
        elif m.group(1).startswith("FAIL"):
            problems.append("R4 FAIL %s: %s" % (label, m.group(2) or "picture does not match words"))
        elif m.group(1).startswith("UNSURE"):
            notes.append("R4 NOTE %s: %s — needs a human look" % (label, m.group(3) or "unsure"))
    return problems, notes


def broll_row(project, plan):
    threshold = "every b-roll segment judged PASS in work/retention-qa.md"
    if plan is None:
        return row("R4 b-roll vs word", "not measured", "no work/edit-plan.json", threshold)
    n = len(broll_segments(plan))
    if n == 0:
        return row("R4 b-roll vs word", "PASS", "0 b-roll segments", threshold)
    problems, notes = check_qa(project, plan)
    fails = [p for p in problems if "no verdict" not in p and "no section" not in p]
    pending = len(problems) - len(fails)
    if fails:
        return row("R4 b-roll vs word", "FAIL", "%d of %d segments failed" % (len(fails), n), threshold)
    if pending:
        return row("R4 b-roll vs word", "needs verdict",
                   "%d of %d segments await a verdict (work/retention-qa.md)" % (pending, n), threshold)
    return row("R4 b-roll vs word", "PASS",
               "%d segments judged, %d unsure" % (n, len(notes)), threshold)


# ---------------------------------------------------------------- R5 BGM against the voice

SPEECH_FLOOR_DBFS = -50.0
HOP_S = 0.1


def words_to_spans(words, pad=0.15):
    """Speech intervals from word times, via speech.speech_spans (one layer per word)."""
    layers = [{"at": w[1], "words": [{"start": 0.0, "end": w[2] - w[1]}]} for w in words]
    return speech.speech_spans(layers, pad=pad)


def active_spans(voice_path, total):
    """Where the voice stem is above the speech floor, merged across single quiet hops."""
    spans = []
    for t, db in speech.energy_db(voice_path, 0.0, total, hop=HOP_S):
        if db > SPEECH_FLOOR_DBFS:
            if spans and t - spans[-1][1] <= HOP_S * 1.5:
                spans[-1][1] = t + HOP_S
            else:
                spans.append([t, t + HOP_S])
    return [(a, b) for a, b in spans]


def _mean_db(path, a, b):
    values = [db for _t, db in speech.energy_db(path, a, b, hop=HOP_S)]
    if not values:
        return None
    return 10 * math.log10(sum(10 ** (v / 10) for v in values) / len(values))


def bgm_row(voice_path, music_path, spans, limit):
    """FAIL when, inside any spoken span, the voice is less than `limit` dB above the music."""
    threshold = "voice >= %.1f dB over music in every spoken span" % limit
    missing = [Path(p).name for p in (voice_path, music_path) if not Path(p).is_file()]
    if missing:
        return row("R5 bgm headroom", "not measured",
                   "stem missing: %s (run tools/make_stems.py --all)" % ", ".join(missing), threshold)
    if spans is None:
        spans = active_spans(voice_path, ff.duration(voice_path))
    worst = None
    for a, b in spans:
        v, m = _mean_db(voice_path, a, b), _mean_db(music_path, a, b)
        if v is None or m is None or v <= SPEECH_FLOOR_DBFS:
            continue
        if worst is None or v - m < worst[0]:
            worst = (v - m, a, b)
    if worst is None:
        return row("R5 bgm headroom", "not measured", "no spoken span found in the voice stem", threshold)
    numbers = ("min headroom %.1f dB at %.2f-%.2f s (%d spans; overall voice %.1f dBFS, music %.1f dBFS)"
               % (worst + (len(spans), mix_music.level_dbfs(voice_path), mix_music.level_dbfs(music_path))))
    return row("R5 bgm headroom", "PASS" if worst[0] >= limit - EPS else "FAIL", numbers, threshold)


# ---------------------------------------------------------------- report and CLI

def _num(x, key):
    if isinstance(x, (bool, str)):
        raise TypeError(key)
    return float(x)


def resolve_config(project, args):
    """DEFAULTS, then work/retention.json, then command-line flags."""
    cfg = dict(DEFAULTS)
    path = Path(project) / "work" / "retention.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise GateError("work/retention.json is not valid JSON: %s" % exc)
        unknown = sorted(set(data) - set(DEFAULTS) - {"source"})
        if unknown:
            raise GateError("work/retention.json: unknown key(s) %s (allowed: %s)"
                            % (", ".join(unknown), ", ".join(k for k in DEFAULTS if k != "source")))
        cfg.update({k: v for k, v in data.items() if k != "source"})
    for key in ("static_max_s", "hook_first_word_by_s", "foreshadow_by_s", "bgm_headroom_db"):
        value = getattr(args, key, None)
        if value is not None:
            cfg[key] = value
    try:
        for key in ("static_max_s", "hook_first_word_by_s", "bgm_headroom_db"):
            cfg[key] = _num(cfg[key], key)
        cfg["foreshadow_by_s"] = tuple(
            _num(x, "foreshadow_by_s") for x in cfg["foreshadow_by_s"])
    except (TypeError, ValueError):
        raise GateError("retention settings must be numbers (foreshadow_by_s: two numbers LO HI)")
    if len(cfg["foreshadow_by_s"]) != 2 or cfg["foreshadow_by_s"][0] > cfg["foreshadow_by_s"][1]:
        raise GateError("foreshadow_by_s must be two numbers LO HI with LO <= HI")
    return cfg


def render_report(rows):
    lines = ["# Retention report", "",
             "Course advice, not platform data. A FAIL here is a flag for the owner, not a block.", "",
             "| rule | status | numbers | threshold | source |", "|---|---|---|---|---|"]
    lines += ["| %s | %s | %s | %s | %s |" % (r["rule"], r["status"], r["numbers"].replace("|", "/"),
                                              r["threshold"], SOURCE_TAG) for r in rows]
    return "\n".join(lines) + "\n"


def run_report(project, master, words_file, cfg, log=print):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise GateError("ffmpeg and ffprobe are required and were not found on PATH")
    if not master.is_file():
        raise GateError("master not found: %s (pass --master)" % master)
    plan = load_plan(project)
    words, why = load_words(project, words_file)
    rows = []
    try:
        rows.append(check_static(str(master), cfg["static_max_s"]))
    except ff.FFError as exc:
        raise GateError("freeze detection failed on %s: %s" % (master.name, (str(exc).splitlines() or [repr(exc)])[-1]))
    rows.append(hook_row(words, why, cfg["hook_first_word_by_s"]))
    av_path = project / "av-script.md"
    rows.append(foreshadow_row(av_path.read_text(encoding="utf-8"), cfg["foreshadow_by_s"])
                if av_path.is_file()
                else row("R3 foreshadow", "not measured", "no av-script.md",
                         "Foreshadow starts %.1f-%.1f s" % cfg["foreshadow_by_s"]))
    if plan is not None:
        try:
            build_qa(project, str(master), plan, words)
        except ff.FFError as exc:
            raise GateError("contact sheet failed: %s" % (str(exc).splitlines() or [repr(exc)])[-1])
    rows.append(broll_row(project, plan))
    stems = project / "output" / "stems"
    try:
        rows.append(bgm_row(str(stems / "voice.wav"), str(stems / "music.wav"),
                            words_to_spans(words) if words else None, cfg["bgm_headroom_db"]))
    except (ff.FFError, mix_music.MusicError, RuntimeError) as exc:
        raise GateError("bgm headroom measurement failed: %s" % (str(exc).splitlines() or [repr(exc)])[-1])
    report = render_report(rows)
    out = project / "work" / "retention-report.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report, encoding="utf-8")
    log(report.rstrip())
    log("wrote %s" % out.relative_to(project).as_posix())
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("report", help="measure R1-R5 and write work/retention-report.md")
    chk = sub.add_parser("check", help="gate on the Verdict cells of work/retention-qa.md")
    for p in (rep, chk):
        p.add_argument("project")
    rep.add_argument("--master", help="master file (default <project>/output/master.mp4)")
    rep.add_argument("--words-file", help="JSON word list on the film timeline, seconds")
    rep.add_argument("--static-max-s", dest="static_max_s", type=float)
    rep.add_argument("--hook-first-word-by-s", dest="hook_first_word_by_s", type=float)
    rep.add_argument("--foreshadow-by-s", dest="foreshadow_by_s", type=float, nargs=2,
                     metavar=("LO", "HI"))
    rep.add_argument("--bgm-headroom-db", dest="bgm_headroom_db", type=float)
    args = ap.parse_args(argv)

    project = Path(args.project)
    try:
        if not project.is_dir():
            raise GateError("project folder not found: %s" % project)
        if args.cmd == "check":
            plan = load_plan(project)
            if plan is None:
                raise GateError("no work/edit-plan.json: nothing to check")
            problems, notes = check_qa(project, plan)
            for line in problems + notes:
                print(line)
            return 1 if problems else 0
        cfg = resolve_config(project, args)
        master = Path(args.master) if args.master else project / "output" / "master.mp4"
        run_report(project, master, args.words_file, cfg)
        return 0
    except GateError as exc:
        print("retention_gate: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
