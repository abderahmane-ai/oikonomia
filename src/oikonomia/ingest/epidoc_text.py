"""EpiDoc → dual text views with a bidirectional offset map.

This is the load-bearing module of the ingest pipeline. It renders a DDbDP
edition into two aligned character strings and locates every editorial
phenomenon and numeral as a span, so that no downstream stage ever needs to
re-open the XML.

Rendering semantics (Leiden / EpiDoc conventions; the reg/orig and
supplied/expan behaviours were confirmed against the EpiDoc Guidelines)
------------------------------------------------------------------------
For each element, text is emitted into the **edited** view (the scholarly
reading), the **diplomatic** view (what is on the papyrus), or both:

===================  =========================  ==========================
Element              Edited view                Diplomatic view
===================  =========================  ==========================
plain text           kept                       kept
``<unclear>``        kept                       kept
``<num>``            kept (value recorded)      kept
``<hi> <add> <del>`` kept                       kept
``<abbr>``           kept                       kept
``<ex>``             kept (the expansion)       dropped
``<supplied>``       kept (restoration)         dropped
``<reg> <corr>``     kept                       dropped
``<surplus>``        dropped                    kept
``<orig> <sic>``     dropped                    kept
``<gap>``            placeholder                placeholder
``<space>``          " "                        " "
``<lb>``             line boundary (newline)    line boundary (newline)
``<choice>``         render reg/corr child      render orig/sic child
``<app>``            render ``<lem>`` only      render ``<lem>`` only
``<head> <note>``    dropped                    dropped
===================  =========================  ==========================

The two views share every "both" chunk; those shared chunks become the aligned
segments of the :class:`~oikonomia.schemas.spans.OffsetMap`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from oikonomia.config import IngestConfig
from oikonomia.ingest.numerals import parse_num_value
from oikonomia.schemas.document import (
    Document,
    LineRef,
    MarkupKind,
    MarkupSpan,
    Numeral,
)
from oikonomia.schemas.spans import AlignedSegment, CharSpan, OffsetMap

if TYPE_CHECKING:
    from lxml.etree import _Element

TEI_NS = "http://www.tei-c.org/ns/1.0"

# Elements whose text is editorial-only (present in the edited reading, not on
# the papyrus): expansion, restoration, regularisation, correction.
_EDITED_ONLY = frozenset({"ex", "supplied", "reg", "corr"})
# Elements whose text is diplomatic-only (on the papyrus, excised by the editor).
_DIPLO_ONLY = frozenset({"surplus", "orig", "sic"})
# Elements that contribute no text and whose subtree is not part of the edition.
_SKIP = frozenset({"head", "note", "milestone", "figure", "figDesc"})

# Map EpiDoc element localnames to the markup kinds we record as spans.
_MARKUP_KIND = {
    "gap": MarkupKind.GAP,
    "unclear": MarkupKind.UNCLEAR,
    "supplied": MarkupKind.SUPPLIED,
    "surplus": MarkupKind.SURPLUS,
    "expan": MarkupKind.EXPANSION,
    "abbr": MarkupKind.ABBREV,
    "reg": MarkupKind.REGULARIZED,
    "corr": MarkupKind.CORRECTED,
}
# EpiDoc attributes worth keeping on a markup span for later use.
_KEEP_ATTRS = ("reason", "quantity", "unit", "extent", "cert", "evidence")


def _localname(el: _Element) -> str:
    tag = el.tag
    if not isinstance(tag, str):  # comments / PIs
        return ""
    return tag.rsplit("}", 1)[-1]


def _child_by_local(el: _Element, names: tuple[str, ...]) -> _Element | None:
    for child in el:
        if _localname(child) in names:
            return child
    return None


class _Builder:
    """Accumulates both views, aligned segments, markup spans, numerals, lines."""

    def __init__(self, cfg: IngestConfig) -> None:
        self._cfg = cfg
        self._ed: list[str] = []
        self._dp: list[str] = []
        self._ed_len = 0
        self._dp_len = 0
        self.segments: list[AlignedSegment] = []
        self.markup: list[MarkupSpan] = []
        self.numerals: list[Numeral] = []
        self.lines: list[LineRef] = []
        self.flags: set[str] = set()
        self._open_line: tuple[str, int, int] | None = None
        self._line_counter = 0

    # -- emission -----------------------------------------------------------
    def _emit(self, text: str, in_ed: bool, in_dp: bool) -> None:
        if not text:
            return
        if in_ed and in_dp:
            self.segments.append(
                AlignedSegment(
                    e0=self._ed_len,
                    e1=self._ed_len + len(text),
                    d0=self._dp_len,
                    d1=self._dp_len + len(text),
                )
            )
        if in_ed:
            self._ed.append(text)
            self._ed_len += len(text)
        if in_dp:
            self._dp.append(text)
            self._dp_len += len(text)

    # -- special elements ---------------------------------------------------
    def _emit_linebreak(self, el: _Element) -> None:
        n = el.get("n") or str(self._line_counter + 1)
        self._close_open_line()
        # Suppress a leading newline before any content has been emitted.
        if self._ed_len > 0 or self._dp_len > 0:
            self._emit("\n", in_ed=True, in_dp=True)
        self._open_line = (n, self._ed_len, self._dp_len)
        self._line_counter += 1

    def _close_open_line(self) -> None:
        if self._open_line is None:
            return
        n, es, ds = self._open_line
        self.lines.append(
            LineRef(
                n=n,
                edited=CharSpan(start=es, end=self._ed_len) if self._ed_len > es else None,
                diplomatic=CharSpan(start=ds, end=self._dp_len) if self._dp_len > ds else None,
            )
        )
        self._open_line = None

    def _emit_gap(self, el: _Element, in_ed: bool, in_dp: bool) -> None:
        self._emit(self._cfg.gap_placeholder, in_ed, in_dp)

    # -- choice / app -------------------------------------------------------
    def _walk_choice(self, el: _Element, in_ed: bool, in_dp: bool) -> None:
        edited_child = _child_by_local(el, ("reg", "corr"))
        diplo_child = _child_by_local(el, ("orig", "sic"))
        if edited_child is not None:
            self._walk(edited_child, in_ed, False)
        if diplo_child is not None:
            self._walk(diplo_child, False, in_dp)
        if edited_child is None and diplo_child is None:
            self.flags.add("choice_without_reg_or_orig")

    def _walk_app(self, el: _Element, in_ed: bool, in_dp: bool) -> None:
        # Apparatus criticus: render the lemma (chosen reading); ignore <rdg>.
        lem = _child_by_local(el, ("lem",))
        if lem is not None:
            self._walk(lem, in_ed, in_dp)
        else:
            self.flags.add("app_without_lem")

    # -- main recursion -----------------------------------------------------
    def _walk(self, el: _Element, in_ed: bool, in_dp: bool) -> None:
        tag = _localname(el)
        ed0, dp0 = self._ed_len, self._dp_len

        if tag == "choice":
            self._walk_choice(el, in_ed, in_dp)
        elif tag == "app":
            self._walk_app(el, in_ed, in_dp)
        elif tag == "lb":
            self._emit_linebreak(el)
        elif tag == "gap":
            self._emit_gap(el, in_ed, in_dp)
        elif tag == "space":
            self._emit(" ", in_ed, in_dp)
        elif tag in _SKIP:
            return  # subtree contributes nothing; caller handles our tail
        else:
            cin_ed = in_ed and tag not in _DIPLO_ONLY
            cin_dp = in_dp and tag not in _EDITED_ONLY
            if el.text:
                self._emit(el.text, cin_ed, cin_dp)
            for child in el:
                self._walk(child, cin_ed, cin_dp)
                if child.tail:
                    self._emit(child.tail, cin_ed, cin_dp)

        ed1, dp1 = self._ed_len, self._dp_len
        self._record(tag, el, ed0, ed1, dp0, dp1)

    def _record(
        self, tag: str, el: _Element, ed0: int, ed1: int, dp0: int, dp1: int
    ) -> None:
        if tag == "num":
            raw = el.get("value")
            self.numerals.append(
                Numeral(
                    value=parse_num_value(raw),
                    raw_value=raw,
                    text="".join(self._ed)[ed0:ed1] if ed1 > ed0 else "",
                    edited=CharSpan(start=ed0, end=ed1) if ed1 > ed0 else None,
                    diplomatic=CharSpan(start=dp0, end=dp1) if dp1 > dp0 else None,
                )
            )
        kind = _MARKUP_KIND.get(tag)
        if kind is None:
            return
        edited = CharSpan(start=ed0, end=ed1) if ed1 > ed0 else None
        diplomatic = CharSpan(start=dp0, end=dp1) if dp1 > dp0 else None
        if edited is None and diplomatic is None:
            return
        attrs: dict[str, str] = {}
        for name in _KEEP_ATTRS:
            value = el.get(name)
            if value is not None:
                attrs[name] = value
        self.markup.append(
            MarkupSpan(kind=kind, edited=edited, diplomatic=diplomatic, attrs=attrs)
        )

    # -- finalisation -------------------------------------------------------
    def finalize(self) -> tuple[str, str, OffsetMap]:
        self._close_open_line()
        return "".join(self._ed), "".join(self._dp), OffsetMap(segments=self.segments)


def _edition_divs(tree: etree._ElementTree) -> list[_Element]:
    return tree.findall(f'.//{{{TEI_NS}}}div[@type="edition"]')


def _text_idnos(tree: etree._ElementTree) -> tuple[str | None, str | None]:
    """Return ``(tm_id_str, ddb_hybrid)`` from the publication statement."""
    tm = None
    ddb = None
    for idno in tree.findall(f".//{{{TEI_NS}}}idno"):
        typ = idno.get("type")
        val = (idno.text or "").strip()
        if typ == "TM" and val:
            tm = val
        elif typ == "ddb-hybrid" and val:
            ddb = val
    return tm, ddb


def parse_ddbdp(xml_bytes: bytes, stem: str, cfg: IngestConfig) -> Document:
    """Parse one DDbDP edition file into a :class:`Document`.

    ``stem`` is the filename stem (e.g. ``"100042"`` or ``"13a"``) and supplies
    the TM id when the XML omits an explicit ``<idno type="TM">``.
    """
    from oikonomia.ingest.paths import parse_stem

    parser = etree.XMLParser(recover=False, resolve_entities=False, no_network=True)
    tree = etree.ElementTree(etree.fromstring(xml_bytes, parser=parser))

    tm_str, ddb_hybrid = _text_idnos(tree)
    numeric_stem, _ = parse_stem(stem)
    tm_id = int(tm_str) if tm_str and tm_str.isdigit() else numeric_stem

    builder = _Builder(cfg)
    divs = _edition_divs(tree)
    if not divs:
        builder.flags.add("no_edition_div")
    for div in divs:
        builder._walk(div, in_ed=True, in_dp=True)

    edited, diplomatic, offset_map = builder.finalize()
    if not edited.strip():
        builder.flags.add("empty_edited_text")

    return Document(
        tm_id=tm_id,
        stem=stem,
        ddb_hybrid=ddb_hybrid,
        edited_text=edited,
        diplomatic_text=diplomatic,
        offset_map=offset_map,
        markup=builder.markup,
        numerals=builder.numerals,
        lines=builder.lines,
        parse_flags=sorted(builder.flags),
    )
