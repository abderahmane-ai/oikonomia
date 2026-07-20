"""Character-span primitives and the bidirectional edited↔diplomatic offset map.

These are the lowest-level contracts in the project. Everything that locates a
piece of information inside a document — a numeral, a lacuna, an entity
annotation, a released-database evidence pointer — is ultimately a
:class:`CharSpan` into one of a document's two text views.

The two views (see :mod:`oikonomia.ingest.epidoc_text`):

* **edited**   — the scholarly reconstruction (abbreviations expanded, lost text
  restored, dialectal spellings regularised).
* **diplomatic** — what is physically on the papyrus (abbreviations left short,
  restored text omitted, original spellings kept).

Because currency and measure terms are overwhelmingly abbreviated, annotation
offsets made against one view must be mappable onto the other; that is what
:class:`OffsetMap` provides.
"""

from __future__ import annotations

import bisect

from pydantic import BaseModel, Field, model_validator


class CharSpan(BaseModel):
    """A half-open character range ``[start, end)`` into a specific text view.

    ``start`` and ``end`` are Python string indices (code points, not bytes).
    The range is half-open so that ``text[span.start:span.end]`` yields exactly
    the covered substring and adjacent spans share a boundary index.
    """

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> CharSpan:
        if self.end < self.start:
            msg = f"CharSpan end ({self.end}) precedes start ({self.start})"
            raise ValueError(msg)
        return self

    def __len__(self) -> int:
        return self.end - self.start

    @property
    def is_empty(self) -> bool:
        return self.end == self.start

    def slice(self, text: str) -> str:
        """Return the substring of ``text`` covered by this span."""
        return text[self.start : self.end]

    def overlaps(self, other: CharSpan) -> bool:
        """True if the two half-open ranges share at least one position."""
        return self.start < other.end and other.start < self.end


class AlignedSegment(BaseModel):
    """A run of identical text present in both views, at possibly different offsets.

    Produced whenever the EpiDoc walker emits a chunk of text into *both* views
    simultaneously (plain text, ``<unclear>``, ``<num>`` content, etc.). The
    two ranges always have equal length.
    """

    e0: int = Field(ge=0)  # edited-view start
    e1: int = Field(ge=0)  # edited-view end
    d0: int = Field(ge=0)  # diplomatic-view start
    d1: int = Field(ge=0)  # diplomatic-view end

    @model_validator(mode="after")
    def _check_lengths(self) -> AlignedSegment:
        if (self.e1 - self.e0) != (self.d1 - self.d0):
            msg = "AlignedSegment edited and diplomatic lengths differ"
            raise ValueError(msg)
        return self


class OffsetMap(BaseModel):
    """Bidirectional map between edited-view and diplomatic-view offsets.

    The map is defined only on characters that are shared between the two views
    (the aligned segments). A character that exists only in the edited view
    (e.g. an expansion ``<ex>`` or a restoration ``<supplied>``) or only in the
    diplomatic view (e.g. a ``<surplus>``) has no counterpart, and the mapping
    functions return ``None`` for it. Callers must treat ``None`` as "no
    corresponding position", never as ``0``.
    """

    segments: list[AlignedSegment] = Field(default_factory=list)

    # Internal sorted key arrays, lazily built for binary search.
    def _edited_starts(self) -> list[int]:
        return [s.e0 for s in self.segments]

    def _diplo_starts(self) -> list[int]:
        return [s.d0 for s in self.segments]

    def edited_to_diplomatic(self, i: int) -> int | None:
        """Map an edited-view offset to its diplomatic-view offset, or ``None``."""
        starts = self._edited_starts()
        idx = bisect.bisect_right(starts, i) - 1
        if idx < 0:
            return None
        seg = self.segments[idx]
        if seg.e0 <= i < seg.e1:
            return seg.d0 + (i - seg.e0)
        return None

    def diplomatic_to_edited(self, i: int) -> int | None:
        """Map a diplomatic-view offset to its edited-view offset, or ``None``."""
        starts = self._diplo_starts()
        idx = bisect.bisect_right(starts, i) - 1
        if idx < 0:
            return None
        seg = self.segments[idx]
        if seg.d0 <= i < seg.d1:
            return seg.e0 + (i - seg.d0)
        return None

    def span_edited_to_diplomatic(self, span: CharSpan) -> CharSpan | None:
        """Map a whole edited-view span to diplomatic space.

        Returns ``None`` unless both endpoints land inside aligned regions. The
        end index is mapped via ``end - 1`` (last covered character) and then
        re-opened, so a span whose interior is fully aligned maps cleanly even
        when ``end`` sits on a segment boundary.
        """
        if span.is_empty:
            mapped = self.edited_to_diplomatic(span.start)
            return CharSpan(start=mapped, end=mapped) if mapped is not None else None
        lo = self.edited_to_diplomatic(span.start)
        hi = self.edited_to_diplomatic(span.end - 1)
        if lo is None or hi is None:
            return None
        return CharSpan(start=lo, end=hi + 1)
