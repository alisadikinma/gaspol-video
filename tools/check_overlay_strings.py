#!/usr/bin/env python3
"""Fail when a Remotion overlay shows text that the script never approved.

    python3 tools/check_overlay_strings.py shots/src/shots/tempelan \
        --from-markdown av-script.md --heading "Blok 4"
    python3 tools/check_overlay_strings.py shots/src --approved work/approved-strings.txt

The NO INVENTED TEXT rule says every word on a product screen comes from one approved list in
the script. Enforcing it by reading is how invented strings ship: a reviewer scans the prompt,
not the component, and the component is where the words actually are.

What it reads as visible text in a .tsx file:
  - JSX text nodes: `>SETUJUI<`
  - text-bearing props: label, text, title, heading, caption, placeholder, value
  - string arrays assigned to a SCREAMING_CASE const (delivery-note numbers, row labels)

What it ignores: identifiers, CSS values, colours, filenames, import paths, numbers on their own,
and anything inside a line-comment.

Approved list: `--approved FILE` (one string per line, `#` comments) and/or `--from-markdown
FILE --heading "Blok 4"`, which collects every `backtick` code span under that heading until the
next heading of the same or higher level — the layout every gaspol-video av-script already uses.

Matching ignores case and collapses whitespace. A composed line like `KELUAR YARD 08:41` passes
if the whole line is approved, or if it is the join of approved parts (`KELUAR YARD` + `08:41`).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEXT_PROPS = ("label", "text", "title", "heading", "caption", "placeholder", "value")

RE_COMMENT_LINE = re.compile(r"^\s*(//|\*|/\*)")
RE_JSX_TEXT = re.compile(r">([^<>{}\n]{2,})<")
RE_PROP = re.compile(r"\b(" + "|".join(TEXT_PROPS) + r")\s*=\s*[\"']([^\"']{2,})[\"']")
RE_CONST_ARRAY = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*(?::[^=]+)?=\s*\[(.*?)\]", re.S)
RE_STRING = re.compile(r"[\"']([^\"'\n]{2,})[\"']")

# Not visible copy even when it sits where copy sits.
RE_CSSISH = re.compile(
    r"^(#|rgba?\(|\d+(\.\d+)?(px|rem|em|%|deg|s|fr)\b|var\(|--)"
    r"|^(flex|grid|none|auto|center|left|right|bold|italic|solid|hidden|absolute|relative|"
    r"column|row|nowrap|wrap|uppercase|lowercase|capitalize|tabular-nums|transparent|inherit|"
    r"currentColor|pointer|blur|ease|linear|clamp|fill|stroke|middle|start|end|top|bottom)$",
    re.I)
RE_FILEISH = re.compile(r"\.(png|jpe?g|mp4|mov|json|tsx?|css|svg|mp3|wav)$|^[./]|/")
RE_IDENTISH = re.compile(r"^[a-z][a-zA-Z0-9]*$")          # camelCase / single lowercase word
RE_HAS_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def looks_visible(s: str) -> bool:
    s = s.strip()
    if len(s) < 2 or not RE_HAS_LETTER.search(s):
        return False
    if RE_CSSISH.match(s) or RE_FILEISH.search(s) or RE_IDENTISH.match(s):
        return False
    return True


def candidates(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    lines = path.read_text().split("\n")
    for n, line in enumerate(lines, 1):
        if RE_COMMENT_LINE.match(line):
            continue
        code = line.split("//")[0] if "://" not in line else line
        for m in RE_JSX_TEXT.finditer(code):
            if looks_visible(m.group(1)):
                found.append((n, m.group(1).strip()))
        for m in RE_PROP.finditer(code):
            if looks_visible(m.group(2)):
                found.append((n, m.group(2).strip()))
    body = path.read_text()
    for m in RE_CONST_ARRAY.finditer(body):
        start_line = body[:m.start()].count("\n") + 1
        for s in RE_STRING.findall(m.group(1)):
            if looks_visible(s):
                found.append((start_line, s.strip()))
    return found


def approved_from_markdown(md: Path, heading: str) -> set[str]:
    lines = md.read_text().split("\n")
    level, collecting = None, False
    out: set[str] = set()
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if collecting and len(m.group(1)) <= level:
                break
            if heading.casefold() in m.group(2).casefold():
                collecting, level = True, len(m.group(1))
                continue
        if collecting:
            spans = [s for s in re.findall(r"`([^`]+)`", line) if RE_HAS_LETTER.search(s)]
            out.update(spans)
            out.update(expand_series(line, spans))
    if not out:
        print(f"warning: no approved strings found under heading '{heading}' in {md}",
              file=sys.stderr)
    return out


RE_SERIES = re.compile(r"`([^`]+)`\s*(?:…|\.\.\.)\s*`([^`]+)`")


def expand_series(line: str, spans: list[str]) -> set[str]:
    """Expand `KEBOCORAN 1 DARI 6` … `KEBOCORAN 6 DARI 6` into every member of the series.

    Scripts write enumerated on-screen text as first … last. Without this, every middle member
    reads as an invented string.
    """
    out: set[str] = set()
    for first, last in RE_SERIES.findall(line):
        a = re.findall(r"\d+", first)
        b = re.findall(r"\d+", last)
        if len(a) != len(b):
            continue
        # The series runs over the ONE number that differs; everything else must match.
        moving = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(moving) != 1:
            continue
        i = moving[0]
        lo, hi = int(a[i]), int(b[i])
        if not 0 <= hi - lo <= 200:
            continue
        parts = re.split(r"(\d+)", first)
        digit_positions = [k for k, part in enumerate(parts) if part.isdigit()]
        for n in range(lo, hi + 1):
            build = list(parts)
            build[digit_positions[i]] = str(n).zfill(len(a[i]))
            out.add("".join(build))
    return out


def is_approved(text: str, approved: set[str]) -> bool:
    t = norm(text)
    if t in approved:
        return True
    # A composed line counts if it is the join of approved parts, longest first.
    rest = t
    for part in sorted(approved, key=len, reverse=True):
        if part and part in rest:
            rest = rest.replace(part, " ").strip()
            if not rest:
                return True
    return not re.sub(r"[\s·:.,|/-]", "", rest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="a .tsx file or a directory of them")
    ap.add_argument("--approved", help="text file, one approved string per line")
    ap.add_argument("--from-markdown", dest="md", help="script file holding the approved list")
    ap.add_argument("--heading", default="Blok 4", help="heading that holds the list")
    args = ap.parse_args()

    approved: set[str] = set()
    if args.approved:
        for line in Path(args.approved).read_text().split("\n"):
            line = line.split("#")[0].strip()
            if line:
                approved.add(norm(line))
    if args.md:
        approved |= {norm(s) for s in approved_from_markdown(Path(args.md), args.heading)}
    if not approved:
        print("FAIL: no approved strings loaded — pass --approved and/or --from-markdown",
              file=sys.stderr)
        return 2

    root = Path(args.path)
    files = sorted(root.rglob("*.tsx")) if root.is_dir() else [root]
    bad = 0
    checked = 0
    for f in files:
        for line_no, text in candidates(f):
            checked += 1
            if not is_approved(text, approved):
                print(f"FAIL {f}:{line_no}: {text!r} is not in the approved list")
                bad += 1

    print(f"\n{checked - bad}/{checked} on-screen strings approved "
          f"({len(approved)} in the list, {len(files)} file(s) scanned)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
