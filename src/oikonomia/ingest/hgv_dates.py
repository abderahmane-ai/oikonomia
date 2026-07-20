"""Parse HGV ``<origDate>`` elements into signed year intervals.

Dates live at ``msDesc/history/origin/origDate`` and take one of three forms:

* ``when="0050-03-17"``            — an exact date (day/month/year precision)
* ``notBefore="0100" notAfter="0199"`` — a bounded range
* a single ``notBefore``/``notAfter``  — a one-sided bound

Years are ISO, zero-padded to four digits, with a leading ``-`` for BCE. We
interpret the integer astronomically (e.g. ``-0044`` → year ``-44``). Genuinely
competing datings appear as sibling ``origDate`` elements carrying
``xml:id="dateAlternativeN"``; these are kept as separate intervals with
``is_alternative=True`` and are never merged into the primary dating.
"""

from __future__ import annotations

from lxml import etree

from oikonomia.schemas.metadata import DateInterval, DatePrecision

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def _parse_iso_year(value: str) -> tuple[int, DatePrecision] | None:
    """Parse an ISO date into ``(signed_year, precision)`` or ``None``."""
    text = value.strip()
    if not text:
        return None
    negative = text.startswith("-")
    body = text[1:] if negative else text
    parts = body.split("-")
    if not parts[0].isdigit():
        return None
    year = int(parts[0]) * (-1 if negative else 1)
    if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
        precision = DatePrecision.DAY
    elif len(parts) == 2 and parts[1].isdigit():
        precision = DatePrecision.MONTH
    else:
        precision = DatePrecision.YEAR
    return year, precision


def _interval_from_origdate(el: etree._Element) -> DateInterval | None:
    """Build a :class:`DateInterval` from one ``<origDate>`` element."""
    xml_id = el.get(XML_ID)
    is_alt = xml_id is not None and "alternative" in xml_id.lower()
    raw = (el.text or "").strip() or None

    when = el.get("when")
    if when:
        parsed = _parse_iso_year(when)
        if parsed is not None:
            year, precision = parsed
            return DateInterval(
                lo=year, hi=year, precision=precision, is_alternative=is_alt,
                xml_id=xml_id, raw=raw,
            )

    nb = el.get("notBefore") or el.get("from")
    na = el.get("notAfter") or el.get("to")
    lo = _parse_iso_year(nb)[0] if nb and _parse_iso_year(nb) else None  # type: ignore[index]
    hi = _parse_iso_year(na)[0] if na and _parse_iso_year(na) else None  # type: ignore[index]
    if lo is not None or hi is not None:
        return DateInterval(
            lo=lo, hi=hi, precision=DatePrecision.RANGE, is_alternative=is_alt,
            xml_id=xml_id, raw=raw,
        )

    if raw is not None:
        # A human-readable date with no machine-readable attributes.
        return DateInterval(precision=DatePrecision.UNKNOWN, is_alternative=is_alt,
                            xml_id=xml_id, raw=raw)
    return None


def parse_dates(tree: etree._ElementTree) -> list[DateInterval]:
    """Return all datings, primary first, alternatives following.

    Ordering: non-alternative datings in document order, then alternatives. This
    guarantees ``HgvMetadata.primary_date`` picks a real primary even when the
    XML lists an alternative first.
    """
    intervals: list[DateInterval] = []
    for el in tree.findall(f".//{{{TEI_NS}}}origDate"):
        di = _interval_from_origdate(el)
        if di is not None:
            intervals.append(di)
    intervals.sort(key=lambda d: d.is_alternative)  # stable: False (primary) first
    return intervals
