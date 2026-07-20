"""Tests for lexicon coverage measurement.

Coverage numbers steer curation decisions, so the accounting has to be exactly
right: every numeral must land in exactly one of attached / dated / unexplained.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from oikonomia.labeling.evaluate import evaluate_coverage
from oikonomia.labeling.lexicon import Lexicon, LexiconEntry
from oikonomia.labeling.matcher import Matcher

LEXICON = Lexicon(
    entries=[
        LexiconEntry(id="drachma", category="CURRENCY", forms=["δραχμαι"]),
        LexiconEntry(id="artaba", category="UNIT", forms=["αρταβαι"]),
        LexiconEntry(id="wheat", category="COMMODITY", forms=["πυρου"]),
        LexiconEntry(id="year", category="DATE_REF", forms=["ετουσ"]),
    ]
)


def _doc(lines: list[str], numerals_on: list[int]) -> str:
    """Build a document whose lines are ``lines``, with a numeral on each of
    ``numerals_on`` (line indices). Offsets are computed, not hand-written."""
    text = ""
    line_spans = []
    for line in lines:
        start = len(text)
        text += line + "\n"
        line_spans.append({"start": start, "end": start + len(line)})

    numerals = []
    for i in numerals_on:
        # Point at the last character of the line — enough to locate the line.
        pos = line_spans[i]["end"] - 1
        numerals.append({"edited": {"start": pos, "end": pos + 1}, "text": "x"})

    return json.dumps(
        {
            "edited_text": text,
            "diplomatic_text": text,
            "lines": [{"n": str(i), "edited": s, "diplomatic": s} for i, s in enumerate(line_spans)],
            "numerals": numerals,
        }
    )


def _frame(docs: list[str], genres: str = '["receipt"]') -> pd.DataFrame:
    return pd.DataFrame({"document_json": docs, "canonical_genres": [genres] * len(docs)})


@pytest.fixture
def matcher() -> Matcher:
    return Matcher(LEXICON)


def test_numeral_with_currency_on_its_line_is_attached(matcher: Matcher) -> None:
    doc = _doc(["ἀργυρίου δραχμαὶ μ"], numerals_on=[0])
    report = evaluate_coverage([_frame([doc])], matcher)
    assert report.n_numerals == 1
    assert report.n_numerals_attached == 1
    assert report.attachment_rate == 1.0


def test_numeral_with_only_a_date_term_counts_as_dated_not_attached(matcher: Matcher) -> None:
    doc = _doc(["ἔτους μϛ"], numerals_on=[0])
    report = evaluate_coverage([_frame([doc])], matcher)
    assert report.n_numerals_attached == 0
    assert report.n_numerals_dated == 1
    assert report.unexplained_rate == 0.0


def test_numeral_with_neither_is_unexplained(matcher: Matcher) -> None:
    doc = _doc(["καὶ ὁμοίως β"], numerals_on=[0])
    report = evaluate_coverage([_frame([doc])], matcher)
    assert report.n_numerals_attached == 0
    assert report.n_numerals_dated == 0
    assert report.unexplained_rate == 1.0


def test_commodity_alone_does_not_count_as_attachment(matcher: Matcher) -> None:
    """A commodity says what is paid for, not what unit it is counted in."""
    doc = _doc(["πυροῦ γ"], numerals_on=[0])
    report = evaluate_coverage([_frame([doc])], matcher)
    assert report.n_numerals_attached == 0
    assert report.matches_by_category["COMMODITY"] == 1


def test_the_three_buckets_partition_every_numeral(matcher: Matcher) -> None:
    """attached + dated + unexplained must account for exactly 100%."""
    doc = _doc(
        ["ἀργυρίου δραχμαὶ μ", "ἔτους μϛ", "καὶ ὁμοίως β", "πυροῦ ἀρτάβαι ιβ"],
        numerals_on=[0, 1, 2, 3],
    )
    report = evaluate_coverage([_frame([doc])], matcher)
    assert report.n_numerals == 4
    assert report.n_numerals_attached == 2
    assert report.n_numerals_dated == 1
    total = report.attachment_rate + report.dated_rate + report.unexplained_rate
    assert total == pytest.approx(1.0, abs=1e-6)


def test_line_scoping_a_unit_on_another_line_does_not_attach(matcher: Matcher) -> None:
    """Accounts list one transaction per line; attachment must not leak across."""
    doc = _doc(["δραχμαὶ μ", "ὁμοίως β"], numerals_on=[1])
    report = evaluate_coverage([_frame([doc])], matcher)
    assert report.n_numerals == 1
    assert report.n_numerals_attached == 0


def test_gap_list_excludes_matched_tokens(matcher: Matcher) -> None:
    doc = _doc(["πυροῦ ὁμοίως β"], numerals_on=[0])
    report = evaluate_coverage([_frame([doc])], matcher)
    gaps = dict(report.top_unmatched_neighbours)
    assert "πυρου" not in gaps  # it matched, so it is not a gap
    assert "ομοιωσ" in gaps


def test_per_genre_breakdown(matcher: Matcher) -> None:
    attached = _doc(["δραχμαὶ μ"], numerals_on=[0])
    unattached = _doc(["ὁμοίως β"], numerals_on=[0])
    report = evaluate_coverage([_frame([attached, unattached])], matcher)
    (genre,) = report.by_genre
    assert genre.genre == "receipt"
    assert genre.n_numerals == 2
    assert genre.n_attached == 1
    assert genre.attachment_rate == 0.5


def test_batching_does_not_change_results(matcher: Matcher) -> None:
    docs = [_doc(["δραχμαὶ μ"], [0]), _doc(["ἔτους μϛ"], [0]), _doc(["ὁμοίως β"], [0])]
    whole = evaluate_coverage([_frame(docs)], matcher)
    split = evaluate_coverage([_frame(docs[:1]), _frame(docs[1:])], matcher)
    assert whole.model_dump() == split.model_dump()


def test_empty_document_is_counted_but_contributes_no_numerals(matcher: Matcher) -> None:
    empty = json.dumps(
        {"edited_text": "", "diplomatic_text": "", "lines": [], "numerals": []}
    )
    report = evaluate_coverage([_frame([empty])], matcher)
    assert report.n_docs == 1
    assert report.n_numerals == 0
    assert report.attachment_rate == 0.0
