"""Tests for HGV date parsing and interval semantics."""

from __future__ import annotations

from lxml import etree

from oikonomia.ingest.hgv_dates import parse_dates
from oikonomia.schemas.metadata import DatePrecision

TEI = "http://www.tei-c.org/ns/1.0"


def _tree(origdate_xml: str) -> etree._ElementTree:
    xml = (
        f'<TEI xmlns="{TEI}"><teiHeader><fileDesc><sourceDesc><msDesc><history>'
        f"<origin>{origdate_xml}</origin>"
        "</history></msDesc></sourceDesc></fileDesc></teiHeader></TEI>"
    )
    return etree.ElementTree(etree.fromstring(xml.encode("utf-8")))


def test_exact_when_day_precision() -> None:
    dates = parse_dates(_tree('<origDate when="0050-03-17">17. März 50</origDate>'))
    assert len(dates) == 1
    d = dates[0]
    assert d.lo == 50 and d.hi == 50
    assert d.precision == DatePrecision.DAY
    assert d.span_years == 0
    assert d.raw == "17. März 50"


def test_bce_year_is_negative() -> None:
    dates = parse_dates(_tree('<origDate when="-0044">44 v. Chr.</origDate>'))
    assert dates[0].lo == -44 and dates[0].hi == -44


def test_range_notbefore_notafter() -> None:
    dates = parse_dates(_tree('<origDate notBefore="0100" notAfter="0199">2. Jh.</origDate>'))
    d = dates[0]
    assert d.lo == 100 and d.hi == 199
    assert d.precision == DatePrecision.RANGE
    assert d.span_years == 99


def test_alternatives_kept_and_ordered_primary_first() -> None:
    xml = (
        '<origDate xml:id="dateAlternative1" notBefore="0200" notAfter="0250">alt</origDate>'
        '<origDate when="0117">primary</origDate>'
    )
    dates = parse_dates(_tree(xml))
    assert len(dates) == 2
    # Primary (non-alternative) must sort first even though it appears second.
    assert dates[0].is_alternative is False
    assert dates[0].lo == 117
    assert dates[1].is_alternative is True
