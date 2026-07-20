"""Tests for the shared corpus XML parser configuration."""

from __future__ import annotations

import pytest
from lxml import etree

from oikonomia.ingest.xml_parser import parse_xml

# Duplicate xml:id — rejected by lxml's default ID collection, but present in
# 512 real DDbDP files where editors merged fragments. Must parse.
DUPLICATE_IDS = (
    '<TEI xmlns="http://www.tei-c.org/ns/1.0">'
    '<text><body>'
    '<div type="edition" xml:id="_ctr"><ab><lb n="1"/>α</ab></div>'
    '<div type="edition" xml:id="_ctr"><ab><lb n="1"/>β</ab></div>'
    "</body></text></TEI>"
).encode()


def test_duplicate_xml_ids_parse() -> None:
    """The 0.75% failure tail: duplicate xml:id must not reject a document."""
    tree = parse_xml(DUPLICATE_IDS)
    divs = tree.findall(".//{http://www.tei-c.org/ns/1.0}div")
    assert len(divs) == 2
    assert [d.get("{http://www.w3.org/XML/1998/namespace}id") for d in divs] == [
        "_ctr",
        "_ctr",
    ]


def test_malformed_xml_still_raises() -> None:
    """Relaxing ID checks must not turn into general error recovery."""
    with pytest.raises(etree.XMLSyntaxError):
        parse_xml(b"<TEI><unclosed></TEI>")


def test_external_entities_not_resolved() -> None:
    """Third-party XML must never expand external entities (XXE)."""
    xxe = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<r>&x;</r>"
    )
    try:
        tree = parse_xml(xxe)
    except etree.XMLSyntaxError:
        return  # refusing outright is equally acceptable
    assert "root:" not in (tree.getroot().text or "")
