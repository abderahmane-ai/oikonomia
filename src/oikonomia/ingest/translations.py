"""Parse translation files (document-level English translations).

Translations are aligned to the Greek only at the *document* level (a single
``<div type="translation">`` blob), and cover ~9.8% of DDbDP. We extract the
plain text and the declared language, guarding against non-English content. No
character alignment to the Greek is attempted — that alignment does not exist,
and pretending otherwise would strand any span projected through it.
"""

from __future__ import annotations

from lxml import etree
from pydantic import BaseModel

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


class TranslationDoc(BaseModel):
    """One translation of one document."""

    tm_id: int
    seq: int
    lang: str | None
    text: str


def _collect_text(el: etree._Element) -> str:
    """Concatenate all descendant text of an element, whitespace-normalised."""
    texts = [t for t in el.itertext() if isinstance(t, str)]
    return " ".join("".join(texts).split())


def parse_translation(xml_bytes: bytes, tm_id: int, seq: int) -> TranslationDoc | None:
    """Parse a translation file; return ``None`` if it holds no translation div."""
    parser = etree.XMLParser(recover=False, resolve_entities=False, no_network=True)
    tree = etree.ElementTree(etree.fromstring(xml_bytes, parser=parser))
    div = tree.find(f'.//{{{TEI_NS}}}div[@type="translation"]')
    if div is None:
        return None
    lang = div.get(XML_LANG)
    text = _collect_text(div)
    if not text:
        return None
    return TranslationDoc(tm_id=tm_id, seq=seq, lang=lang, text=text)
