"""Hand-built fixtures for the database packaging (document index + manifest)."""

from __future__ import annotations

import pandas as pd

from oikonomia.db.export import TableSpec, build_manifest, document_index

DOCS = pd.DataFrame([
    {"stem": "s1", "tm_id": "t1", "century": 2, "place_pleiades": 100, "deal_type": "sale"},
    {"stem": "s2", "tm_id": "t2", "century": 3, "place_pleiades": 200, "deal_type": "receipt"},
])
PERSONS = pd.DataFrame([
    {"stem": "s1", "gender": "female"},
    {"stem": "s1", "gender": "male"},
    {"stem": "s2", "gender": "female"},
])
PRINCIPALS = pd.DataFrame([
    {"stem": "s1", "gender": "female", "guardian": "with"},
])
MONETARY = pd.DataFrame([
    {"tm_id": "t1"}, {"tm_id": "t1"},  # two money facts in t1
])
PRICES = pd.DataFrame([{"tm_id": "t1"}])
TAXES = pd.DataFrame([{"tm_id": "t2"}])


def _row(idx: pd.DataFrame, stem: str) -> pd.Series:
    return idx[idx["stem"] == stem].iloc[0]


def test_document_index_folds_person_and_principal_counts_by_stem() -> None:
    idx = document_index(DOCS, PERSONS, PRINCIPALS, MONETARY, PRICES, TAXES)
    s1 = _row(idx, "s1")
    assert s1["n_persons"] == 2 and s1["n_women_mentions"] == 1 and s1["n_men_mentions"] == 1
    assert s1["n_principals"] == 1 and s1["n_women_principals"] == 1
    assert bool(s1["has_guardian_woman"]) is True


def test_document_index_folds_money_price_tax_by_tmid() -> None:
    idx = document_index(DOCS, PERSONS, PRINCIPALS, MONETARY, PRICES, TAXES)
    s1, s2 = _row(idx, "s1"), _row(idx, "s2")
    assert s1["n_money_facts"] == 2 and bool(s1["has_price"]) is True and bool(s1["has_tax"]) is False
    assert s2["n_money_facts"] == 0 and bool(s2["has_price"]) is False and bool(s2["has_tax"]) is True


def test_document_index_zero_fills_docs_with_no_joins() -> None:
    s2 = _row(document_index(DOCS, PERSONS, PRINCIPALS, MONETARY, PRICES, TAXES), "s2")
    assert s2["n_principals"] == 0 and s2["n_women_principals"] == 0
    assert bool(s2["has_guardian_woman"]) is False
    assert s2["n_persons"] == 1 and s2["n_women_mentions"] == 1


def test_document_index_survives_empty_finding_tables() -> None:
    empty = pd.DataFrame()
    idx = document_index(DOCS, empty, empty, empty, empty, empty)
    assert len(idx) == 2  # every document survives
    assert idx["n_persons"].tolist() == [0, 0]
    assert idx["has_price"].tolist() == [False, False]


def test_build_manifest_inventories_tables_with_provenance() -> None:
    m = build_manifest(
        [
            (TableSpec("principals", "one principal mention", "stem+span", "PARTY_OF heads, gendered"), PRINCIPALS),
            (TableSpec("documents", "one document", "stem", "the per-doc spine"), DOCS),
        ],
        corpus_rev="d7a34f30",
    )
    assert m["corpus_rev"] == "d7a34f30" and m["licence"] == "CC BY 3.0"
    assert m["generated_at"].endswith("Z")
    names = {t["name"]: t for t in m["tables"]}  # type: ignore[index,union-attr]
    assert names["principals"]["rows"] == 1
    assert names["documents"]["rows"] == 2 and "deal_type" in names["documents"]["columns"]
