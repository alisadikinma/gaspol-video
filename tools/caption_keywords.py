#!/usr/bin/env python3
"""Score candidate keyword spans for kinetic captions.

Pure scoring: given a scene's already-timed word list, decide which run of words
deserves the highlight box on a caption page. Text and timing both come from
elsewhere (the script, and vo/vo-manifest.json or AssemblyAI); this module never
invents either — it only ranks spans that are already there.

Rules, highest score wins on overlap:
  number-unit (9)  a digit run or a spelled Indonesian number together with an
                    adjacent unit/currency/time word, including an interior
                    sampai/hingga/- connector.
  brand-term  (7)  a term from gen_subs.derive_keyterms(project), passed in by
                    the caller as `keyterms`.
  acronym     (6)  a 2+ character token of uppercase letters/digits with at
                    least one letter.
  reversal    (4)  one of a closed list of Indonesian contrast words.

Stdlib only.
"""

import re

NUMBER_WORDS = {
    "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh",
}
MULTIPLIER_WORDS = {"puluh", "ratus", "ribu", "juta", "miliar"}
UNIT_WORDS = {"rp", "%", "tahun", "bulan", "hari", "jam", "detik", "menit", "kali", "persen"}
CONNECTOR_WORDS = {"sampai", "hingga", "-"}
REVERSAL_WORDS = {"tapi", "tetapi", "justru", "bukan", "hanya", "malah", "padahal"}

_TRAILING_PUNCT = ".,;:!?()[]{}\"'’‘"

_DIGIT_RUN = re.compile(r"\d+([.,]\d+)?")
_DIGIT_PCT = re.compile(r"\d+([.,]\d+)?%")
_RP_AMOUNT = re.compile(r"rp\.?\d+([.,]\d+)?", re.IGNORECASE)
_ACRONYM = re.compile(r"[A-Z0-9]+")


class CaptionKeywordError(Exception):
    """The word list cannot be scored as given."""


def _normalize(text):
    return text.strip(_TRAILING_PUNCT)


def _is_number(norm_lower):
    if norm_lower in NUMBER_WORDS or norm_lower in MULTIPLIER_WORDS:
        return True
    return bool(_DIGIT_RUN.fullmatch(norm_lower)) or bool(_DIGIT_PCT.fullmatch(norm_lower))


def _is_unit(norm_lower):
    if norm_lower in UNIT_WORDS:
        return True
    if _DIGIT_PCT.fullmatch(norm_lower):
        return True
    return bool(_RP_AMOUNT.fullmatch(norm_lower))


def _is_connector(norm_lower):
    return norm_lower in CONNECTOR_WORDS


def _is_component(norm_lower):
    return _is_number(norm_lower) or _is_unit(norm_lower) or _is_connector(norm_lower)


def _is_acronym(stripped):
    if len(stripped) < 2:
        return False
    if not _ACRONYM.fullmatch(stripped):
        return False
    return any(ch.isalpha() for ch in stripped)


def _extract_texts(words):
    if not isinstance(words, list):
        raise CaptionKeywordError(f"words must be a list, got {type(words).__name__}")
    texts = []
    for i, w in enumerate(words):
        if not isinstance(w, dict) or "text" not in w:
            raise CaptionKeywordError(f"word at index {i} is missing 'text'")
        texts.append(w["text"])
    return texts


def _number_unit_spans(norms):
    """Maximal runs of number/unit/connector tokens, trimmed to start and end on
    a number or unit token, kept only when at least one of each is present."""
    spans = []
    n = len(norms)
    i = 0
    while i < n:
        if not _is_component(norms[i]):
            i += 1
            continue
        j = i
        while j < n and _is_component(norms[j]):
            j += 1
        start, end = i, j - 1
        while start <= end and not (_is_number(norms[start]) or _is_unit(norms[start])):
            start += 1
        while end >= start and not (_is_number(norms[end]) or _is_unit(norms[end])):
            end -= 1
        if start <= end:
            seg = norms[start:end + 1]
            if any(_is_number(t) for t in seg) and any(_is_unit(t) for t in seg):
                spans.append({"start_word": start, "end_word": end, "score": 9, "rule": "number-unit"})
        i = j
    return spans


def _brand_term_spans(norms, keyterms):
    spans = []
    if not keyterms:
        return spans
    n = len(norms)
    for term in keyterms:
        term_norms = [_normalize(t).lower() for t in term.split()]
        if not term_norms:
            continue
        tlen = len(term_norms)
        for start in range(0, n - tlen + 1):
            if norms[start:start + tlen] == term_norms:
                spans.append({"start_word": start, "end_word": start + tlen - 1,
                              "score": 7, "rule": "brand-term"})
    return spans


def _acronym_spans(raw_texts):
    spans = []
    for i, raw in enumerate(raw_texts):
        if _is_acronym(_normalize(raw)):
            spans.append({"start_word": i, "end_word": i, "score": 6, "rule": "acronym"})
    return spans


def _reversal_spans(norms):
    spans = []
    for i, norm in enumerate(norms):
        if norm in REVERSAL_WORDS:
            spans.append({"start_word": i, "end_word": i, "score": 4, "rule": "reversal"})
    return spans


def score_spans(words, keyterms=None):
    """words: list of {"text": str, ...}. keyterms: optional list of brand terms
    (see gen_subs.derive_keyterms), each may be a multi-word phrase. Returns list of
    {"start_word": int, "end_word": int, "score": int, "rule": str},
    sorted by (-score, start_word). Spans never overlap: the higher score wins,
    ties go to the earlier span."""
    raw_texts = _extract_texts(words)
    norms = [_normalize(t).lower() for t in raw_texts]

    candidates = []
    candidates.extend(_number_unit_spans(norms))
    candidates.extend(_brand_term_spans(norms, keyterms))
    candidates.extend(_acronym_spans(raw_texts))
    candidates.extend(_reversal_spans(norms))

    candidates.sort(key=lambda s: (-s["score"], s["start_word"]))

    selected = []
    for cand in candidates:
        overlaps = any(
            cand["start_word"] <= s["end_word"] and s["start_word"] <= cand["end_word"]
            for s in selected
        )
        if not overlaps:
            selected.append(cand)

    return selected
