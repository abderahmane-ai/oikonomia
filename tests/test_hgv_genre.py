"""Tests for HGV genre term parsing and canonical mapping."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from oikonomia.ingest.hgv_genre import load_genre_map, map_terms, parse_terms

TEI = "http://www.tei-c.org/ns/1.0"
GENRE_MAP = Path(__file__).parents[1] / "resources" / "genre_map.yaml"


def _tree(terms: list[str]) -> etree._ElementTree:
    inner = "".join(f'<term n="{i+1}">{t}</term>' for i, t in enumerate(terms))
    xml = f'<TEI xmlns="{TEI}"><teiHeader><profileDesc><textClass><keywords scheme="hgv">{inner}</keywords></textClass></profileDesc></teiHeader></TEI>'
    return etree.ElementTree(etree.fromstring(xml.encode("utf-8")))


def test_parse_terms_in_order() -> None:
    assert parse_terms(_tree(["Vertrag", "Kauf", "Haus"])) == ["Vertrag", "Kauf", "Haus"]


def test_genre_map_loads_and_maps_only_genre_facet() -> None:
    gm = load_genre_map(GENRE_MAP)
    # Real 100042 terms: two are genre, others are commodity/meta.
    canonical = map_terms(["Vertrag", "Kauf", "Haus", "Grundstück", "Übersetzung"], gm)
    assert canonical == ["contract", "sale"]  # Haus/Grundstück=commodity, Übersetzung=meta


def test_map_terms_deduplicates() -> None:
    gm = load_genre_map(GENRE_MAP)
    # Rechnung and Abrechnung both canonicalise to "account".
    assert map_terms(["Abrechnung", "Rechnung"], gm) == ["account"]


def test_shipped_genre_map_is_well_formed() -> None:
    gm = load_genre_map(GENRE_MAP)
    assert gm, "genre map should not be empty"
    valid_facets = {"genre", "commodity", "topic", "meta"}
    for term, spec in gm.items():
        assert spec["canonical"], f"{term} has empty canonical"
        assert spec["facet"] in valid_facets, f"{term} has unknown facet {spec['facet']!r}"
