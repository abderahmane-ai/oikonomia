"""The autonomy curve — women transacting with vs without a guardian, by bucket.

The headline of the women finding. Among the women who carry a guardian formula
(:mod:`oikonomia.db.personscan`), what share transact **without** one (χωρὶς
κυρίου — acting in their own legal right, the ius liberorum) rather than **with**
one (μετὰ κυρίου)? Broken across a bucket — a century or a region — it traces
whether and where women's independent legal capacity widened.

Pure pandas over the person table: one function, grouped counts and the
autonomous share, with a minimum-n floor so a bucket of two people is not read as
a trend. The ``bucket`` column is caller-supplied (``century``, or a ``region``
the CLI derives from the Pleiades place), so the same logic serves both cuts.
"""

from __future__ import annotations

import pandas as pd

FEMALE = "female"
WITH = "with"
WITHOUT = "without"


def guardian_curve(df: pd.DataFrame, bucket: str, min_n: int = 8) -> pd.DataFrame:
    """Per-bucket with/without-guardian counts and the autonomous (without) share.

    Restricts to female rows carrying a guardian formula (``with``/``without``),
    drops rows with no ``bucket`` value, groups, and keeps buckets with at least
    ``min_n`` such women. Columns out: ``bucket``, ``n_with``, ``n_without``,
    ``n``, ``autonomous_share`` (= ``n_without / n``), sorted by bucket.
    """
    fem = df[(df["gender"] == FEMALE) & (df["guardian"].isin([WITH, WITHOUT]))]
    fem = fem[fem[bucket].notna()]
    rows: list[dict[str, object]] = []
    for key, grp in fem.groupby(bucket):
        n_with = int((grp["guardian"] == WITH).sum())
        n_without = int((grp["guardian"] == WITHOUT).sum())
        n = n_with + n_without
        if n < min_n:
            continue
        rows.append({
            "bucket": key,
            "n_with": n_with,
            "n_without": n_without,
            "n": n,
            "autonomous_share": n_without / n,
        })
    out = pd.DataFrame(rows, columns=["bucket", "n_with", "n_without", "n", "autonomous_share"])
    return out.sort_values("bucket").reset_index(drop=True)
