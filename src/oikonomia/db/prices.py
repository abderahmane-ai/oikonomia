"""Clean, robust commodity price series from the monetary fact table (Phase 9).

The raw fact table over-links: a commodity gets joined to any nearby numeral, so a
naive ``value / quantity`` is dominated by artifacts. Two, measured on wheat,
account for almost all the noise and are filtered here:

* **the double-link** — 48% of priced wheat rows have ``value_num == quantity``:
  the *same* numeral was read as both the price and the amount, forcing the ratio
  to ~1.0 (the "1 dr/artaba everywhere" artifact). Dropped.
* **the wrong unit** — a commodity linked to a land area (``aroura``) or an
  account total (quantities in the tens of thousands). Requiring the commodity's
  *own* dry/liquid measure and a plausible quantity removes these.

On top of that, only the **silver denominations** are kept: the Ptolemaic bronze
``chalkous`` carries the era's runaway bronze-to-silver inflation, which is not a
commodity price signal and is not comparable across the drachma standard.

What survives is a small, high-precision subset — precision over recall, because
this feeds a *published* number. On wheat it reproduces the literature: Ptolemaic
~2 dr/artaba, the Roman 2c AD peak ~10–13 (lit. ~7–12). Estimates are reported as
median + interquartile range + n per time bucket, never a bare mean over noise.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Silver-standard denominations (drachma system). The bronze chalkous is excluded
# on purpose — see the module docstring.
SILVER_DENOMS: frozenset[str] = frozenset(
    {"drachma", "obol", "diobol", "triobol", "tetrobol", "pentobol", "hemiobelion"}
)


@dataclass(frozen=True)
class PriceSpec:
    """A commodity priced in its own measure, with a plausibility band (dr/unit)."""

    commodity: str
    unit: str
    price_lo: float
    price_hi: float
    qty_hi: float = 10000.0  # a larger linked quantity is an account total, not a sale


# The staples worth a series. Grains (artaba) are the flagship — best populated and
# directly comparable to the published grain-price literature. Wine/oil use liquid
# measures and are thinner; kept for exploration, not the headline claim.
SPECS: dict[str, PriceSpec] = {
    "wheat": PriceSpec("wheat", "artaba", 0.5, 500.0),
    "barley": PriceSpec("barley", "artaba", 0.5, 500.0),
    "wine": PriceSpec("wine", "keramion", 1.0, 2000.0),
    "oil": PriceSpec("oil", "metretes", 1.0, 5000.0),
}


def clean_prices(df: pd.DataFrame, spec: PriceSpec) -> pd.DataFrame:
    """The high-precision priced-observation subset for one commodity.

    Adds a ``unit_price`` column (drachmas per unit) and returns only the rows that
    survive every filter — silver system + denomination, the commodity's own unit,
    a real (non-double-linked) quantity, and plausible quantity and price.
    """
    d = df[
        (df["commodity_id"] == spec.commodity)
        & (df["system"] == "silver")
        & (df["unit_id"] == spec.unit)
        & df["currency_id"].isin(SILVER_DENOMS)
        & df["unit_price_base"].notna()
        & df["quantity"].notna()
        & df["value_num"].notna()
    ].copy()
    # Drop the double-link artifact: the same numeral read as price and quantity.
    d = d[d["value_num"] != d["quantity"]]
    d = d[(d["quantity"] >= 0.5) & (d["quantity"] <= spec.qty_hi)]
    d["unit_price"] = d["unit_price_base"]
    d = d[(d["unit_price"] >= spec.price_lo) & (d["unit_price"] <= spec.price_hi)]
    return d


def price_series(
    df: pd.DataFrame, spec: PriceSpec, *, bucket: str = "century", min_n: int = 5
) -> pd.DataFrame:
    """Median + IQR + n per time bucket, over the cleaned observations.

    ``bucket`` is a fact-table column (``century`` or ``bin50``). Buckets with
    fewer than ``min_n`` observations are dropped — a median over 2 points is not a
    price. Returns columns ``[bucket, median, p25, p75, n]``, sorted by time.
    """
    clean = clean_prices(df, spec)
    clean = clean[clean[bucket].notna()]
    if clean.empty:
        return pd.DataFrame(columns=[bucket, "median", "p25", "p75", "n"])
    g = clean.groupby(bucket)["unit_price"]
    out = pd.DataFrame(
        {
            "median": g.median(),
            "p25": g.quantile(0.25),
            "p75": g.quantile(0.75),
            "n": g.size(),
        }
    ).reset_index()
    return out[out["n"] >= min_n].sort_values(bucket).reset_index(drop=True)
