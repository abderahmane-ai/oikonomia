"""Tests for corpus characterization.

Every expected value here is hand-computed from the three-document frame below,
so a wrong denominator fails rather than merely shifting a number.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from oikonomia.corpus.stats import MARKUP_KINDS, compute_stats
from oikonomia.schemas.document import MarkupKind


def _doc(*, markup: list[str], n_lines: int) -> str:
    return json.dumps(
        {
            "markup": [{"kind": k} for k in markup],
            "lines": [{"n": str(i)} for i in range(n_lines)],
        }
    )


# Three documents, chosen so every rate has a different numerator/denominator:
#   A: HGV, English translation, exact-day date, place, 4 numerals, 10 lines
#   B: HGV, no translation, wide range (-300..100 = 400y), no place, 6 numerals
#   C: no HGV at all — must be excluded from every date/place denominator
FRAME = pd.DataFrame(
    {
        "has_hgv": [True, True, False],
        "has_translation": [True, False, False],
        "date_lo": [50.0, -300.0, None],
        "date_hi": [50.0, 100.0, None],
        "date_precision": ["day", "range", "unknown"],
        "n_alt_dates": [0, 2, 0],
        "place_tm": [1.0, None, None],
        "place_pleiades": [1.0, None, None],
        "canonical_genres": ['["receipt"]', '["account","receipt"]', "[]"],
        "n_numerals": [4, 6, 0],
        "n_chars_edited": [100, 300, 0],
        "parse_flags": ["[]", "[]", '["empty_edited_text"]'],
        "document_json": [
            _doc(markup=["gap", "gap", "unclear"], n_lines=10),
            _doc(markup=["expansion"], n_lines=20),
            _doc(markup=[], n_lines=0),
        ],
    }
)


@pytest.fixture
def stats():
    return compute_stats([FRAME])


def test_markup_kinds_track_the_enum() -> None:
    """The regression that made num/expan/choice silently read 0.0."""
    assert set(MARKUP_KINDS) == {k.value for k in MarkupKind}


def test_coverage_rates(stats) -> None:
    assert stats.n_docs == 3
    assert stats.hgv_join_rate == pytest.approx(2 / 3, abs=1e-4)
    assert stats.translation_rate == pytest.approx(1 / 3, abs=1e-4)
    assert stats.empty_edited_text_rate == pytest.approx(1 / 3, abs=1e-4)


def test_date_rates_are_conditioned_on_hgv(stats) -> None:
    """Doc C has no HGV record, so it must not dilute the dating rates."""
    assert stats.date_machine_readable_rate == 1.0  # 2 dated / 2 with HGV
    assert stats.date_exact_day_rate == 0.5  # A only, of 2 dated
    assert stats.date_wide_span_rate == 0.5  # B's 400y span, of 2 dated
    assert stats.date_alternative_rate == 0.5  # B only, of 2 with HGV


def test_place_rates(stats) -> None:
    assert stats.place_linkable_rate == 0.5
    assert stats.place_pleiades_rate == 0.5


def test_markup_presence_is_per_document_not_per_span(stats) -> None:
    """Doc A has two <gap> spans; presence counts the document once."""
    assert stats.markup_presence["gap"] == pytest.approx(1 / 3, abs=1e-4)
    assert stats.markup_presence["unclear"] == pytest.approx(1 / 3, abs=1e-4)
    assert stats.markup_presence["expansion"] == pytest.approx(1 / 3, abs=1e-4)
    assert stats.markup_presence["surplus"] == 0.0


def test_numeral_presence_is_separate_from_markup(stats) -> None:
    assert "num" not in stats.markup_presence
    assert stats.numeral_presence_rate == pytest.approx(2 / 3, abs=1e-4)


def test_text_mass(stats) -> None:
    assert stats.n_chars_edited == 400
    assert stats.n_numerals == 10
    assert stats.n_lines == 30
    assert stats.median_chars_edited == 100.0


def test_genre_stats_count_multi_genre_docs_under_each(stats) -> None:
    by_genre = {g.genre: g for g in stats.genres}
    # receipt: A (10 lines, 4 num) + B (20 lines, 6 num)
    assert by_genre["receipt"].n_docs == 2
    assert by_genre["receipt"].n_lines == 30
    assert by_genre["receipt"].numerals_per_line == pytest.approx(10 / 30, abs=1e-4)
    # account: B only
    assert by_genre["account"].n_docs == 1
    assert by_genre["account"].numerals_per_line == pytest.approx(6 / 20, abs=1e-4)


def test_batching_does_not_change_results() -> None:
    """Streaming is an optimisation; it must not alter any statistic."""
    whole = compute_stats([FRAME])
    split = compute_stats([FRAME.iloc[:1], FRAME.iloc[1:]])
    assert whole.model_dump() == split.model_dump()


def test_empty_corpus_is_an_error() -> None:
    with pytest.raises(ValueError, match="no documents"):
        compute_stats([])
