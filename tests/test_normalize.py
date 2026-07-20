"""Tests for Greek folding and the folded→original position map.

The load-bearing property is not the folded string but the round trip: a span
found in folded space must slice the *right* substring of the original.
"""

from __future__ import annotations

import pytest

from oikonomia.labeling.normalize import fold_char, normalize
from oikonomia.schemas.spans import CharSpan


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ἀρτάβας", "αρταβασ"),  # breathing + acute dropped, final sigma folded
        ("Ἡλιοδώρου", "ηλιοδωρου"),  # capital + rough breathing
        ("ᾳ", "α"),  # iota subscript
        ("ᾧ", "ω"),  # breathing + circumflex + subscript
        ("ϊ", "ι"),  # diaeresis
        ("ΟΔΟΣ", "οδοσ"),  # capitals, sigma folded
        ("λόγος", "λογοσ"),  # final sigma folded to medial
        ("δραχμ", "δραχμ"),  # already folded — unchanged
    ],
)
def test_folding(raw: str, expected: str) -> None:
    assert normalize(raw).text == expected


def test_final_and_medial_sigma_collapse() -> None:
    """The fold Python's lower() does not do: ς and σ must become one form."""
    assert normalize("λόγος").text == normalize("λογοσ").text


def test_origin_map_round_trips_every_position() -> None:
    """Each folded character must slice back to a character of the original."""
    raw = "ἔτους μϛ Μεσορὴ δ"
    n = normalize(raw)
    assert len(n.origin) == len(n.text)
    for i in range(len(n.text)):
        span = n.to_original(CharSpan(start=i, end=i + 1))
        assert span is not None
        assert normalize(span.slice(raw)).text == n.text[i]


def test_word_span_maps_back_with_its_accents() -> None:
    """A word located in folded space must recover the accented original."""
    raw = "ἀργυρίου δραχμὰς τεσσαράκοντα"
    n = normalize(raw)
    at = n.text.index("δραχμασ")
    span = n.to_original(CharSpan(start=at, end=at + len("δραχμασ")))
    assert span is not None
    assert span.slice(raw) == "δραχμὰς"


def test_origin_is_non_decreasing() -> None:
    n = normalize("ᾧ ἀρτάβας Ἡλιοδώρου ϊδ")
    assert n.origin == sorted(n.origin)


def test_dropped_marks_do_not_shift_following_text() -> None:
    """Accents shorten the folded string; later origins must still be right."""
    raw = "ἀ β"  # folded "α β": the breathing is dropped
    n = normalize(raw)
    assert n.text == "α β"
    beta = n.to_original(CharSpan(start=2, end=3))
    assert beta is not None
    assert beta.slice(raw) == "β"


def test_combining_mark_folds_to_empty() -> None:
    assert fold_char("́") == ""


def test_empty_and_out_of_range_spans() -> None:
    n = normalize("αβγ")
    empty = n.to_original(CharSpan(start=1, end=1))
    assert empty is not None and empty.is_empty
    assert n.to_original(CharSpan(start=0, end=99)) is None


def test_empty_string() -> None:
    n = normalize("")
    assert n.text == "" and n.origin == [] and n.source_len == 0
