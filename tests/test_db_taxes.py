"""Hand-built fixtures for the tax findings (Phase 9).

Covers the fiscal-era mapping, the attestation pivot (fiscal-regime map), and the
payment cleaning (silver + comparable denomination + individual-payment cap) with
its per-century median/IQR/min-n aggregation.
"""

from __future__ import annotations

import pandas as pd

from oikonomia.db.taxes import (
    clean_tax_payments,
    era_of,
    fiscal_regime,
    payments_by_century,
)


def _tax(**over: object) -> dict[str, object]:
    """A clean silver laographia payment; override to break a filter."""
    base: dict[str, object] = {
        "tax_id": "laographia",
        "system": "silver",
        "currency_id": "drachma",
        "value_base": 4.0,
        "century": 2.0,
        "tm_id": "1",
        "place_pleiades": 100.0,
    }
    base.update(over)
    return base


def test_era_of_maps_signed_centuries() -> None:
    assert era_of(-2) == "Ptolemaic"  # 2c BC
    assert era_of(1) == "Roman" and era_of(3) == "Roman"
    assert era_of(4) == "Byzantine+" and era_of(8) == "Byzantine+"
    assert era_of(None) is None


def test_fiscal_regime_pivots_attestation_by_era() -> None:
    rows = (
        [_tax(tax_id="laographia", century=2.0) for _ in range(25)]  # Roman poll tax
        + [_tax(tax_id="demosia", century=6.0) for _ in range(25)]  # Byzantine land tax
        + [_tax(tax_id="rare", century=2.0) for _ in range(3)]  # below min_total → dropped
    )
    reg = fiscal_regime(pd.DataFrame(rows), min_total=20)
    assert set(reg.index) == {"laographia", "demosia"}  # 'rare' dropped
    assert reg.loc["laographia", "Roman"] == 25
    assert reg.loc["demosia", "Byzantine+"] == 25
    assert reg.loc["laographia", "total"] == 25


def test_clean_tax_payments_filters() -> None:
    rows = [
        _tax(),  # kept
        _tax(currency_id="chalkous"),  # bronze → dropped
        _tax(system="gold"),  # gold → dropped
        _tax(value_base=5000.0),  # collective account total → dropped
        _tax(value_base=0.0),  # zero → dropped
    ]
    out = clean_tax_payments(pd.DataFrame(rows), "laographia")
    assert len(out) == 1 and out.iloc[0]["payment"] == 4.0


def test_payments_by_century_median_iqr_and_min_n() -> None:
    rows = (
        [_tax(value_base=v) for v in (2.0, 4.0, 6.0, 8.0, 10.0)]  # 2c AD, n=5
        + [_tax(century=1.0, value_base=4.0)]  # 1c AD, n=1 → dropped
    )
    ser = payments_by_century(pd.DataFrame(rows), "laographia", min_n=5)
    assert list(ser["century"]) == [2.0]
    r = ser.iloc[0]
    assert r["median"] == 6.0 and r["p25"] == 4.0 and r["p75"] == 8.0 and r["n"] == 5
