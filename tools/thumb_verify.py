#!/usr/bin/env python3
"""Verdict sheet for rendered thumbnails: nothing is final until it was looked at.

    python3 tools/thumb_verify.py init  <project>
    python3 tools/thumb_verify.py check <project>

`init` writes `packaging/thumb-verify.md`: one section per `packaging/thumb-*.png` with the
image's sha256 and a five-row verdict table for Claude to fill after looking at the image.
Re-running keeps the verdicts of an image whose bytes did not change and clears the rest.

`check` reads only the Verdict cells. Exit 1 on a thumbnail with no section, a missing image,
an image changed after it was judged, or a cell that is empty, malformed or `FAIL:`;
`UNSURE:` is a note for a human. Exit 2 when the sheet does not exist.

Stdlib only.
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

QUESTIONS = ["text spelled correctly", "text legible at phone size",
             "face recognisable (if cast shown)", "one dominant element",
             "matches the video's promise"]
SHEET_HEADER = ("# Thumbnail verify\n\n"
                "Look at each thumbnail, then fill every Verdict cell: `PASS`, "
                "`FAIL: <what is visible>`, or `UNSURE: <why>`.\n\n")
CHANGED_NOTE = "- note: image changed since last judged — verdicts cleared"

_SPLIT_RE = re.compile(r"(?m)^(?=## thumb-)")
_NAME_RE = re.compile(r"## (thumb-[^\n]*?)\s*$", re.M)
_SHA_RE = re.compile(r"(?m)^- sha256: (\S+)")
_ROW_RE = re.compile(r"^\|\s*(\d)\s*\|[^|]*\|(.*)\|\s*$")
_VERDICT_RE = re.compile(r"^(PASS|FAIL:\s*(.*)|UNSURE:\s*(.*))$", re.DOTALL)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _thumbnails(project):
    return sorted((project / "packaging").glob("thumb-*.png"))


def _parse(text):
    """{file name: (section text, sha or None, verdict cells)}"""
    found = {}
    for chunk in _SPLIT_RE.split(text):
        m = _NAME_RE.match(chunk)
        if not m:
            continue
        sha = _SHA_RE.search(chunk)
        verdicts = [""] * len(QUESTIONS)
        for line in chunk.splitlines():
            row = _ROW_RE.match(line)
            if row and 1 <= int(row.group(1)) <= len(QUESTIONS):
                verdicts[int(row.group(1)) - 1] = row.group(2).strip()
        found[m.group(1)] = (chunk.rstrip("\n") + "\n", sha.group(1) if sha else None, verdicts)
    return found


def render_section(name, sha, verdicts=None, note=None):
    verdicts = verdicts or [""] * len(QUESTIONS)
    lines = ["## %s" % name, "", "- sha256: %s" % sha]
    if note:
        lines.append(note)
    lines += ["", "| # | Question | Verdict |", "|---|---|---|"]
    for i, (question, verdict) in enumerate(zip(QUESTIONS, verdicts), 1):
        lines.append("| %d | %s | %s |" % (i, question, verdict) if verdict
                     else "| %d | %s | |" % (i, question))
    return "\n".join(lines) + "\n"


def build_sheet(existing_text, thumbs):
    """Sheet text for the thumbnails on disk. Same sha keeps verdicts; a different one clears
    them and says so."""
    old = _parse(existing_text)
    sections = []
    for path in thumbs:
        sha = _sha256(path)
        prev = old.get(path.name)
        if prev and prev[1] == sha:
            sections.append(render_section(path.name, sha, verdicts=prev[2]))
        elif prev and prev[1] is not None:
            sections.append(render_section(path.name, sha, note=CHANGED_NOTE))
        else:
            sections.append(render_section(path.name, sha))
    return SHEET_HEADER + "\n".join(sections)


def check(project):
    """Returns (problems, notes) as printable lines. Reads only the Verdict cells."""
    sheet = project / "packaging" / "thumb-verify.md"
    sections = _parse(sheet.read_text(encoding="utf-8"))
    on_disk = {p.name: p for p in _thumbnails(project)}
    problems, notes = [], []
    for name in sorted(set(on_disk) | set(sections)):
        if name not in sections:
            problems.append("thumb FAIL %s: no section in packaging/thumb-verify.md" % name)
            continue
        _chunk, sha, verdicts = sections[name]
        if name not in on_disk:
            problems.append("thumb FAIL %s: image is missing on disk" % name)
        elif sha != _sha256(on_disk[name]):
            problems.append("thumb FAIL %s: verdicts were judged against a different image "
                            "(sha256 does not match)" % name)
        for k, cell in enumerate(verdicts, 1):
            m = _VERDICT_RE.match(cell)
            q = QUESTIONS[k - 1]
            if not cell:
                problems.append("thumb FAIL %s q%d: %s has no verdict" % (name, k, q))
            elif not m:
                problems.append("thumb FAIL %s q%d: verdict must start with PASS, FAIL: or "
                                "UNSURE: (got %r)" % (name, k, cell))
            elif m.group(1).startswith("FAIL"):
                problems.append("thumb FAIL %s q%d: %s" % (name, k, m.group(2) or q))
            elif m.group(1).startswith("UNSURE"):
                notes.append("thumb NOTE %s q%d: %s — needs a human look"
                             % (name, k, m.group(3) or q))
    return problems, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["init", "check"])
    ap.add_argument("project")
    args = ap.parse_args(argv)
    project = Path(args.project)
    sheet = project / "packaging" / "thumb-verify.md"

    if args.command == "init":
        thumbs = _thumbnails(project)
        if not thumbs:
            print("thumb_verify: no packaging/thumb-*.png found, nothing to do")
            return 0
        existing = sheet.read_text(encoding="utf-8") if sheet.exists() else ""
        tmp = sheet.with_name(sheet.name + ".tmp")
        tmp.write_text(build_sheet(existing, thumbs), encoding="utf-8")
        os.replace(tmp, sheet)
        print("wrote packaging/thumb-verify.md (%d thumbnails)" % len(thumbs))
        return 0

    if not sheet.exists():
        print("thumb_verify: packaging/thumb-verify.md is missing; run init first",
              file=sys.stderr)
        return 2
    problems, notes = check(project)
    for line in problems + notes:
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
