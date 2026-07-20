"""Tests for the proximity baseline.

Expectations are hand-derived from short, real-shaped Greek phrases. The point
of a baseline is that its failures are *known*, so the tests pin down the rules
it does encode and the cases it is known to get wrong.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from oikonomia.labeling.lexicon import load_lexicon
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.weak_rules import label_document, run_baseline
from oikonomia.schemas.spans import CharSpan

RESOURCES = Path(__file__).resolve().parents[1] / "resources"


@pytest.fixture(scope="module")
def matcher() -> Matcher:
    return Matcher(load_lexicon(RESOURCES))


def _label(text: str, matcher: Matcher, numerals: list[str], lines: list[str] | None = None):
    """Label ``text``, locating each numeral and line by substring search."""
    numeral_spans = []
    cursor = 0
    for n in numerals:
        at = text.index(n, cursor)
        numeral_spans.append(CharSpan(start=at, end=at + len(n)))
        cursor = at + len(n)
    if lines is None:
        line_spans = [CharSpan(start=0, end=len(text))]
    else:
        line_spans = []
        cursor = 0
        for ln in lines:
            at = text.index(ln, cursor)
            line_spans.append(CharSpan(start=at, end=at + len(ln)))
            cursor = at + len(ln)
    return label_document(text, numeral_spans, line_spans, matcher)


def _rels(result, rel_type: str) -> list[tuple[str, str]]:
    return [
        (result.entities[r.head].text, result.entities[r.tail].text)
        for r in result.relations
        if r.type == rel_type
    ]


def test_commodity_unit_quantity_chain(matcher: Matcher) -> None:
    """The canonical account phrasing: commodity, unit, number."""
    result = _label("πυροῦ ἀρτάβας μ", matcher, ["μ"])
    labels = {(e.label, e.text) for e in result.entities}
    assert ("COMMODITY", "πυροῦ") in labels
    assert ("UNIT", "ἀρτάβας") in labels
    assert ("QUANTITY", "μ") in labels
    assert _rels(result, "HAS_UNIT") == [("μ", "ἀρτάβας")]
    assert _rels(result, "HAS_QUANTITY") == [("πυροῦ", "μ")]


def test_currency_makes_it_money_not_quantity(matcher: Matcher) -> None:
    result = _label("ἀργυρίου δραχμὰς μ", matcher, ["μ"])
    money = [e for e in result.entities if e.label == "MONEY_AMOUNT"]
    assert [e.text for e in money] == ["μ"]
    assert not [e for e in result.entities if e.label == "QUANTITY"]
    assert ("μ", "δραχμὰς") in _rels(result, "HAS_CURRENCY")


def test_regnal_year_numeral_is_not_a_quantity(matcher: Matcher) -> None:
    """Rule 3: ιϛ in "ιϛ ἔτος" is part of the date, not an amount."""
    result = _label("ιϛ ἔτος", matcher, ["ιϛ"])
    assert not [e for e in result.entities if e.label in {"QUANTITY", "MONEY_AMOUNT"}]
    assert [e.label for e in result.entities] == ["DATE_REF"]


def test_date_numeral_suppressed_but_real_quantity_kept(matcher: Matcher) -> None:
    """Both in one line: the regnal year drops out, the artabas do not."""
    text = "ιϛ ἔτος πυροῦ ἀρτάβας μ"
    result = _label(text, matcher, ["ιϛ", "μ"])
    amounts = [e.text for e in result.entities if e.label == "QUANTITY"]
    assert amounts == ["μ"]
    assert _rels(result, "HAS_UNIT") == [("μ", "ἀρτάβας")]


def test_attachment_does_not_cross_a_line_boundary(matcher: Matcher) -> None:
    """Rule 2: the next line is a different transaction."""
    line1, line2 = "πυροῦ ἀρτάβας μ", "κριθῆς η"
    text = f"{line1}\n{line2}"
    result = _label(text, matcher, ["μ", "η"], lines=[line1, line2])
    # η is on line 2; it must not borrow line 1's ἀρτάβας.
    assert _rels(result, "HAS_UNIT") == [("μ", "ἀρτάβας")]
    assert ("κριθῆς", "η") in _rels(result, "HAS_QUANTITY")


def test_left_preference_on_a_tie(matcher: Matcher) -> None:
    """Units precede numerals 80%+ of the time, so ties break left."""
    # Equidistant units either side of the numeral: the left one must win.
    text = "ἀρτάβας μ κεράμια"
    result = _label(text, matcher, ["μ"])
    assert _rels(result, "HAS_UNIT") == [("μ", "ἀρτάβας")]


def test_charged_under_tax_term(matcher: Matcher) -> None:
    result = _label("ὑπὲρ λαογραφίας δραχμὰς η", matcher, ["η"])
    assert ("η", "λαογραφίας") in _rels(result, "CHARGED_UNDER")


def test_window_limits_attachment(matcher: Matcher) -> None:
    """A unit far away in the same line must not attach."""
    text = "ἀρτάβας " + "α" * 60 + " μ"
    result = _label(text, matcher, ["μ"])
    assert _rels(result, "HAS_UNIT") == []


def test_no_numerals_yields_no_relations(matcher: Matcher) -> None:
    result = _label("πυροῦ ἀρτάβας", matcher, [])
    assert result.relations == []
    assert {e.label for e in result.entities} == {"COMMODITY", "UNIT"}


def test_spans_index_the_original_text(matcher: Matcher) -> None:
    """Every predicted span must slice back to its own recorded text."""
    text = "ἀργυρίου δραχμὰς μ καὶ πυροῦ ἀρτάβας η"
    result = _label(text, matcher, ["μ", "η"])
    assert result.entities
    for ent in result.entities:
        assert ent.span.slice(text) == ent.text


def test_known_failure_adjectival_metal_is_mislabelled(matcher: Matcher) -> None:
    """A documented false positive, pinned so it cannot regress silently.

    In "ποτήριον χαλκοῦν" ("a bronze cup") χαλκοῦν is an adjective, but the
    lexicon calls it CURRENCY. The guidelines (§5) require gold annotation to
    fix this; the baseline cannot. Asserting it keeps the limitation visible.
    """
    result = _label("ποτήριον χαλκοῦν", matcher, [])
    assert [(e.label, e.text) for e in result.entities] == [("CURRENCY", "χαλκοῦν")]


def test_run_baseline_over_batches(matcher: Matcher) -> None:
    """The corpus runner must aggregate what label_document produces."""
    text = "ιϛ ἔτος πυροῦ ἀρτάβας μ"
    doc = {
        "edited_text": text,
        "numerals": [
            {"edited": {"start": text.index("ιϛ"), "end": text.index("ιϛ") + 2}},
            {"edited": {"start": text.index("μ"), "end": text.index("μ") + 1}},
            {"edited": None},  # unlocatable numeral: must be skipped, not crash
        ],
        "lines": [{"edited": {"start": 0, "end": len(text)}}],
    }
    df = pd.DataFrame({"document_json": [json.dumps(doc), json.dumps(doc)]})
    report = run_baseline([df], matcher)

    assert report.n_docs == 2
    # Two locatable numerals per doc; the regnal year is suppressed.
    assert report.n_numerals == 4
    assert report.n_numerals_suppressed_as_date == 2
    assert report.date_suppression_rate == 0.5
    # The surviving numeral is linked in both documents.
    assert report.numeral_link_rate == 1.0
    assert report.relations_by_type["HAS_UNIT"] == 2


def test_run_baseline_skips_empty_documents(matcher: Matcher) -> None:
    df = pd.DataFrame(
        {"document_json": [json.dumps({"edited_text": "", "numerals": [], "lines": []})]}
    )
    report = run_baseline([df], matcher)
    assert report.n_docs == 0
    assert report.numeral_link_rate == 0.0
