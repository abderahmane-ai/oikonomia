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

import re
from typing import TYPE_CHECKING

from lxml import etree

from oikonomia.config import IngestConfig
from oikonomia.ingest.numerals import parse_num_value
from oikonomia.ingest.xml_parser import parse_xml
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


_WS_RUN = re.compile(r"\s+")


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


def _rstrip_text_before(lb: _Element) -> None:
    """Strip trailing whitespace from the text node immediately preceding ``lb``.

    That whitespace is the source file's own indentation, not part of the
    edition, and it sits in one of three places (measured over the corpus:
    82% / 9% / 2% of line breaks respectively).
    """
    prev = lb.getprevious()
    if prev is None:
        parent = lb.getparent()
        if parent is not None and parent.text:
            parent.text = parent.text.rstrip()
        return
    if prev.tail:
        prev.tail = prev.tail.rstrip()
        return
    # No tail: the preceding characters are the last text *inside* `prev`
    # (e.g. `<supplied>ά\n    </supplied><lb break="no"/>`). Descend to it.
    _rstrip_last_text_in(prev)


def _rstrip_last_text_in(el: _Element) -> None:
    """Strip trailing whitespace from the last text node inside ``el``."""
    node = el
    while True:
        last = node[-1] if len(node) else None
        if last is None:
            if node.text:
                node.text = node.text.rstrip()
            return
        if last.tail:
            last.tail = last.tail.rstrip()
            return
        node = last


def _canonical_ws_mask(text: str) -> list[bool]:
    """Mark which characters survive canonicalisation. Deletions only.

    A run of whitespace collapses to a single character — the newline if the
    run contains one, else its first space — and leading/trailing runs vanish
    entirely. Nothing is ever substituted, so the surviving characters keep
    their relative order and a span can be remapped by counting deletions.
    """
    keep = [True] * len(text)
    for m in _WS_RUN.finditer(text):
        start, end = m.span()
        if start == 0 or end == len(text):
            chosen = -1  # leading/trailing padding: drop the run outright
        else:
            nl = text.find("\n", start, end)
            chosen = nl if nl >= 0 else start
        for i in range(start, end):
            keep[i] = i == chosen
    return keep


def _apply_mask(text: str, keep: list[bool]) -> tuple[str, list[int]]:
    """Return the canonical text and a prefix table for remapping offsets.

    ``prefix[i]`` is the number of surviving characters before old index ``i``,
    which is exactly the new index of the first survivor at or after ``i``. So
    an old span ``[i, j)`` becomes ``[prefix[i], prefix[j])``.
    """
    prefix = [0] * (len(text) + 1)
    total = 0
    for i, k in enumerate(keep):
        prefix[i] = total
        total += k
    prefix[len(text)] = total
    new_text = "".join(c for c, k in zip(text, keep, strict=True) if k)
    return new_text, prefix


def _remap(span: CharSpan | None, prefix: list[int]) -> CharSpan | None:
    """Move a span onto canonical coordinates, or drop it if nothing survives."""
    if span is None:
        return None
    start, end = prefix[span.start], prefix[span.end]
    return CharSpan(start=start, end=end) if end > start else None


def _remap_segments(
    segments: list[AlignedSegment],
    ed_keep: list[bool],
    dp_keep: list[bool],
    ed_prefix: list[int],
    dp_prefix: list[int],
) -> list[AlignedSegment]:
    """Remap aligned segments, splitting where the two views diverge.

    A segment covers the same characters in both views, but a character can
    survive in one and not the other — the space after an edited-only
    ``<supplied>`` may end a run in the edited view while the diplomatic view
    still needs it. Such a character is simply left uncovered, exactly as
    view-specific text already is, and the segment splits around it.
    """
    out: list[AlignedSegment] = []
    for seg in segments:
        length = seg.e1 - seg.e0
        # Fast path: nothing inside was dropped in either view, so the whole
        # segment maps across unchanged. This is the overwhelming majority.
        if all(ed_keep[seg.e0 : seg.e1]) and all(dp_keep[seg.d0 : seg.d1]):
            e0, d0 = ed_prefix[seg.e0], dp_prefix[seg.d0]
            out.append(AlignedSegment(e0=e0, e1=e0 + length, d0=d0, d1=d0 + length))
            continue
        run = 0
        for k in range(length + 1):
            both = k < length and ed_keep[seg.e0 + k] and dp_keep[seg.d0 + k]
            if both:
                run += 1
                continue
            if run:
                e_end, d_end = ed_prefix[seg.e0 + k], dp_prefix[seg.d0 + k]
                out.append(
                    AlignedSegment(e0=e_end - run, e1=e_end, d0=d_end - run, d1=d_end)
                )
                run = 0
    return out


def normalize_edition_whitespace(div: _Element) -> None:
    """Strip the XML's own layout whitespace from an edition, in place.

    DDbDP files are pretty-printed, so every tag is preceded by a newline and
    an indent. That whitespace is markup formatting, not text, but it lands in
    the character stream and produced two distinct defects:

    * ``<lb break="no"/>`` marks a break falling *inside* a word — the scribe
      ran out of room and continued on the next line — so no separator belongs
      there at all. ναύκληρος came out as "ναύκλη ρος": text no lexicon matches
      and no tokenizer handles well. 35.28% of documents contain at least one.
    * At an ordinary ``<lb>``, the indent survived alongside the newline the
      parser emits, so a line boundary read ``'\\n\\n    \\n'`` instead of
      ``'\\n'``.

    Only the ``break="no"`` case is handled here, because only it is
    *semantic*: the two halves must touch, and no later pass can infer that
    from the character stream alone. Every other whitespace defect — doubled
    spaces, a space before a newline, leading and trailing padding — is
    resolved by :func:`canonicalize_whitespace` in ``finalize``, which also
    remaps the spans. Doing it there rather than here keeps this pass from
    having to anticipate every shape the XML takes.
    """
    for lb in div.iter(f"{{{TEI_NS}}}lb"):
        if lb.get("break") != "no":
            continue
        _rstrip_text_before(lb)
        if lb.tail:
            lb.tail = lb.tail.lstrip()


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
        # EpiDoc `<lb break="no"/>` marks a line break that falls *inside* a
        # word — the scribe ran out of room and continued on the next line.
        # Emitting a separator there splits the word in two, which is wrong in
        # the text and wrong for every consumer of it: "ναύκληρος" becomes
        # "ναύκλη ρος", which no lexicon matches and no tokenizer handles well.
        # 35% of DDbDP documents contain at least one.
        #
        # The line boundary is still recorded in `lines` — the papyrus really
        # did break there — but the character stream runs on unbroken.
        # Any doubling with neighbouring whitespace is resolved by the
        # canonicalisation pass in `finalize`; only the *absence* of a
        # separator is semantic and has to be decided here.
        word_continues = el.get("break") == "no"
        if not word_continues:
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
        """Close the last line, canonicalise whitespace, and remap every span.

        The XML is pretty-printed, so its indentation lands in the character
        stream: a line boundary read ``'\\n\\n    \\n'`` and vacats collided
        with the spaces around them. Canonicalising here — after the text is
        built but before anything outside sees it — means one component decides
        whitespace, and the stored text, the `OffsetMap`, markup, numeral and
        line spans, and gold annotation offsets all index the same string.
        """
        self._close_open_line()
        ed, dp = "".join(self._ed), "".join(self._dp)
        ed_keep, dp_keep = _canonical_ws_mask(ed), _canonical_ws_mask(dp)
        new_ed, ed_prefix = _apply_mask(ed, ed_keep)
        new_dp, dp_prefix = _apply_mask(dp, dp_keep)

        self.markup = [
            m.model_copy(
                update={
                    "edited": _remap(m.edited, ed_prefix),
                    "diplomatic": _remap(m.diplomatic, dp_prefix),
                }
            )
            for m in self.markup
        ]
        self.numerals = [
            n.model_copy(
                update={
                    "edited": (e := _remap(n.edited, ed_prefix)),
                    "diplomatic": _remap(n.diplomatic, dp_prefix),
                    "text": new_ed[e.start : e.end] if e else "",
                }
            )
            for n in self.numerals
        ]
        self.lines = [
            line.model_copy(
                update={
                    "edited": _remap(line.edited, ed_prefix),
                    "diplomatic": _remap(line.diplomatic, dp_prefix),
                }
            )
            for line in self.lines
        ]
        segments = _remap_segments(self.segments, ed_keep, dp_keep, ed_prefix, dp_prefix)
        self.segments = segments
        return new_ed, new_dp, OffsetMap(segments=segments)


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

    tree = parse_xml(xml_bytes)

    tm_str, ddb_hybrid = _text_idnos(tree)
    numeric_stem, _ = parse_stem(stem)
    tm_id = int(tm_str) if tm_str and tm_str.isdigit() else numeric_stem

    builder = _Builder(cfg)
    divs = _edition_divs(tree)
    if not divs:
        builder.flags.add("no_edition_div")
    for div in divs:
        normalize_edition_whitespace(div)
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
