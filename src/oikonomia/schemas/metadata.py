"""HGV metadata contracts: dates, places, genre.

The HGV (Heidelberger Gesamtverzeichnis) metadata files supply the *when*,
*where*, and *what kind* for each papyrus. These are the axes the historical
analysis ultimately pivots on, so their uncertainty is modelled explicitly
rather than flattened:

* dates are **intervals**, and genuinely competing datings are kept as a list
  and never merged;
* places carry the machine-linkable Trismegistos / Pleiades identifiers found in
  ``<provenance>`` — the free-text ``<origPlace>`` is deliberately *not* used
  for joins;
* genre terms are the raw German folksonomy, mapped separately to a canonical
  taxonomy.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DatePrecision(StrEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    RANGE = "range"
    UNKNOWN = "unknown"


class DateInterval(BaseModel):
    """A dating expressed as a closed year interval ``[lo, hi]``.

    Years are signed astronomical-style integers: 50 CE is ``50``, 44 BCE is
    ``-44``. ``lo``/``hi`` may be ``None`` when only one bound is known. For an
    exact ``when=`` date, ``lo == hi``.

    Alternative datings (EpiDoc ``xml:id="dateAlternativeN"`` siblings) are
    represented as separate ``DateInterval`` instances with ``is_alternative``
    set; the first, primary dating has ``is_alternative=False``.
    """

    lo: int | None = None
    hi: int | None = None
    precision: DatePrecision = DatePrecision.UNKNOWN
    is_alternative: bool = False
    xml_id: str | None = None
    raw: str | None = None  # human-readable label, e.g. "17. März 50"

    @property
    def span_years(self) -> int | None:
        if self.lo is None or self.hi is None:
            return None
        return self.hi - self.lo


class PlaceRef(BaseModel):
    """A place reference carrying gazetteer identifiers.

    Parsed from ``<provenance type="located">//placeName/@ref``, whose value is
    a space-separated list of URIs mixing Trismegistos and Pleiades. ``level``
    reflects the ``@subtype`` (site / nome / region) so the most specific place
    can be selected for mapping.
    """

    trismegistos_geo_id: int | None = None
    pleiades_id: int | None = None
    name: str | None = None
    level: str | None = None  # "site" | "nome" | "region" | raw subtype
    raw_ref: str | None = None


class HgvMetadata(BaseModel):
    """Assembled, machine-usable metadata for one document."""

    tm_id: int
    dates: list[DateInterval] = Field(default_factory=list)
    places: list[PlaceRef] = Field(default_factory=list)
    hgv_terms: list[str] = Field(default_factory=list)  # raw German folksonomy
    canonical_genres: list[str] = Field(default_factory=list)  # mapped taxonomy
    title: str | None = None  # free-text German title
    orig_place_text: str | None = None  # <origPlace> free text — NOTES ONLY, never a join key
    parse_flags: list[str] = Field(default_factory=list)

    @property
    def primary_date(self) -> DateInterval | None:
        for d in self.dates:
            if not d.is_alternative:
                return d
        return self.dates[0] if self.dates else None

    @property
    def primary_place(self) -> PlaceRef | None:
        """Most specific linked place (prefer site > nome > region)."""
        order = {"site": 0, "nome": 1, "region": 2}
        linked = [p for p in self.places if p.trismegistos_geo_id or p.pleiades_id]
        if not linked:
            return None
        return sorted(linked, key=lambda p: order.get(p.level or "", 9))[0]
