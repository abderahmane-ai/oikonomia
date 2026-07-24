"""Package the derived tables into a documented, queryable database (deliverable #2).

Phase 9 produced a handful of parquet tables — monetary facts, prices, taxes,
persons, the autonomy curve, principals — each keyed to a document and a character
span. This module turns those *artifacts* into a *database*: a per-document index
(the spine everything hangs off) and a machine-readable manifest (the inventory +
provenance), so a reader can query "which 3c-AD sale documents have a female
principal?" and trace every answer back to a span in a pinned corpus revision.

Two pure builders, unit-testable on small frames:

* :func:`document_index` — one row per document (keyed on the unique ``stem``),
  carrying the corpus metadata plus per-document counts folded in from the person,
  principal, money, price and tax tables. Money/price/tax fold in by ``tm_id``
  (not ``stem``), which repeats across the ~1,700 documents that share a TM id —
  a boolean/`count` there is shared by those siblings, noted in the data
  dictionary.
* :func:`build_manifest` — the table inventory: grain, key, row count and a
  one-line description per shipped table, plus the corpus revision, licence and a
  generation timestamp.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple

import pandas as pd


class TableSpec(NamedTuple):
    """One shipped table's inventory entry for the manifest."""

    name: str
    grain: str  # what one row is
    key: str  # the join key(s)
    description: str


def _by(df: pd.DataFrame, key: str) -> pd.core.groupby.DataFrameGroupBy:
    return df.groupby(key)


def document_index(
    docs: pd.DataFrame,
    persons: pd.DataFrame,
    principals: pd.DataFrame,
    monetary: pd.DataFrame,
    prices: pd.DataFrame,
    taxes: pd.DataFrame,
) -> pd.DataFrame:
    """One row per document, enriched with per-document counts from every table.

    ``docs`` is the document universe: columns ``stem, tm_id, century,
    place_pleiades, deal_type`` (one row per document). The person and principal
    counts fold in by ``stem`` (unique); the money-fact count and the price/tax
    flags fold in by ``tm_id``. Missing joins become 0 / False, so every document
    in ``docs`` survives.
    """
    out = docs.copy()

    if not persons.empty:
        p = persons.assign(
            _w=(persons["gender"] == "female").astype(int),
            _m=(persons["gender"] == "male").astype(int),
        )
        agg = p.groupby("stem").agg(
            n_persons=("gender", "size"),
            n_women_mentions=("_w", "sum"),
            n_men_mentions=("_m", "sum"),
        ).reset_index()
        out = out.merge(agg, on="stem", how="left")

    if not principals.empty:
        pr = principals.assign(
            _w=(principals["gender"] == "female").astype(int),
            _gw=((principals["gender"] == "female") & principals["guardian"].isin(["with", "without"])),
        )
        agg = pr.groupby("stem").agg(
            n_principals=("gender", "size"),
            n_women_principals=("_w", "sum"),
            has_guardian_woman=("_gw", "any"),
        ).reset_index()
        out = out.merge(agg, on="stem", how="left")

    if not monetary.empty and "tm_id" in monetary.columns:
        out = out.merge(
            pd.DataFrame({"n_money_facts": _by(monetary, "tm_id").size()}).reset_index(),
            on="tm_id", how="left",
        )
    price_tms = set(prices["tm_id"].astype(str)) if ("tm_id" in prices.columns and not prices.empty) else set()
    tax_tms = set(taxes["tm_id"].astype(str)) if ("tm_id" in taxes.columns and not taxes.empty) else set()
    out["has_price"] = out["tm_id"].astype(str).isin(price_tms)
    out["has_tax"] = out["tm_id"].astype(str).isin(tax_tms)

    count_cols = [
        "n_persons", "n_women_mentions", "n_men_mentions",
        "n_principals", "n_women_principals", "n_money_facts",
    ]
    for c in count_cols:
        if c in out.columns:
            out[c] = out[c].fillna(0).astype(int)
        else:
            out[c] = 0
    if "has_guardian_woman" not in out.columns:
        out["has_guardian_woman"] = False
    out["has_guardian_woman"] = out["has_guardian_woman"].fillna(False).astype(bool)
    return out


def build_manifest(
    tables: list[tuple[TableSpec, pd.DataFrame]],
    *,
    corpus_rev: str,
    schema_version: str = "1.0",
    licence: str = "CC BY 3.0",
) -> dict[str, object]:
    """The database inventory + provenance, as a JSON-serializable dict.

    One entry per shipped table (grain, key, row count, columns, description),
    plus the pinned corpus revision every span traces to, the licence and a UTC
    generation timestamp — so the export is self-describing and reproducible.
    """
    return {
        "schema_version": schema_version,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus_rev": corpus_rev,
        "licence": licence,
        "provenance": "every row traces to (tm_id/stem, char-span) in corpus.parquet at corpus_rev",
        "tables": [
            {
                "name": spec.name,
                "grain": spec.grain,
                "key": spec.key,
                "rows": len(df),
                "columns": list(df.columns),
                "description": spec.description,
            }
            for spec, df in tables
        ],
    }
