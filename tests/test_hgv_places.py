"""Tests for HGV place parsing (multi-URI refs; origPlace excluded from joins)."""

from __future__ import annotations

from lxml import etree

from oikonomia.ingest.hgv_places import parse_origplace_text, parse_places

TEI = "http://www.tei-c.org/ns/1.0"


def _tree(body: str) -> etree._ElementTree:
    xml = f'<TEI xmlns="{TEI}"><teiHeader><fileDesc><sourceDesc><msDesc><history>{body}</history></msDesc></sourceDesc></fileDesc></teiHeader></TEI>'
    return etree.ElementTree(etree.fromstring(xml.encode("utf-8")))


def test_space_separated_multi_uri_ref() -> None:
    body = (
        '<provenance type="located"><p>'
        '<placeName n="1" type="ancient" '
        'ref="https://www.trismegistos.org/place/2157 https://pleiades.stoa.org/places/737053">'
        "Soknopaiu Nesos</placeName>"
        '<placeName n="2" type="ancient" subtype="nome" '
        'ref="https://www.trismegistos.org/place/332">Arsinoites</placeName>'
        "</p></provenance>"
    )
    places = parse_places(_tree(body))
    assert len(places) == 2
    assert places[0].trismegistos_geo_id == 2157
    assert places[0].pleiades_id == 737053
    assert places[0].level == "site"
    assert places[1].trismegistos_geo_id == 332
    assert places[1].level == "nome"


def test_provenance_type_other_than_located_ignored() -> None:
    body = '<provenance type="found"><p><placeName ref="https://www.trismegistos.org/place/999">X</placeName></p></provenance>'
    assert parse_places(_tree(body)) == []


def test_origplace_is_free_text_only() -> None:
    body = "<origPlace>Soknopaiu Nesos (Arsinoites, Ägypten)</origPlace>"
    assert parse_origplace_text(_tree(body)) == "Soknopaiu Nesos (Arsinoites, Ägypten)"
    # And origPlace contributes no linked place references.
    assert parse_places(_tree(body)) == []
