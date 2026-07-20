"""Shared test fixtures and invariant helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from oikonomia.config import IngestConfig
from oikonomia.schemas.document import Document

FIXTURES = Path(__file__).parent / "fixtures"

# A hand-crafted EpiDoc edition with a known, hand-computed rendering. Kept tiny
# and deterministic so the expected edited/diplomatic strings and every span can
# be asserted exactly (see test_epidoc_text.py for the full derivation).
#
#   line 1:  α <expan><abbr>β</abbr><ex>γ</ex></expan> δ
#   line 2:  <choice><reg>ε</reg><orig>ζ</orig></choice> <supplied>η</supplied> θ
#
#   edited      = "αβγδ\nεηθ"
#   diplomatic  = "αβδ\nζθ"
CRAFTED_EDITION = (
    '<TEI xmlns="http://www.tei-c.org/ns/1.0">'
    "<text><body>"
    '<div type="edition" xml:lang="grc"><ab>'
    '<lb n="1"/>α<expan><abbr>β</abbr><ex>γ</ex></expan>δ'
    '<lb n="2"/><choice><reg>ε</reg><orig>ζ</orig></choice>'
    '<supplied reason="lost">η</supplied>θ'
    "</ab></div>"
    "</body></text></TEI>"
).encode()


@pytest.fixture
def ingest_cfg() -> IngestConfig:
    return IngestConfig(idp_git_rev="testrev", gap_placeholder="·")


def assert_document_invariants(doc: Document) -> None:
    """Assert the structural invariants every parsed document must satisfy."""
    ed, dp = doc.edited_text, doc.diplomatic_text

    # 1. Every markup span lies within its view and, where both views are
    #    present, the aligned offset map maps edited→diplomatic consistently.
    for m in doc.markup:
        if m.edited is not None:
            assert 0 <= m.edited.start <= m.edited.end <= len(ed)
        if m.diplomatic is not None:
            assert 0 <= m.diplomatic.start <= m.diplomatic.end <= len(dp)

    # 2. Each numeral's recorded text equals the slice it points at.
    for num in doc.numerals:
        if num.edited is not None:
            assert num.text == ed[num.edited.start : num.edited.end]

    # 3. THE core correctness property: every aligned segment slices to identical
    #    text in both views. If the offset map is wrong, this fails.
    for seg in doc.offset_map.segments:
        assert ed[seg.e0 : seg.e1] == dp[seg.d0 : seg.d1]

    # 4. Aligned segments are ordered and non-overlapping in both views.
    prev_e = prev_d = -1
    for seg in doc.offset_map.segments:
        assert seg.e0 >= prev_e
        assert seg.d0 >= prev_d
        prev_e, prev_d = seg.e1, seg.d1

    # 5. Line spans lie within bounds.
    for ln in doc.lines:
        if ln.edited is not None:
            assert 0 <= ln.edited.start <= ln.edited.end <= len(ed)
        if ln.diplomatic is not None:
            assert 0 <= ln.diplomatic.start <= ln.diplomatic.end <= len(dp)
