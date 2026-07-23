"""Hand-computed fixtures for date bucketing (Phase 9).

The only real hazard is the absent year 0: 100 BC and 100 AD must land in
mirrored centuries with opposite sign, and a 50-year bin must floor monotonically
across the BC/AD line. Every case here pins one of those boundaries.
"""

from __future__ import annotations

from oikonomia.db.dates import century, date_mid, era, half_century_start


def test_date_mid_prefers_interval_then_either_bound() -> None:
    assert date_mid(-124, -124) == -124
    assert date_mid(100, 200) == 150
    assert date_mid(None, 50) == 50
    assert date_mid(50, None) == 50
    assert date_mid(None, None) is None


def test_century_is_signed_and_respects_the_missing_year_zero() -> None:
    assert century(1) == 1 and century(100) == 1  # 1st c. AD
    assert century(101) == 2 and century(124) == 2  # 2nd c. AD
    assert century(-1) == -1 and century(-100) == -1  # 1st c. BC
    assert century(-101) == -2 and century(-124) == -2  # 2nd c. BC
    assert century(0) == -1  # astronomical 0 = 1 BC
    assert century(None) is None


def test_half_century_start_floors_across_the_bc_ad_line() -> None:
    assert half_century_start(-124) == -150  # bin -150..-101
    assert half_century_start(124) == 100  # bin 100..149
    assert half_century_start(-100) == -100
    assert half_century_start(49) == 0
    assert half_century_start(-1) == -50
    assert half_century_start(None) is None


def test_era() -> None:
    assert era(50) == "AD" and era(-50) == "BC" and era(0) == "BC"
    assert era(None) is None
