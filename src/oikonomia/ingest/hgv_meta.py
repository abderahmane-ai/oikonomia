"""Assemble :class:`HgvMetadata` from an HGV EpiDoc metadata file."""

from __future__ import annotations

from lxml import etree

from oikonomia.ingest.hgv_dates import parse_dates
from oikonomia.ingest.hgv_genre import map_terms, parse_terms
from oikonomia.ingest.hgv_places import parse_origplace_text, parse_places
from oikonomia.ingest.xml_parser import parse_xml
from oikonomia.schemas.metadata import HgvMetadata

TEI_NS = "http://www.tei-c.org/ns/1.0"


def _tm_id(tree: etree._ElementTree, fallback: int) -> int:
    for idno in tree.findall(f".//{{{TEI_NS}}}idno"):
        if idno.get("type") == "TM":
            val = (idno.text or "").strip()
            if val.isdigit():
                return int(val)
    return fallback


def _title(tree: etree._ElementTree) -> str | None:
    el = tree.find(f".//{{{TEI_NS}}}titleStmt/{{{TEI_NS}}}title")
    if el is None:
        el = tree.find(f".//{{{TEI_NS}}}title")
    return (el.text or "").strip() if el is not None and el.text else None


def parse_hgv(
    xml_bytes: bytes, stem_numeric: int, genre_map: dict[str, dict[str, str]]
) -> HgvMetadata:
    """Parse one HGV metadata file into :class:`HgvMetadata`.

    ``stem_numeric`` is the numeric TM id from the filename, used as a fallback
    when the XML lacks an explicit ``<idno type="TM">``.
    """
    tree = parse_xml(xml_bytes)

    dates = parse_dates(tree)
    places = parse_places(tree)
    terms = parse_terms(tree)
    canonical = map_terms(terms, genre_map)

    flags: list[str] = []
    if not any(d.lo is not None or d.hi is not None for d in dates):
        flags.append("no_machine_date")
    if not any(p.trismegistos_geo_id or p.pleiades_id for p in places):
        flags.append("no_place_ref")
    if not canonical:
        flags.append("no_canonical_genre")

    return HgvMetadata(
        tm_id=_tm_id(tree, stem_numeric),
        dates=dates,
        places=places,
        hgv_terms=terms,
        canonical_genres=canonical,
        title=_title(tree),
        orig_place_text=parse_origplace_text(tree),
        parse_flags=flags,
    )
