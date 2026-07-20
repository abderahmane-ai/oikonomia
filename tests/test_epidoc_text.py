"""Tests for the dual-view EpiDoc parser — the load-bearing ingest module.

The crafted fixture is small enough that the expected edited/diplomatic strings
and every span are derived by hand, so these are exact-value tests, not
smoke tests.
"""

from __future__ import annotations

from oikonomia.config import IngestConfig
from oikonomia.ingest.epidoc_text import parse_ddbdp
from oikonomia.schemas.document import MarkupKind

from .conftest import CRAFTED_EDITION, FIXTURES, assert_document_invariants


def test_crafted_edited_and_diplomatic_strings(ingest_cfg) -> None:
    doc = parse_ddbdp(CRAFTED_EDITION, "1", ingest_cfg)
    # Expansion keeps abbr+ex in edited; drops ex in diplomatic.
    # Regularization uses reg in edited, orig in diplomatic.
    # Supplied text is present in edited, absent in diplomatic.
    assert doc.edited_text == "αβγδ\nεηθ"
    assert doc.diplomatic_text == "αβδ\nζθ"


def test_crafted_markup_spans(ingest_cfg) -> None:
    doc = parse_ddbdp(CRAFTED_EDITION, "1", ingest_cfg)
    ed, dp = doc.edited_text, doc.diplomatic_text
    by_kind = {m.kind: m for m in doc.markup}

    # Expansion: edited covers "βγ", diplomatic covers "β".
    exp = by_kind[MarkupKind.EXPANSION]
    assert exp.edited is not None and exp.edited.slice(ed) == "βγ"
    assert exp.diplomatic is not None and exp.diplomatic.slice(dp) == "β"

    # Regularized reg="ε" is edited-only.
    reg = by_kind[MarkupKind.REGULARIZED]
    assert reg.edited is not None and reg.edited.slice(ed) == "ε"
    assert reg.diplomatic is None

    # Supplied "η" is edited-only and carries its reason attribute.
    sup = by_kind[MarkupKind.SUPPLIED]
    assert sup.edited is not None and sup.edited.slice(ed) == "η"
    assert sup.diplomatic is None
    assert sup.attrs.get("reason") == "lost"


def test_crafted_offset_map(ingest_cfg) -> None:
    doc = parse_ddbdp(CRAFTED_EDITION, "1", ingest_cfg)
    om = doc.offset_map
    # Shared characters map; editorial-only characters do not.
    assert om.edited_to_diplomatic(0) == 0  # α
    assert om.edited_to_diplomatic(1) == 1  # β (abbr, shared)
    assert om.edited_to_diplomatic(2) is None  # γ (ex, edited-only)
    assert om.edited_to_diplomatic(3) == 2  # δ (shared)
    assert om.edited_to_diplomatic(5) is None  # ε (reg, edited-only)
    assert om.edited_to_diplomatic(6) is None  # η (supplied, edited-only)
    assert om.edited_to_diplomatic(7) == 5  # θ (shared)
    # Reverse: diplomatic ζ (orig) has no edited counterpart.
    assert om.diplomatic_to_edited(4) is None  # ζ


def test_crafted_lines(ingest_cfg) -> None:
    doc = parse_ddbdp(CRAFTED_EDITION, "1", ingest_cfg)
    assert [ln.n for ln in doc.lines] == ["1", "2"]
    l1, l2 = doc.lines
    assert l1.edited is not None and l1.edited.slice(doc.edited_text) == "αβγδ"
    assert l2.edited is not None and l2.edited.slice(doc.edited_text) == "εηθ"
    assert l1.diplomatic is not None and l1.diplomatic.slice(doc.diplomatic_text) == "αβδ"
    assert l2.diplomatic is not None and l2.diplomatic.slice(doc.diplomatic_text) == "ζθ"


def test_crafted_invariants(ingest_cfg) -> None:
    assert_document_invariants(parse_ddbdp(CRAFTED_EDITION, "1", ingest_cfg))


def test_numeral_extraction(ingest_cfg) -> None:
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition"><ab>'
        '<lb n="1"/><num value="10">δέκα</num> καὶ <num value="1/2">ἥμισυ</num>'
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "5", ingest_cfg)
    assert [n.value for n in doc.numerals] == [10.0, 0.5]
    assert doc.numerals[0].text == "δέκα"
    assert doc.numerals[1].raw_value == "1/2"


def test_gap_uses_configured_placeholder(ingest_cfg) -> None:
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition"><ab><lb n="1"/>α<gap reason="lost" quantity="3" unit="character"/>β'
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "7", ingest_cfg)
    assert doc.edited_text == "α·β"  # ingest_cfg uses '·' as the placeholder
    gap = next(m for m in doc.markup if m.kind == MarkupKind.GAP)
    assert gap.attrs.get("quantity") == "3"


def test_apparatus_uses_lemma_not_readings(ingest_cfg) -> None:
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition"><ab><lb n="1"/>'
        "<app><lem>καλός</lem><rdg>κακός</rdg></app>"
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "9", ingest_cfg)
    assert doc.edited_text == "καλός"
    assert "κακός" not in doc.edited_text


def test_head_and_note_are_dropped(ingest_cfg) -> None:
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition"><head>Text</head><ab><lb n="1"/>'
        "α<note>editor comment</note>β"
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "11", ingest_cfg)
    assert doc.edited_text == "αβ"


def test_real_fixture_parses_and_holds_invariants(ingest_cfg) -> None:
    xml = (FIXTURES / "ddb" / "100042.xml").read_bytes()
    doc = parse_ddbdp(xml, "100042", ingest_cfg)
    assert doc.tm_id == 100042
    assert doc.ddb_hybrid == "sb;30;17708"
    assert len(doc.edited_text) > 0
    assert doc.n_numerals >= 1
    assert_document_invariants(doc)


def test_line_break_inside_a_word_emits_no_separator(ingest_cfg: IngestConfig) -> None:
    """EpiDoc `<lb break="no"/>` falls inside a word, not between words.

    Emitting a newline there splits the word: ναύκληρος became "ναύκλη ρος",
    which no lexicon matches and no tokenizer handles well. 35% of DDbDP
    documents contain at least one.
    """
    # Indented exactly as the real DDbDP files are: the pretty-printer puts a
    # newline and four spaces before the tag, and that whitespace lands in the
    # preceding element's tail. Without indentation this test passes even with
    # the emitted newline suppressed, so the indentation is the point.
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition" xml:lang="grc"><ab>'
        '<lb n="1"/>ναύκλη\n\n    <lb n="2" break="no"/>ρος'
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "1", ingest_cfg)
    assert doc.edited_text == "ναύκληρος"
    # The physical break is still recorded, even though no character marks it.
    assert len(doc.lines) == 2


def test_edited_text_whitespace_is_canonical(ingest_cfg: IngestConfig) -> None:
    """Text comes out with no trace of the XML's own layout.

    DDbDP files are pretty-printed, so every tag carries a newline and indent
    that used to survive into the text: a line boundary read '\\n\\n    \\n'.
    Offsets are only shared across consumers if exactly one component decides
    whitespace, and that component is the parser.
    """
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition" xml:lang="grc"><ab>\n\n    '
        '<lb n="1"/>πυροῦ   ἀρτάβας\n\n    '
        '<lb n="2"/>δραχμὰς ιβ\n\n  '
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "1", ingest_cfg)
    assert doc.edited_text == "πυροῦ ἀρτάβας\nδραχμὰς ιβ"
    # No leading/trailing whitespace, no doubled space, no blank line.
    assert doc.edited_text == doc.edited_text.strip()
    assert "  " not in doc.edited_text
    assert "\n\n" not in doc.edited_text
    assert " \n" not in doc.edited_text and "\n " not in doc.edited_text


def test_vacat_beside_source_spaces_yields_one_separator(ingest_cfg: IngestConfig) -> None:
    """`<space>` is a vacat and emits a space of its own.

    The source puts literal spaces around it too, so the three collided:
    'Ποκῶτος   δραχμὰς'. A vacat meeting a line break must not leave ' \\n'.
    """
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition" xml:lang="grc"><ab>'
        '<lb n="1"/>Ποκῶτος  <space extent="unknown" unit="character"/>  δραχμὰς'
        '  <space extent="unknown" unit="character"/> \n\n    '
        '<lb n="2"/>ιδ'
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "1", ingest_cfg)
    assert doc.edited_text == "Ποκῶτος δραχμὰς\nιδ"


def test_spans_survive_whitespace_canonicalisation(ingest_cfg: IngestConfig) -> None:
    """Canonicalisation deletes characters, so every span must be remapped.

    This is the whole point of doing it inside the parser: a consumer that
    collapsed whitespace afterwards would leave every offset pointing at the
    wrong character.
    """
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition" xml:lang="grc"><ab>\n\n    '
        '<lb n="1"/>πυροῦ   <supplied reason="lost">ἀρτάβας</supplied>\n\n    '
        '<lb n="2"/>δραχμὰς <num value="14">ιδ</num>\n\n  '
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "1", ingest_cfg)
    text = doc.edited_text
    assert text == "πυροῦ ἀρτάβας\nδραχμὰς ιδ"

    # Every span still selects the text it was recorded for.
    num = doc.numerals[0]
    assert num.edited is not None
    assert text[num.edited.start : num.edited.end] == "ιδ" == num.text
    supplied = next(m for m in doc.markup if m.kind is MarkupKind.SUPPLIED)
    assert supplied.edited is not None
    assert text[supplied.edited.start : supplied.edited.end] == "ἀρτάβας"
    # Aligned segments still describe the same characters in both views.
    for seg in doc.offset_map.segments:
        assert text[seg.e0 : seg.e1] == doc.diplomatic_text[seg.d0 : seg.d1]


def test_word_join_strips_whitespace_held_inside_the_previous_element(
    ingest_cfg: IngestConfig,
) -> None:
    """The trailing whitespace is not always in a tail.

    In ~2% of corpus cases the preceding text is the last text node *inside*
    the previous element (`<supplied>ά\n    </supplied><lb break="no"/>χ`),
    so stripping only `prev.tail` leaves the split in place.
    """
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition" xml:lang="grc"><ab>'
        '<lb n="1"/>δρ<supplied reason="lost">α\n\n    </supplied>'
        '<lb n="2" break="no"/>χμάς'
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "1", ingest_cfg)
    assert doc.edited_text == "δραχμάς"


def test_ordinary_line_break_still_separates_words(ingest_cfg: IngestConfig) -> None:
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition" xml:lang="grc"><ab>'
        '<lb n="1"/>πυροῦ<lb n="2"/>ἀρτάβας'
        "</ab></div></body></text></TEI>"
    ).encode()
    doc = parse_ddbdp(xml, "1", ingest_cfg)
    assert doc.edited_text == "πυροῦ\nἀρτάβας"
