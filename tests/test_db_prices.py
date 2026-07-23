"""Hand-built fixtures for price cleaning + series aggregation (Phase 9).

Each row is a fact-table record; the tests assert exactly which survive the
cleaning filters (the double-link artifact, bronze denomination, wrong unit,
implausible quantity/price) and that the series reports median + IQR + n with the
minimum-n cutoff.
"""

from __future__ import annotations

import pandas as pd

from oikonomia.db.prices import SPECS, clean_prices, price_series

WHEAT = SPECS["wheat"]


def _row(**over: object) -> dict[str, object]:
    """A clean wheat price row (12 dr/artaba); override fields to break one filter."""
    base: dict[str, object] = {
        "commodity_id": "wheat",
        "system": "silver",
        "unit_id": "artaba",
        "currency_id": "drachma",
        "value_num": 60.0,
        "quantity": 5.0,
        "unit_price_base": 12.0,
        "century": 2.0,
    }
    base.update(over)
    return base


def test_clean_keeps_a_good_observation() -> None:
    df = pd.DataFrame([_row()])
    out = clean_prices(df, WHEAT)
    assert len(out) == 1 and out.iloc[0]["unit_price"] == 12.0


def test_double_link_artifact_dropped() -> None:
    # value_num == quantity: the same numeral read as both price and amount.
    df = pd.DataFrame([_row(value_num=5.0, quantity=5.0)])
    assert clean_prices(df, WHEAT).empty


def test_bronze_denomination_dropped() -> None:
    # chalkous carries the Ptolemaic bronze/silver inflation — not comparable.
    df = pd.DataFrame([_row(currency_id="chalkous")])
    assert clean_prices(df, WHEAT).empty


def test_wrong_unit_dropped() -> None:
    # aroura is a land area, not a grain measure — an over-link.
    df = pd.DataFrame([_row(unit_id="aroura")])
    assert clean_prices(df, WHEAT).empty


def test_implausible_quantity_and_price_dropped() -> None:
    assert clean_prices(pd.DataFrame([_row(quantity=20000.0)]), WHEAT).empty  # account total
    assert clean_prices(pd.DataFrame([_row(unit_price_base=0.1)]), WHEAT).empty  # below floor
    assert clean_prices(pd.DataFrame([_row(unit_price_base=900.0)]), WHEAT).empty  # above ceiling


def test_gold_system_dropped() -> None:
    df = pd.DataFrame([_row(system="gold")])
    assert clean_prices(df, WHEAT).empty


def test_series_reports_median_iqr_n_and_applies_min_n() -> None:
    rows = (
        [_row(unit_price_base=p, value_num=p * 5) for p in (8.0, 10.0, 12.0, 14.0, 16.0)]  # 2c AD, n=5
        + [_row(century=1.0, unit_price_base=2.0, value_num=10.0)]  # 1c AD, n=1 -> dropped by min_n
    )
    ser = price_series(pd.DataFrame(rows), WHEAT, bucket="century", min_n=5)
    assert list(ser["century"]) == [2.0]  # the n=1 bucket is gone
    r = ser.iloc[0]
    assert r["median"] == 12.0 and r["p25"] == 10.0 and r["p75"] == 14.0 and r["n"] == 5


def test_series_empty_when_nothing_clean() -> None:
    df = pd.DataFrame([_row(currency_id="chalkous")])
    assert price_series(df, WHEAT).empty
