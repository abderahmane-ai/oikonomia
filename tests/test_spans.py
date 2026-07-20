"""Unit tests for CharSpan and the OffsetMap primitive."""

from __future__ import annotations

import pytest

from oikonomia.schemas.spans import AlignedSegment, CharSpan, OffsetMap


def test_charspan_slice_and_len() -> None:
    span = CharSpan(start=2, end=5)
    assert len(span) == 3
    assert span.slice("αβγδεζ") == "γδε"
    assert not span.is_empty


def test_charspan_rejects_reversed() -> None:
    with pytest.raises(ValueError, match="precedes start"):
        CharSpan(start=5, end=2)


def test_charspan_overlaps() -> None:
    assert CharSpan(start=0, end=3).overlaps(CharSpan(start=2, end=4))
    assert not CharSpan(start=0, end=2).overlaps(CharSpan(start=2, end=4))


def test_aligned_segment_length_must_match() -> None:
    with pytest.raises(ValueError, match="lengths differ"):
        AlignedSegment(e0=0, e1=3, d0=0, d1=2)


def _sample_map() -> OffsetMap:
    # edited "αβXδ" vs diplomatic "αβδ": X (index 2) is edited-only.
    return OffsetMap(
        segments=[
            AlignedSegment(e0=0, e1=2, d0=0, d1=2),  # αβ
            AlignedSegment(e0=3, e1=4, d0=2, d1=3),  # δ
        ]
    )


def test_offset_map_forward_and_gap() -> None:
    om = _sample_map()
    assert om.edited_to_diplomatic(0) == 0
    assert om.edited_to_diplomatic(1) == 1
    assert om.edited_to_diplomatic(2) is None  # edited-only
    assert om.edited_to_diplomatic(3) == 2


def test_offset_map_reverse() -> None:
    om = _sample_map()
    assert om.diplomatic_to_edited(0) == 0
    assert om.diplomatic_to_edited(2) == 3
    assert om.diplomatic_to_edited(99) is None  # out of range


def test_offset_map_span_translation() -> None:
    om = _sample_map()
    # Edited [0,2) "αβ" maps cleanly to diplomatic [0,2).
    mapped = om.span_edited_to_diplomatic(CharSpan(start=0, end=2))
    assert mapped == CharSpan(start=0, end=2)
    # A span straddling the edited-only X cannot map end-1 at index 2 → None.
    assert om.span_edited_to_diplomatic(CharSpan(start=1, end=3)) is None
