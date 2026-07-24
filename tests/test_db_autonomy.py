"""Hand-computed fixtures for the autonomy curve aggregation."""

from __future__ import annotations

import pandas as pd

from oikonomia.db.autonomy import guardian_curve


def _rows(specs: list[tuple[str, str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"gender": g, "guardian": gu, "century": c} for g, gu, c in specs]
    )


def test_counts_and_autonomous_share() -> None:
    df = _rows([
        ("female", "with", 2),
        ("female", "without", 2),
        ("female", "with", 2),
        ("male", "with", 2),       # male → ignored
        ("female", "none", 2),      # no formula → ignored
    ])
    c = guardian_curve(df, "century", min_n=1)
    assert len(c) == 1
    r = c.iloc[0]
    assert r["bucket"] == 2 and r["n_with"] == 2 and r["n_without"] == 1 and r["n"] == 3
    assert abs(r["autonomous_share"] - 1 / 3) < 1e-9


def test_min_n_floor_drops_thin_buckets() -> None:
    df = _rows([("female", "with", 1), ("female", "without", 2), ("female", "with", 2)])
    c = guardian_curve(df, "century", min_n=2)
    assert list(c["bucket"]) == [2]  # century 1 has only 1 woman → dropped


def test_nan_bucket_rows_ignored() -> None:
    df = _rows([
        ("female", "with", None),
        ("female", "without", 2),
        ("female", "with", 2),
    ])
    c = guardian_curve(df, "century", min_n=1)
    assert list(c["bucket"]) == [2]


def test_empty_when_no_guardian_formula() -> None:
    df = _rows([("female", "none", 2), ("male", "with", 2)])
    c = guardian_curve(df, "century", min_n=1)
    assert c.empty
    assert list(c.columns) == ["bucket", "n_with", "n_without", "n", "autonomous_share"]
