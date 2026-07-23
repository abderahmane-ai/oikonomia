"""Tax findings from the monetary fact table (Phase 9).

Two things the fact table supports cleanly, because a tax fact is just
``amount + CHARGED_UNDER→tax + date`` — no per-unit division to go wrong:

* **the fiscal-regime map** — which named tax is attested in which era. This needs
  only ``tax_id`` and the century, so it is robust to amount noise, and it
  reproduces the textbook fiscal history: the ``laographia`` poll tax is a Roman
  institution (gone by late antiquity), ``prosdiagraphomena`` a Roman surcharge,
  ``demosia`` the dominant Byzantine land-tax term.

* **tax payment amounts** — the drachma value paid, silver system. These are
  *payments*, not tax rates: the poll tax was paid in installments, so a single
  receipt records a partial sum (median ~4 dr) while the full annual capitation
  (~16–40 dr by nome) shows up only in the upper tail. Reported honestly as
  payment medians + IQR, never as "the rate".

Amounts are cleaned like prices: silver, comparable denomination (no bronze
``chalkous``), and an individual-payment cap that drops village/estate account
totals (talent-scale sums).
"""

from __future__ import annotations

import pandas as pd

from oikonomia.db.money import COMPARABLE_SILVER_DENOMS

# A single person's tax payment is small; a larger sum is a collective account
# total (a whole village's poll tax, an estate's land tax), not one assessment.
MAX_INDIVIDUAL_PAYMENT_DR = 500.0

# Fiscal eras of Greco-Roman Egypt, by signed century (no year 0).
ERAS: tuple[tuple[str, int, int], ...] = (
    ("Ptolemaic", -4, 0),  # centuries -4..-1 (BC)
    ("Roman", 1, 4),  # 1c..3c AD
    ("Byzantine+", 4, 9),  # 4c AD onward (incl. early Islamic)
)


def era_of(century: float | None) -> str | None:
    """Fiscal era label for a signed century, or ``None``."""
    if century is None or (isinstance(century, float) and century != century):
        return None
    c = int(century)
    for name, lo, hi in ERAS:
        if lo <= c < hi:
            return name
    return None


def fiscal_regime(df: pd.DataFrame, *, min_total: int = 20) -> pd.DataFrame:
    """Attestation count of each tax by fiscal era (all systems).

    Rows are taxes (``tax_id``), columns the eras, values the number of attested
    tax payments. This is the fiscal-regime map; it uses attestation, not amounts,
    so it is unaffected by denomination or installment noise. Taxes with fewer than
    ``min_total`` total attestations are dropped as too rare to characterize.
    """
    tx = df[df["tax_id"].notna() & df["century"].notna()].copy()
    tx["era"] = tx["century"].map(era_of)
    tx = tx[tx["era"].notna()]
    piv = tx.pivot_table(
        index="tax_id", columns="era", values="tm_id", aggfunc="count", fill_value=0
    )
    order = [e for e, _, _ in ERAS if e in piv.columns]
    piv = piv[order]
    piv["total"] = piv.sum(axis=1)
    return piv[piv["total"] >= min_total].sort_values("total", ascending=False)


def clean_tax_payments(df: pd.DataFrame, tax_id: str) -> pd.DataFrame:
    """Individual silver payments for one tax (comparable denomination, plausible).

    Keeps silver-system amounts in a comparable denomination whose value is a
    plausible individual payment; drops the collective account totals. Returns the
    rows with their ``value_base`` (drachmas) as ``payment``.
    """
    d = df[
        (df["tax_id"] == tax_id)
        & (df["system"] == "silver")
        & df["currency_id"].isin(COMPARABLE_SILVER_DENOMS)
        & df["value_base"].notna()
    ].copy()
    d = d[(d["value_base"] > 0) & (d["value_base"] <= MAX_INDIVIDUAL_PAYMENT_DR)]
    d["payment"] = d["value_base"]
    return d


def payments_by_century(
    df: pd.DataFrame, tax_id: str, *, min_n: int = 5
) -> pd.DataFrame:
    """Median + IQR + n of one tax's silver payments per century.

    Returns ``[century, median, p25, p75, n]``, buckets with ``n < min_n`` dropped.
    """
    clean = clean_tax_payments(df, tax_id)
    clean = clean[clean["century"].notna()]
    if clean.empty:
        return pd.DataFrame(columns=["century", "median", "p25", "p75", "n"])
    g = clean.groupby("century")["payment"]
    out = pd.DataFrame(
        {"median": g.median(), "p25": g.quantile(0.25), "p75": g.quantile(0.75), "n": g.size()}
    ).reset_index()
    return out[out["n"] >= min_n].sort_values("century").reset_index(drop=True)
