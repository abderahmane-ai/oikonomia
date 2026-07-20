"""Tests for the corpus-attestation check.

This is the standing guard on the project's lexicon rule — forms are measured,
never recalled. The check is only worth having if it *fails* on an invented
form, so that is the first thing asserted.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from oikonomia.labeling.evaluate import verify_lexicon
from oikonomia.labeling.lexicon import Lexicon, LexiconEntry


def _corpus(*texts: str) -> list[pd.DataFrame]:
    docs = [json.dumps({"edited_text": t}) for t in texts]
    return [pd.DataFrame({"document_json": docs})]


def _lex(**entries: list[str]) -> Lexicon:
    return Lexicon(
        entries=[
            LexiconEntry(id=eid, category="UNIT", forms=forms)
            for eid, forms in entries.items()
        ]
    )


def test_invented_form_is_reported() -> None:
    """The case the check exists for: a form nothing in the corpus attests."""
    lexicon = _lex(artaba=["αρταβασ", "ουδεποτεγεγραμμενον"])
    report = verify_lexicon(_corpus("πυροῦ ἀρτάβας μ"), lexicon)

    assert not report.ok
    assert report.n_unattested == 1
    assert [a.form for a in report.unattested] == ["ουδεποτεγεγραμμενον"]


def test_all_attested_passes() -> None:
    lexicon = _lex(artaba=["αρταβασ"], wheat=["πυρου"])
    report = verify_lexicon(_corpus("πυροῦ ἀρτάβας μ"), lexicon)

    assert report.ok
    assert report.n_unattested == 0
    assert report.n_forms == report.n_attested == 2


def test_attestation_matches_folded_not_raw() -> None:
    """Accented corpus text must attest the folded lexicon form."""
    report = verify_lexicon(_corpus("ἀρτάβας"), _lex(artaba=["αρταβασ"]))
    assert report.ok


def test_counts_documents_not_occurrences() -> None:
    """A word repeated in one document counts once."""
    report = verify_lexicon(
        _corpus("ἀρτάβας ἀρτάβας ἀρτάβας", "ἀρτάβας"), _lex(artaba=["αρταβασ"])
    )
    assert [a.n_docs for a in report.rarest_attested] == [2]


def test_whitespace_only_documents_are_skipped() -> None:
    """The 6,731 whitespace-only docs must not count as attestation."""
    report = verify_lexicon(_corpus("   \n  ", "ἀρτάβας"), _lex(artaba=["αρταβασ"]))
    assert report.rarest_attested[0].n_docs == 1


def test_rarest_attested_is_sorted_ascending() -> None:
    lexicon = _lex(artaba=["αρταβασ"], wheat=["πυρου"])
    report = verify_lexicon(_corpus("πυροῦ ἀρτάβας", "ἀρτάβας"), lexicon)
    counts = [a.n_docs for a in report.rarest_attested]
    assert counts == sorted(counts)
    assert counts == [1, 2]


@pytest.mark.corpus
def test_shipped_lexicon_is_fully_attested() -> None:
    """Guard for the real files — skipped unless the built corpus is present."""
    from pathlib import Path

    from oikonomia.corpus.io import iter_batches
    from oikonomia.labeling.evaluate import VERIFY_COLUMNS
    from oikonomia.labeling.lexicon import load_lexicon

    root = Path(__file__).resolve().parents[1]
    corpus = root / "data" / "processed" / "corpus.parquet"
    if not corpus.is_file():
        pytest.skip("built corpus not present")

    report = verify_lexicon(
        iter_batches(corpus, VERIFY_COLUMNS), load_lexicon(root / "resources")
    )
    assert report.ok, [a.form for a in report.unattested]
