"""Tests for gold-annotation sampling.

The properties here are about *budget* and *contamination*: a bad sample wastes
the scarcest resource in the project and can silently poison the evaluation.
"""

from __future__ import annotations

from typing import Any

import pytest

from oikonomia.gold.sample import (
    MAX_CHARS,
    MIN_CHARS,
    gap_ratio,
    greek_ratio,
    is_annotatable,
    select,
)


def _row(doc_id: str, genre: str, bucket: str, n_numerals: int = 5) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "text": "α" * 300,
        "n_numerals": n_numerals,
        "genre": genre,
        "date_bucket": bucket,
    }


def _pool() -> list[dict[str, Any]]:
    rows = []
    for genre in ("receipt", "lease", "letter_private"):
        for bucket in ("ptolemaic", "high_roman", "byzantine"):
            for i in range(40):
                dense = _row(f"{genre}-{bucket}-{i}", genre, bucket, n_numerals=9)
                prose = _row(f"{genre}-{bucket}-p{i}", genre, bucket, n_numerals=0)
                rows += [dense, prose]
    return rows


def test_no_genre_dominates_the_budget() -> None:
    """The corpus is 25% receipts; a proportional sample wastes the budget."""
    chosen = select(_pool(), n=60, seed=1)
    counts: dict[str, int] = {}
    for r in chosen:
        counts[r["genre"]] = counts.get(r["genre"], 0) + 1
    assert max(counts.values()) - min(counts.values()) <= 2


def test_sample_spreads_across_date_buckets() -> None:
    """Not all picks may land in the century where the corpus mass is."""
    chosen = select(_pool(), n=60, seed=1)
    assert len({r["date_bucket"] for r in chosen}) == 3


def test_prose_documents_are_deliberately_included() -> None:
    """PERSON/PLACE must be seen outside accounting lines too."""
    chosen = select(_pool(), n=60, seed=1, prose_share=0.2)
    prose = [r for r in chosen if r["n_numerals"] <= 2]
    assert 6 <= len(prose) <= 18  # ~20% of 60, with rounding slack


def test_selection_is_deterministic_for_a_seed() -> None:
    ids = lambda s: [r["doc_id"] for r in select(_pool(), n=40, seed=s)]  # noqa: E731
    assert ids(3) == ids(3)
    assert ids(3) != ids(4)


def test_selection_ignores_input_order() -> None:
    """Reordering the corpus scan must not change the sample."""
    pool = _pool()
    a = [r["doc_id"] for r in select(pool, n=40, seed=2)]
    b = [r["doc_id"] for r in select(list(reversed(pool)), n=40, seed=2)]
    assert a == b


def test_no_document_is_selected_twice() -> None:
    chosen = select(_pool(), n=100, seed=1)
    assert len({r["doc_id"] for r in chosen}) == len(chosen)


# --------------------------------------------------------------------------
# Annotatability filters
# --------------------------------------------------------------------------


def test_latin_documents_are_rejected() -> None:
    """idp.data carries Latin texts; they are useless to a Greek model and
    would burn annotator time being skipped."""
    latin = "per modios xxx decembres per gracilem pondo centum " * 4
    assert greek_ratio(latin) == 0.0
    assert not is_annotatable(latin)


def test_greek_documents_are_accepted() -> None:
    greek = "πυροῦ ἀρτάβας τεσσαράκοντα ἐν τῷ ἔτει διὰ Ἡλιοδώρου ἀγορανόμου " * 3
    assert greek_ratio(greek) > 0.99
    assert is_annotatable(greek)


def test_heavily_damaged_documents_are_rejected() -> None:
    """Past ~10% lacunae a document is more gap than text."""
    damaged = "… … … … … … … … …" + "α" * 60
    assert gap_ratio(damaged) > 0.10
    assert not is_annotatable(damaged)


@pytest.mark.parametrize("n", [MIN_CHARS - 1, MAX_CHARS + 1])
def test_length_bounds_are_enforced(n: int) -> None:
    assert not is_annotatable("α" * n)


def test_greek_ratio_handles_empty_and_digits() -> None:
    assert greek_ratio("") == 0.0
    assert greek_ratio("123 456") == 0.0
    assert gap_ratio("") == 0.0
