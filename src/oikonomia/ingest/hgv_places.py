"""Parse HGV provenance into machine-linkable place references.

The linkable place data lives in ``<provenance type="located">`` as one or more
``<placeName>`` elements whose ``@ref`` is a *space-separated* list of gazetteer
URIs mixing Trismegistos and Pleiades, e.g.::

    <placeName type="ancient"
        ref="https://www.trismegistos.org/place/2157 https://pleiades.stoa.org/places/737053">

The free-text ``<origPlace>`` (e.g. "Soknopaiu Nesos (Arsinoites, Ägypten)") is
captured for notes only and is **structurally forbidden from joins** — it is
unlinked German prose.
"""

from __future__ import annotations

import re

from lxml import etree

from oikonomia.schemas.metadata import PlaceRef

TEI_NS = "http://www.tei-c.org/ns/1.0"

_TM_PLACE = re.compile(r"trismegistos\.org/place/(\d+)")
_PLEIADES = re.compile(r"pleiades\.stoa\.org/places/(\d+)")


def _place_from_placename(el: etree._Element) -> PlaceRef:
    ref = el.get("ref") or ""
    tm_match = _TM_PLACE.search(ref)
    pl_match = _PLEIADES.search(ref)
    return PlaceRef(
        trismegistos_geo_id=int(tm_match.group(1)) if tm_match else None,
        pleiades_id=int(pl_match.group(1)) if pl_match else None,
        name=(el.text or "").strip() or None,
        level=el.get("subtype") or ("site" if el.get("type") == "ancient" else None),
        raw_ref=ref or None,
    )


def parse_places(tree: etree._ElementTree) -> list[PlaceRef]:
    """Return the linked place references from ``<provenance type="located">``."""
    places: list[PlaceRef] = []
    for prov in tree.findall(f".//{{{TEI_NS}}}provenance"):
        if prov.get("type") != "located":
            continue
        for pn in prov.findall(f".//{{{TEI_NS}}}placeName"):
            places.append(_place_from_placename(pn))
    return places


def parse_origplace_text(tree: etree._ElementTree) -> str | None:
    """Free-text ``<origPlace>`` — NOTES ONLY, never a join key."""
    el = tree.find(f".//{{{TEI_NS}}}origPlace")
    if el is None:
        return None
    return (el.text or "").strip() or None
