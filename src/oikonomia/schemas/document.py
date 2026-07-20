"""Document-level contracts: parsed text views, markup spans, numerals, lines.

A :class:`Document` is the fully-parsed representation of one DDbDP papyrus:
both text views, the offset map between them, the editorial markup located as
spans, the tagged numerals, and the line structure. It is deliberately
*self-describing* — every span carries the view it indexes and (for spans) the
originating EpiDoc element kind — so that downstream stages never need to
re-open the XML.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from oikonomia.schemas.spans import CharSpan, OffsetMap


class MarkupKind(StrEnum):
    """EpiDoc editorial phenomena we locate as spans.

    These correspond to the Leiden conventions that carry information for the
    extraction task: how damaged a passage is, what the editor supplied, where
    abbreviations were expanded, and where the scribe's spelling was regularised.
    """

    GAP = "gap"  # lost or illegible text (<gap>)
    UNCLEAR = "unclear"  # visible but uncertain characters (<unclear>)
    SUPPLIED = "supplied"  # editorial restoration of lost/omitted text (<supplied>)
    SURPLUS = "surplus"  # text the editor marks as superfluous (<surplus>)
    EXPANSION = "expansion"  # an expanded abbreviation (<expan>)
    ABBREV = "abbrev"  # a standalone abbreviation (<abbr>)
    REGULARIZED = "regularized"  # normalised spelling chosen (<choice><reg>)
    CORRECTED = "corrected"  # scribal error corrected (<choice><corr>)


class MarkupSpan(BaseModel):
    """One editorial phenomenon, located in whichever view(s) it appears.

    A ``SUPPLIED`` span, for instance, has an ``edited`` range (the restored
    text is present in the scholarly reading) but no ``diplomatic`` range (it is
    not physically on the papyrus). A ``SURPLUS`` span is the reverse. Shared
    phenomena such as ``UNCLEAR`` are present in both.
    """

    kind: MarkupKind
    edited: CharSpan | None = None
    diplomatic: CharSpan | None = None
    # Raw EpiDoc attributes (e.g. gap reason/quantity/unit) kept for later use
    # without re-parsing the XML.
    attrs: dict[str, str] = Field(default_factory=dict)


class Numeral(BaseModel):
    """A ``<num>`` element: a written number with its editorial value.

    ``value`` is the numeric value from the ``@value`` attribute where it parses
    cleanly to a float (including simple fractions like ``1/2``); ``raw_value``
    always preserves the original attribute string, and ``value`` is ``None``
    when it cannot be interpreted (e.g. ranges, non-numeric markers). ``text``
    is the surface Greek as it appears in the *edited* view.
    """

    value: float | None = None
    raw_value: str | None = None
    text: str = ""
    edited: CharSpan | None = None
    diplomatic: CharSpan | None = None


class LineRef(BaseModel):
    """One inscription/papyrus line, delimited by ``<lb>`` boundaries.

    ``n`` is the editorial line label (usually an integer string, occasionally
    with letters). Ranges are given per view because a line's character extent
    differs between edited and diplomatic text.
    """

    n: str
    edited: CharSpan | None = None
    diplomatic: CharSpan | None = None


class Document(BaseModel):
    """The complete parsed representation of a single DDbDP papyrus."""

    tm_id: int
    stem: str  # filename stem, e.g. "100042" or "13a"
    ddb_hybrid: str | None = None  # e.g. "sb;30;17708"
    edited_text: str
    diplomatic_text: str
    offset_map: OffsetMap
    markup: list[MarkupSpan] = Field(default_factory=list)
    numerals: list[Numeral] = Field(default_factory=list)
    lines: list[LineRef] = Field(default_factory=list)
    # Non-fatal issues encountered while parsing (unknown elements, empty edition…).
    parse_flags: list[str] = Field(default_factory=list)

    @property
    def n_numerals(self) -> int:
        return len(self.numerals)

    def damage_ratio(self) -> float:
        """Fraction of edited-view characters that fall inside gap/supplied spans.

        A cheap, view-consistent proxy for how reconstructed a document is, used
        later for stratification and slice-wise evaluation. Returns 0.0 for an
        empty document.
        """
        if not self.edited_text:
            return 0.0
        covered = 0
        for m in self.markup:
            if m.kind in (MarkupKind.GAP, MarkupKind.SUPPLIED) and m.edited is not None:
                covered += len(m.edited)
        return min(covered / len(self.edited_text), 1.0)
