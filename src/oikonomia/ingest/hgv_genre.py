"""Parse HGV keyword terms and map the German folksonomy to canonical genres.

Genre lives in ``keywords[@scheme="hgv"]/<term>`` as free German terms — an
uncontrolled folksonomy of ~415 values mixing document genre ("Quittung"),
commodity ("Wein"), and topic ("Steuern"). We keep the raw terms verbatim and,
via ``resources/genre_map.yaml``, project the *genre*-facet terms onto a small
canonical taxonomy. Full curation of all 415 terms is Phase 2 work; the shipped
map seeds the frequent terms and is extended there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"


def parse_terms(tree: etree._ElementTree) -> list[str]:
    """Return raw HGV keyword terms in document order."""
    terms: list[str] = []
    for kw in tree.findall(f".//{{{TEI_NS}}}keywords"):
        if kw.get("scheme") not in (None, "hgv"):
            continue
        for term in kw.findall(f"{{{TEI_NS}}}term"):
            text = (term.text or "").strip()
            if text:
                terms.append(text)
    return terms


def load_genre_map(path: Path) -> dict[str, dict[str, str]]:
    """Load the term→{canonical, facet} mapping resource."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mapping = data.get("terms", data)
    out: dict[str, dict[str, str]] = {}
    for term, spec in mapping.items():
        if isinstance(spec, dict) and "canonical" in spec:
            out[term] = {"canonical": str(spec["canonical"]), "facet": str(spec.get("facet", ""))}
    return out


def map_terms(terms: list[str], genre_map: dict[str, dict[str, str]]) -> list[str]:
    """Project raw terms onto canonical *genre*-facet labels (deduplicated)."""
    seen: list[str] = []
    for t in terms:
        spec = genre_map.get(t)
        if spec and spec.get("facet") == "genre":
            canon = spec["canonical"]
            if canon not in seen:
                seen.append(canon)
    return seen
