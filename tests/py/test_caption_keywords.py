import unittest

from tools.caption_keywords import CaptionKeywordError, score_spans


def _w(text_list):
    return [{"text": t} for t in text_list]


class ScoreSpansTest(unittest.TestCase):
    def test_number_unit_span_covers_whole_range(self):
        spans = score_spans(_w("di 1 sampai 4 tahun setelahnya".split()))
        self.assertEqual(spans, [
            {"start_word": 1, "end_word": 4, "score": 9, "rule": "number-unit"},
        ])

    def test_empty_word_list_returns_no_spans(self):
        self.assertEqual(score_spans([]), [])

    def test_single_word_with_no_rule_match_returns_no_spans(self):
        self.assertEqual(score_spans(_w(["halo"])), [])

    def test_words_not_a_list_raises(self):
        with self.assertRaises(CaptionKeywordError):
            score_spans("not a list")

    def test_word_missing_text_raises_naming_index(self):
        with self.assertRaises(CaptionKeywordError) as ctx:
            score_spans([{"text": "ok"}, {"no_text": "oops"}])
        self.assertIn("1", str(ctx.exception))

    def test_tied_scores_sort_earlier_start_first(self):
        spans = score_spans(_w("ANPR jalan lalu OCR".split()))
        self.assertEqual(spans, [
            {"start_word": 0, "end_word": 0, "score": 6, "rule": "acronym"},
            {"start_word": 3, "end_word": 3, "score": 6, "rule": "acronym"},
        ])

    def test_span_ending_on_final_word(self):
        spans = score_spans(_w("harga naik 4 tahun".split()))
        self.assertEqual(spans, [
            {"start_word": 2, "end_word": 3, "score": 9, "rule": "number-unit"},
        ])
        self.assertEqual(spans[0]["end_word"], len("harga naik 4 tahun".split()) - 1)

    def test_acronym_overlapping_number_unit_span_is_dropped(self):
        # "RP" is both a currency unit word and, on its own, an uppercase acronym token.
        # The number-unit span (score 9) must win; no acronym span may survive alongside it.
        spans = score_spans(_w("Ongkos 5 RP saja".split()))
        self.assertEqual(spans, [
            {"start_word": 1, "end_word": 2, "score": 9, "rule": "number-unit"},
        ])

    def test_brand_term_span_from_keyterms(self):
        spans = score_spans(_w("Sistem INDUSIA Gate membaca plat".split()),
                             keyterms=["INDUSIA Gate"])
        self.assertEqual(spans, [
            {"start_word": 1, "end_word": 2, "score": 7, "rule": "brand-term"},
        ])

    def test_reversal_word_scores_four(self):
        spans = score_spans(_w("Murah tapi kuat".split()))
        self.assertEqual(spans, [
            {"start_word": 1, "end_word": 1, "score": 4, "rule": "reversal"},
        ])

    def test_duplicate_keyterms_produce_one_span_not_two(self):
        spans = score_spans(_w("Sistem INDUSIA membaca".split()),
                             keyterms=["INDUSIA", "INDUSIA"])
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0], {"start_word": 1, "end_word": 1, "score": 7, "rule": "brand-term"})


if __name__ == "__main__":
    unittest.main()
