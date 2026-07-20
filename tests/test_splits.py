"""Tests for near-duplicate clustering and split assignment.

The properties that matter here are not "does it run" but "can it leak" and
"can it silently unbalance". Both failures are invisible in the totals — the
corpus-level 80/10/10 comes out exact even when every stratum is wrong — so
they are asserted directly.
"""

from __future__ import annotations

import pytest

from oikonomia.splits.assign import (
    DEFAULT_FRACTIONS,
    DocRecord,
    assign_chronological,
    assign_random,
    build_groups,
    parse_genres,
    report_split,
)
from oikonomia.splits.dedup import cluster_duplicates, shingles

BASE = (
    "πυροῦ ἀρτάβας τεσσαράκοντα ἐν τῷ ιϛ ἔτει διὰ Ἡλιοδώρου ἀγορανόμου καὶ τῶν ἄλλων"
)
UNACCENTED = (
    "πυρου αρταβας τεσσαρακοντα εν τω ιϛ ετει δια Ηλιοδωρου αγορανομου και των αλλων"
)
OTHER = (
    "οἴνου κεράμια τέσσαρα καὶ ἐλαίου ξέσται δύο παρὰ Σαραπίωνος τοῦ Διονυσίου πράκτορος"
)


# --------------------------------------------------------------------------
# Deduplication
# --------------------------------------------------------------------------


def test_exact_and_accent_variants_cluster_together() -> None:
    """Folding is the point: diacritics must not hide a republication."""
    result = cluster_duplicates(["a", "b", "c"], [BASE, BASE, UNACCENTED])
    assert result.n_clusters == 1
    assert result.clusters[0].members == ["a", "b", "c"]


def test_unrelated_documents_stay_apart() -> None:
    result = cluster_duplicates(["a", "b"], [BASE, OTHER])
    assert result.n_clusters == 2
    assert result.clusters == []
    assert result.n_duplicated_docs == 0


def test_clustering_is_deterministic_across_calls() -> None:
    """Splits are only reproducible if clustering is."""
    ids, texts = ["a", "b", "c"], [BASE, UNACCENTED, OTHER]
    assert cluster_duplicates(ids, texts).cluster_of == cluster_duplicates(ids, texts).cluster_of


def test_clustering_is_independent_of_input_order() -> None:
    """Cluster membership must not depend on how documents were enumerated."""
    forward = cluster_duplicates(["a", "b", "c"], [BASE, UNACCENTED, OTHER])
    reverse = cluster_duplicates(["c", "b", "a"], [OTHER, UNACCENTED, BASE])
    assert forward.cluster_of == reverse.cluster_of


def test_shingles_are_stable_across_processes() -> None:
    """Regression: the builtin hash() is per-process randomised (PYTHONHASHSEED).

    Using it here would silently produce different clusters on every run.
    """
    import subprocess
    import sys

    code = "from oikonomia.splits.dedup import shingles; print(sorted(shingles('αρταβασ'))[:3])"
    runs = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        ).stdout
        for _ in range(2)
    }
    assert len(runs) == 1


def test_empty_and_short_text() -> None:
    assert shingles("") == set()
    assert len(shingles("αβ")) == 1  # shorter than the shingle size
    result = cluster_duplicates(["a", "b"], ["", ""])
    assert result.n_docs == 2


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError, match="same length"):
        cluster_duplicates(["a", "b"], [BASE])


# --------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------


def _rec(doc_id: str, tm: int, genre: str = "receipt", date: float | None = 150.0):
    return DocRecord(doc_id=doc_id, tm_id=tm, genre=genre, date_mid=date)


def test_shared_tm_id_forms_one_group() -> None:
    """1,706 real documents share a TM id — the same papyrus, edited twice."""
    records = [_rec("a", 1), _rec("b", 1), _rec("c", 2)]
    groups = build_groups(records)
    assert groups["a"] == groups["b"] != groups["c"]


def test_duplicate_clusters_merge_into_groups() -> None:
    records = [_rec("a", 1), _rec("b", 2), _rec("c", 3)]
    groups = build_groups(records, {"a": "a", "b": "a", "c": "c"})
    assert groups["a"] == groups["b"] != groups["c"]


def test_grouping_is_transitive_across_both_signals() -> None:
    """A shares a TM id with B; B is a near-duplicate of C: all three move together."""
    records = [_rec("a", 1), _rec("b", 1), _rec("c", 9)]
    groups = build_groups(records, {"b": "b", "c": "b", "a": "a"})
    assert groups["a"] == groups["b"] == groups["c"]


# --------------------------------------------------------------------------
# Assignment
# --------------------------------------------------------------------------


def _corpus(n_per_stratum: int = 100) -> list[DocRecord]:
    records = []
    for genre in ("receipt", "account", "nogenre"):
        for date, _bucket in ((150.0, "high_roman"), (450.0, "byzantine")):
            for i in range(n_per_stratum):
                records.append(_rec(f"{genre}-{date}-{i}", tm=hash((genre, date, i)) % 10**9,
                                    genre=genre, date=date))
    for r in records:
        r.group_id = r.doc_id
    return records


def test_random_split_hits_target_proportions() -> None:
    records = _corpus()
    assignment = assign_random(records, seed=1)
    report = report_split(records, assignment, regime="random", seed=1)
    for name, target in DEFAULT_FRACTIONS.items():
        assert report.counts[name].fraction == pytest.approx(target, abs=0.02)


def test_random_split_stratifies_within_every_stratum() -> None:
    """The bug this catches: balancing on a *global* deficit fills train with
    whole strata and only divides the ones processed last. The corpus-level
    80/10/10 is exact either way, so only a per-stratum check sees it."""
    records = _corpus()
    assignment = assign_random(records, seed=1)

    by_stratum: dict[str, dict[str, int]] = {}
    for r in records:
        by_stratum.setdefault(r.stratum, {}).setdefault(assignment[r.doc_id], 0)
        by_stratum[r.stratum][assignment[r.doc_id]] += 1

    for stratum, counts in by_stratum.items():
        n = sum(counts.values())
        for name, target in DEFAULT_FRACTIONS.items():
            assert counts.get(name, 0) / n == pytest.approx(target, abs=0.05), stratum


def test_no_group_straddles_two_splits() -> None:
    """The leakage property, asserted directly on a corpus of large groups."""
    records = []
    for g in range(60):
        for i in range(5):  # five documents per group
            r = _rec(f"g{g}-d{i}", tm=g)
            r.group_id = f"g{g}"
            records.append(r)
    assignment = assign_random(records, seed=3)
    report = report_split(records, assignment, regime="random", seed=3)
    assert report.leaked_groups == []
    assert report.ok


def test_random_split_is_deterministic_for_a_seed() -> None:
    records = _corpus(30)
    assert assign_random(records, seed=5) == assign_random(records, seed=5)


def test_random_split_ignores_input_order() -> None:
    """Reordering the corpus must not change any document's split."""
    records = _corpus(30)
    shuffled = list(reversed(records))
    assert assign_random(records, seed=5) == assign_random(shuffled, seed=5)


def test_different_seeds_give_different_splits() -> None:
    records = _corpus(30)
    assert assign_random(records, seed=1) != assign_random(records, seed=2)


def test_chronological_split_orders_by_date() -> None:
    """Train must be early, test must be late."""
    records = []
    for year in range(100, 1100, 10):
        r = _rec(f"y{year}", tm=year, date=float(year))
        r.group_id = r.doc_id
        records.append(r)
    assignment = assign_chronological(records)

    train = [r.date_mid for r in records if assignment[r.doc_id] == "train"]
    test = [r.date_mid for r in records if assignment[r.doc_id] == "test"]
    assert max(train) < min(test)


def test_chronological_puts_undated_in_train() -> None:
    """Undated documents cannot support a temporal-generalisation claim."""
    records = []
    for year in range(100, 600, 10):
        r = _rec(f"y{year}", tm=year, date=float(year))
        r.group_id = r.doc_id
        records.append(r)
    for i in range(20):
        r = _rec(f"u{i}", tm=9000 + i, date=None)
        r.group_id = r.doc_id
        records.append(r)

    assignment = assign_chronological(records)
    assert all(assignment[f"u{i}"] == "train" for i in range(20))


def test_report_detects_a_leaking_assignment() -> None:
    """The check must fail on a bad split, not just pass on a good one."""
    records = [_rec("a", 1), _rec("b", 1)]
    for r in records:
        r.group_id = "shared"
    bad = {"a": "train", "b": "test"}
    report = report_split(records, bad, regime="random", seed=0)
    assert report.leaked_groups == ["shared"]
    assert not report.ok


def test_temporal_overlap_is_reported() -> None:
    """Grouping can drag a late document into train; that must be visible."""
    records = []
    for year in (100.0, 900.0):  # one group, dates 800 years apart
        r = _rec(f"pair-{year}", tm=1, date=year)
        r.group_id = "pair"
        records.append(r)
    for year in range(200, 800, 50):
        r = _rec(f"y{year}", tm=year, date=float(year))
        r.group_id = r.doc_id
        records.append(r)

    assignment = assign_chronological(records)
    report = report_split(records, assignment, regime="chronological", seed=0)
    assert report.n_train_after_test_start >= 1
    assert report.temporal_overlap_rate > 0


# --------------------------------------------------------------------------
# Stratum parsing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["receipt"]', "receipt"),
        ('["contract","sale"]', "contract"),  # first genre wins
        ("[]", "nogenre"),
        (None, "nogenre"),
        ("not json", "nogenre"),
    ],
)
def test_parse_genres(raw: str | None, expected: str) -> None:
    assert parse_genres(raw) == expected


def test_undated_is_its_own_stratum() -> None:
    assert _rec("a", 1, date=None).date_bucket == "undated"
    assert _rec("b", 2, date=150.0).date_bucket == "high_roman"
    assert _rec("c", 3, date=-100.0).date_bucket == "ptolemaic"
