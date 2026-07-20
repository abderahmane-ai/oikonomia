"""Tests for numeral-context mining — the evidence a lexicon is built from."""

from __future__ import annotations

import json

import pandas as pd

from oikonomia.labeling.mine import mine_batches, mine_document, tokenize
from oikonomia.labeling.normalize import normalize


def test_tokenize_splits_on_non_greek() -> None:
    tokens = tokenize(normalize("ἀργυρίου δραχμὰς μ").text)
    assert [t for t, _ in tokens] == ["αργυριου", "δραχμασ", "μ"]


def test_token_spans_locate_the_token() -> None:
    folded = normalize("πυρου αρταβαι").text
    for token, span in tokenize(folded):
        assert folded[span.start : span.end] == token


def test_tokenize_handles_empty_and_punctuation_only() -> None:
    assert tokenize("") == []
    assert tokenize(" . , ") == []


def _doc(line: str, numeral: str) -> dict:
    """One-line document with ``numeral`` located where it occurs in ``line``."""
    start = line.index(numeral)
    return {
        "edited_text": line,
        "lines": [{"n": "1", "edited": {"start": 0, "end": len(line)}}],
        "numerals": [
            {"text": numeral, "edited": {"start": start, "end": start + len(numeral)}}
        ],
    }


def test_mine_yields_neighbours_with_side_and_surface_form() -> None:
    doc = _doc("πυροῦ ἀρτάβαι ιβ λοιπαί", "ιβ")
    got = list(mine_document(doc, window=2))
    assert ("αρταβαι", "left", "ἀρτάβαι") in got
    assert ("πυρου", "left", "πυροῦ") in got
    assert ("λοιπαι", "right", "λοιπαί") in got


def test_window_limits_how_far_context_reaches() -> None:
    doc = _doc("α β γ δ ιβ", "ιβ")
    one = [t for t, side, _ in mine_document(doc, window=1) if side == "left"]
    assert one == ["δ"]


def test_context_does_not_cross_line_boundaries() -> None:
    """Adjacent lines are different transactions; reading across invents links."""
    text = "δραχμαι μ\nὁμοίως β"
    doc = {
        "edited_text": text,
        "lines": [
            {"n": "1", "edited": {"start": 0, "end": 9}},
            {"n": "2", "edited": {"start": 10, "end": len(text)}},
        ],
        "numerals": [{"text": "β", "edited": {"start": len(text) - 1, "end": len(text)}}],
    }
    tokens = {t for t, _, _ in mine_document(doc)}
    assert "ομοιωσ" in tokens
    assert "δραχμαι" not in tokens


def test_numerals_without_a_locatable_span_are_skipped() -> None:
    doc = {
        "edited_text": "δραχμαι μ",
        "lines": [{"n": "1", "edited": {"start": 0, "end": 9}}],
        "numerals": [{"text": "", "edited": None}],
    }
    assert list(mine_document(doc)) == []


def test_ranking_counts_documents_not_occurrences() -> None:
    """One document repeating a word must not outrank a word used widely."""
    spammy = json.dumps(_doc("ρ ρ ρ ρ ρ ιβ", "ιβ") | {"edited_text": "ρ ρ ρ ρ ρ ιβ"})
    repeated = [spammy] * 1
    common = [json.dumps(_doc("δραχμαι ιβ", "ιβ")) for _ in range(6)]
    df = pd.DataFrame({"document_json": [*repeated, *common]})

    candidates = mine_batches([df], window=5, min_docs=2)
    by_token = {c.token: c for c in candidates}
    assert by_token["δραχμαι"].n_docs == 6


def test_min_docs_filters_rare_tokens() -> None:
    docs = [json.dumps(_doc("δραχμαι ιβ", "ιβ")), json.dumps(_doc("σπανιον ιβ", "ιβ"))]
    df = pd.DataFrame({"document_json": docs})
    tokens = {c.token for c in mine_batches([df], min_docs=2)}
    assert tokens == set()  # each token appears in only one document


def test_right_ratio_reports_which_side_a_token_favours() -> None:
    docs = [json.dumps(_doc("δραχμαι ιβ", "ιβ")) for _ in range(3)]
    df = pd.DataFrame({"document_json": docs})
    (candidate,) = [c for c in mine_batches([df], min_docs=2) if c.token == "δραχμαι"]
    # The unit precedes the numeral in Greek accounts, so it is a left neighbour.
    assert candidate.n_left == 3
    assert candidate.n_right == 0
    assert candidate.right_ratio == 0.0
