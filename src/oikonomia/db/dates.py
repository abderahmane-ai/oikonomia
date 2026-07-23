"""Turn the corpus's numeric date bounds into series-ready time buckets.

The corpus already carries ``date_lo``/``date_hi`` as signed years (negative =
BC, e.g. ``-124`` = 124 BC), parsed from HGV — so dating a document is a lookup,
not an extraction. This module only reduces that interval to the buckets a time
series needs: a midpoint, a signed century, and a 50-year bin.

The subtlety is the missing year zero: history goes 1 BC → 1 AD with no year 0,
so century and bin arithmetic is done on the sign and magnitude separately, never
by naive integer division that would put 100 BC and 100 AD in mirrored-but-wrong
centuries.
"""

from __future__ import annotations


def date_mid(date_lo: float | None, date_hi: float | None) -> float | None:
    """Interval midpoint; falls back to whichever bound exists, else ``None``."""
    if date_lo is not None and date_hi is not None:
        return (date_lo + date_hi) / 2.0
    return date_lo if date_lo is not None else date_hi


def century(year: float | None) -> int | None:
    """Signed century of ``year``: +2 = 2nd c. AD, -2 = 2nd c. BC.

    Uses magnitude so 124 AD and 124 BC both land in "the 2nd century" with
    opposite sign, respecting the absent year 0 (a year in (0,100] is 1st c. AD;
    a year in [-100,0) is 1st c. BC).
    """
    if year is None:
        return None
    y = int(year)
    if y == 0:  # astronomical 0 = 1 BC by convention
        return -1
    if y > 0:
        return (y - 1) // 100 + 1
    return -((-y - 1) // 100 + 1)


def half_century_start(year: float | None) -> int | None:
    """Start year of the 50-year bin containing ``year`` (floor toward −∞).

    ``-124 → -150`` (bin −150…−101), ``124 → 100`` (bin 100…149): a monotone
    numeric key safe to group and sort a series on across the BC/AD line.
    """
    if year is None:
        return None
    import math

    return int(math.floor(year / 50.0) * 50)


def era(year: float | None) -> str | None:
    """"BC" / "AD" label for a signed year (0 treated as 1 BC)."""
    if year is None:
        return None
    return "AD" if year > 0 else "BC"
