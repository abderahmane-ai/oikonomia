"""Parsing of ``<num>`` value attributes into floats.

EpiDoc encodes the interpreted value of a written number in ``@value``. Most are
plain integers ("10", "21"); some are simple fractions ("1/2", "1/4"); a few are
non-numeric or ranged and cannot be interpreted, in which case the value is
``None`` while the raw attribute string is always preserved on the
:class:`~oikonomia.schemas.document.Numeral`.
"""

from __future__ import annotations

import re

_INT = re.compile(r"^-?\d+$")
_FRACTION = re.compile(r"^(-?\d+)\s*/\s*(\d+)$")


def parse_num_value(raw: str | None) -> float | None:
    """Interpret a ``<num @value>`` string as a float, or ``None`` if it can't be.

    Handles integers, simple ``a/b`` fractions (including unicode-free forms
    already normalised by EpiDoc), and decimals. Returns ``None`` for empty,
    ranged, or otherwise non-numeric values rather than guessing.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if _INT.match(text):
        return float(int(text))
    m = _FRACTION.match(text)
    if m:
        denom = int(m.group(2))
        if denom == 0:
            return None
        return int(m.group(1)) / denom
    try:
        return float(text)
    except ValueError:
        return None
