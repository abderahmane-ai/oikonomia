"""The single XML parser configuration used for every idp.data file.

All three readers (DDbDP editions, HGV metadata, translations) must agree on
parser settings, so they share this one factory rather than each building their
own ``etree.XMLParser``.

The settings are deliberate:

``recover=False``
    Malformed XML is a finding, not something to paper over. A document that
    cannot be parsed is recorded in the failure report, never silently
    half-parsed into a partial edition.
``resolve_entities=False`` / ``no_network=True``
    The corpus is third-party XML carrying DOCTYPE declarations. Never fetch or
    expand external entities (billion-laughs / XXE).
``collect_ids=False``
    Measured, not assumed. With lxml's default ID collection, 512 of the 67,980
    DDbDP files (0.75%) fail with "ID <x> already defined" — duplicate
    ``xml:id`` values that upstream editors introduced when merging fragments
    (``_ctr``, ``column_i``, ``_FrA``…). Those documents are otherwise
    well-formed and their text is perfectly extractable; refusing them would
    discard real papyri over a defect in an attribute we never read. Disabling
    ID collection stops enforcing uniqueness and recovers all of them. We do
    not resolve IDREFs anywhere, so nothing downstream depends on the ID table.
"""

from __future__ import annotations

from lxml import etree


def parse_xml(xml_bytes: bytes) -> etree._ElementTree:
    """Parse ``xml_bytes`` with the corpus-wide parser settings.

    Raises ``etree.XMLSyntaxError`` on genuinely malformed XML.
    """
    parser = etree.XMLParser(
        recover=False,
        resolve_entities=False,
        no_network=True,
        collect_ids=False,
    )
    return etree.ElementTree(etree.fromstring(xml_bytes, parser=parser))
