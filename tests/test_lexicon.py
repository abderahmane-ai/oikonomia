"""Tests for lexicon loading and longest-match matching.

The matcher's contract has one property that matters above the rest: spans come
back in **original** offsets, so slicing the caller's own string with them
yields the accented word that matched. Everything else is bookkeeping.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from oikonomia.labeling.lexicon import (
    Lexicon,
    LexiconEntry,
    load_lexicon,
    load_lexicon_file,
)
from oikonomia.labeling.matcher import Matcher

RESOURCES = Path(__file__).resolve().parents[1] / "resources"


def _lex(*entries: LexiconEntry) -> Lexicon:
    return Lexicon(entries=list(entries))


DRACHMA = LexiconEntry(
    id="drachma",
    category="CURRENCY",
    forms=["δραχμασ", "δραχμαι"],
    abbrev_forms=["δραχμ"],
)
ARTABA = LexiconEntry(id="artaba", category="UNIT", forms=["αρταβαι"])


# --- loading ---------------------------------------------------------------


def test_shipped_lexicon_loads_and_has_no_form_collisions() -> None:
    lexicon = load_lexicon(RESOURCES)
    index = lexicon.index()  # raises on a form claimed by two entries
    assert len(lexicon.entries) > 50
    assert {e.category for e in lexicon.entries} >= {
        "CURRENCY",
        "UNIT",
        "COMMODITY",
        "TAX_TERM",
        "DATE_REF",
    }
    assert "δραχμασ" in index
    assert index["δραχμασ"].id == "drachma"


def test_unfolded_form_is_rejected(tmp_path: Path) -> None:
    """An accented entry would never match; that must fail loudly at load."""
    path = tmp_path / "bad.yaml"
    path.write_text(
        "category: CURRENCY\nentries:\n  - id: drachma\n    forms: [δραχμάς]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not folded"):
        load_lexicon_file(path)


def test_entry_without_forms_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("category: UNIT\nentries:\n  - id: empty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no forms"):
        load_lexicon_file(path)


def test_missing_category_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("entries: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="category"):
        load_lexicon_file(path)


def test_form_claimed_by_two_entries_is_an_error() -> None:
    other = LexiconEntry(id="other", category="UNIT", forms=["δραχμασ"])
    with pytest.raises(ValueError, match="claimed by both"):
        _lex(DRACHMA, other).index()


# --- matching --------------------------------------------------------------


def test_match_returns_original_offsets_not_folded_ones() -> None:
    """The core property: spans index the caller's string, accents and all."""
    text = "ἀργυρίου δραχμὰς τεσσαράκοντα"
    matcher = Matcher(_lex(DRACHMA))
    (hit,) = matcher.match(text)
    assert hit.entry_id == "drachma"
    assert text[hit.span.start : hit.span.end] == "δραχμὰς"
    assert hit.text == "δραχμὰς"
    assert hit.folded == "δραχμασ"


def test_abbreviation_does_not_match_inside_a_longer_word() -> None:
    """δραχμ must not fire on the first five letters of δραχμαι."""
    matcher = Matcher(_lex(DRACHMA))
    (hit,) = matcher.match("δραχμαὶ ρ")
    assert hit.folded == "δραχμαι"
    assert hit.is_abbrev is False


def test_standalone_abbreviation_matches_and_is_flagged() -> None:
    matcher = Matcher(_lex(DRACHMA))
    (hit,) = matcher.match("δραχμ η")
    assert hit.folded == "δραχμ"
    assert hit.is_abbrev is True


def test_abbrevs_can_be_excluded() -> None:
    matcher = Matcher(_lex(DRACHMA), include_abbrev=False)
    assert matcher.match("δραχμ η") == []


def test_multiple_categories_in_one_line() -> None:
    matcher = Matcher(_lex(DRACHMA, ARTABA))
    hits = matcher.match("πυροῦ ἀρτάβαι ιβ δραχμαὶ ρ")
    assert [(h.category, h.entry_id) for h in hits] == [
        ("UNIT", "artaba"),
        ("CURRENCY", "drachma"),
    ]


def test_matches_are_non_overlapping_and_ordered() -> None:
    matcher = Matcher(load_lexicon(RESOURCES))
    hits = matcher.match("οἴνου κεράμια δ καὶ ἐλαίου ξέσται β")
    assert [h.span.start for h in hits] == sorted(h.span.start for h in hits)
    for a, b in itertools.pairwise(hits):
        assert a.span.end <= b.span.start


def test_no_match_returns_empty() -> None:
    matcher = Matcher(_lex(DRACHMA))
    assert matcher.match("ἔτους μϛ Μεσορὴ δ") == []
    assert matcher.match("") == []


def test_case_and_accent_variants_all_match_one_entry() -> None:
    """The point of folding: one lexicon form covers the spelling variants."""
    matcher = Matcher(_lex(DRACHMA))
    for variant in ["δραχμὰς", "δραχμάς", "δράχμας", "ΔΡΑΧΜΑΣ"]:
        hits = matcher.match(variant)
        assert len(hits) == 1, variant
        assert hits[0].entry_id == "drachma"
