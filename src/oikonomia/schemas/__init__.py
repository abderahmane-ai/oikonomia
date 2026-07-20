"""Typed contracts shared across every pipeline stage — the spine of the repo."""

from oikonomia.schemas.document import (
    Document,
    LineRef,
    MarkupKind,
    MarkupSpan,
    Numeral,
)
from oikonomia.schemas.manifest import ArtifactFingerprint, StageManifest
from oikonomia.schemas.metadata import (
    DateInterval,
    DatePrecision,
    HgvMetadata,
    PlaceRef,
)
from oikonomia.schemas.spans import AlignedSegment, CharSpan, OffsetMap

__all__ = [
    "AlignedSegment",
    "ArtifactFingerprint",
    "CharSpan",
    "DateInterval",
    "DatePrecision",
    "Document",
    "HgvMetadata",
    "LineRef",
    "MarkupKind",
    "MarkupSpan",
    "Numeral",
    "OffsetMap",
    "PlaceRef",
    "StageManifest",
]
