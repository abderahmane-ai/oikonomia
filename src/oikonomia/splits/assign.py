"""Assign documents to train/dev/test, without leaking and without lying.

Two regimes, both produced, because they answer different questions and the
gap between them is itself a result:

**random** — the headline split. Groups are kept intact and strata are
preserved, so it measures how well the model reads papyri of the kind it was
trained on.

**chronological** — train on early documents, test on late ones. This is the
honest test of the project's actual claim: price and wage series *across a
millennium*. The literature is consistent that random splits overestimate
performance relative to chronological ones, sometimes by double-digit points,
because they let the model train and test on the same period. A model that
cannot read a century it never saw leaves a hole in the series, and a random
split will never reveal it.

Report both. If they agree, the model generalises across time; if they
diverge, that gap is the finding, and the honest headline is the lower number.

**Grouping.** A "group" is the unit that moves atomically between splits. Two
signals define it, unioned:

1. shared TM id — 618 documents in the working set share one with another, i.e.
   they are the same papyrus edited or republished separately;
2. near-duplicate cluster (see :mod:`oikonomia.splits.dedup`).

Publication volume is deliberately *not* a grouping signal. It would be
correct in spirit — fragments of one roll appear in one volume — but the
largest volume here holds 2,023 documents, and grouping at that granularity
would force whole volumes into one split and make stratification impossible.
Group by the evidence of actual textual identity instead.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence

from pydantic import BaseModel, Field

TRAIN, DEV, TEST = "train", "dev", "test"
SPLIT_NAMES = (TRAIN, DEV, TEST)
DEFAULT_FRACTIONS = {TRAIN: 0.8, DEV: 0.1, TEST: 0.1}

# Date buckets for stratification, in years (astronomical: BCE negative).
# Chosen to follow the corpus's actual mass rather than round centuries: the
# 2nd century CE alone holds 23% of dated documents.
DATE_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("ptolemaic", -400, -30),  # to the Roman annexation of Egypt
    ("early_roman", -30, 100),
    ("high_roman", 100, 200),
    ("late_roman", 200, 300),
    ("diocletianic", 300, 400),
    ("byzantine", 400, 600),
    ("arab", 600, 900),
)
UNDATED = "undated"
NO_GENRE = "nogenre"


class DocRecord(BaseModel):
    """One document's split-relevant facts."""

    doc_id: str
    tm_id: int
    group_id: str = ""
    genre: str = NO_GENRE
    date_mid: float | None = None

    @property
    def date_bucket(self) -> str:
        if self.date_mid is None:
            return UNDATED
        for name, lo, hi in DATE_BUCKETS:
            if lo <= self.date_mid < hi:
                return name
        return UNDATED

    @property
    def stratum(self) -> str:
        return f"{self.genre}|{self.date_bucket}"


class SplitCounts(BaseModel):
    n_docs: int
    n_groups: int
    fraction: float


class SplitReport(BaseModel):
    """What a split actually looks like, so it can be checked rather than trusted."""

    regime: str
    seed: int
    counts: dict[str, SplitCounts]
    n_docs: int
    n_groups: int
    n_strata: int
    # Largest absolute deviation between a stratum's share of a split and its
    # share of the whole corpus. Sensitive to tiny strata, which cannot be
    # divided 80/10/10 at all, so read it alongside the TV distance below.
    max_stratum_drift: float
    # Total-variation distance between each split's stratum distribution and
    # the corpus's. 0 = identical; size-weighted, so it is not dominated by
    # strata holding three documents.
    stratum_tv_distance: dict[str, float] = Field(default_factory=dict)
    date_range_by_split: dict[str, list[float | None]]
    # Dated train documents falling at or after the test set's earliest date.
    # Only meaningful for the chronological regime, where it is the residual
    # contamination: grouping keeps a group atomic, so a group whose members
    # are dated centuries apart drags early and late documents together. Small
    # is fine; it must be reported rather than assumed away.
    n_train_after_test_start: int = 0
    temporal_overlap_rate: float = 0.0
    leaked_groups: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.leaked_groups


class _UnionFind:
    __slots__ = ("_parent",)

    def __init__(self, keys: Sequence[str]) -> None:
        self._parent: dict[str, str] = {k: k for k in keys}

    def find(self, k: str) -> str:
        parent = self._parent
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Union by name keeps group ids deterministic regardless of the
            # order pairs arrive in.
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            self._parent[hi] = lo


def build_groups(
    records: Sequence[DocRecord], dup_cluster_of: dict[str, str] | None = None
) -> dict[str, str]:
    """Union TM-id identity and near-duplicate clusters into atomic groups."""
    uf = _UnionFind([r.doc_id for r in records])

    by_tm: dict[int, list[str]] = {}
    for r in records:
        by_tm.setdefault(r.tm_id, []).append(r.doc_id)
    for members in by_tm.values():
        for other in members[1:]:
            uf.union(members[0], other)

    if dup_cluster_of:
        by_cluster: dict[str, list[str]] = {}
        for doc_id, cid in dup_cluster_of.items():
            by_cluster.setdefault(cid, []).append(doc_id)
        for members in by_cluster.values():
            anchor = members[0]
            for other in members[1:]:
                uf.union(anchor, other)

    return {r.doc_id: uf.find(r.doc_id) for r in records}


def _group_strata(records: Sequence[DocRecord]) -> dict[str, str]:
    """One stratum per group — the most common among its documents.

    A group must land in exactly one split, so it needs a single stratum even
    when its members disagree (a republished text can be catalogued under two
    genres). Ties break on the stratum name so the choice is deterministic.
    """
    counts: dict[str, dict[str, int]] = {}
    for r in records:
        counts.setdefault(r.group_id, {}).setdefault(r.stratum, 0)
        counts[r.group_id][r.stratum] += 1
    return {
        gid: max(sorted(strata), key=lambda s: strata[s]) for gid, strata in counts.items()
    }


def assign_random(
    records: Sequence[DocRecord],
    fractions: dict[str, float] | None = None,
    *,
    seed: int = 17,
) -> dict[str, str]:
    """Group-aware stratified assignment. Returns doc_id -> split name.

    Within each stratum, groups are shuffled and then handed to whichever split
    is furthest below its target *document* count. Balancing on documents
    rather than groups matters here because group sizes are wildly uneven — a
    single duplicate cluster can hold dozens of documents, and balancing group
    counts would leave the splits lopsided in the thing that actually matters.
    """
    fractions = fractions or DEFAULT_FRACTIONS
    strata = _group_strata(records)

    sizes: dict[str, int] = {}
    for r in records:
        sizes[r.group_id] = sizes.get(r.group_id, 0) + 1

    by_stratum: dict[str, list[str]] = {}
    for gid, stratum in strata.items():
        by_stratum.setdefault(stratum, []).append(gid)

    group_split: dict[str, str] = {}
    active = [name for name in SPLIT_NAMES if fractions.get(name, 0.0) > 0]
    rng = random.Random(seed)

    # Balance *within* each stratum, not globally. Balancing on a global
    # deficit is the subtle failure here: train's deficit is the largest until
    # it is nearly full, so whole strata land in train and only the strata
    # processed last get divided. The corpus-level 80/10/10 comes out exact
    # either way, which is what makes the bug invisible from the totals.
    for stratum in sorted(by_stratum):
        groups = sorted(by_stratum[stratum])  # sort first: input order must not matter
        rng.shuffle(groups)
        # Largest groups first, so the big indivisible clusters are placed while
        # there is still room to balance around them.
        groups.sort(key=lambda g: -sizes[g])

        stratum_docs = sum(sizes[g] for g in groups)
        targets = {name: fractions.get(name, 0.0) * stratum_docs for name in active}
        assigned: dict[str, int] = dict.fromkeys(active, 0)

        for gid in groups:
            deficit = {name: targets[name] - assigned[name] for name in active}
            choice = max(sorted(deficit), key=lambda n: deficit[n])
            group_split[gid] = choice
            assigned[choice] += sizes[gid]

    return {r.doc_id: group_split[r.group_id] for r in records}


def assign_chronological(
    records: Sequence[DocRecord],
    fractions: dict[str, float] | None = None,
) -> dict[str, str]:
    """Train on the earliest documents, test on the latest.

    Groups are ordered by their median date and cut at cumulative-document
    quantiles, so the split boundaries fall where the corpus's mass actually
    is rather than at round dates.

    **Undated groups go to train.** They cannot support a claim about temporal
    generalisation — there is no date to generalise across — and putting them
    in test would quietly dilute exactly the measurement this regime exists to
    make. It costs recall on the test set and buys interpretability.
    """
    fractions = fractions or DEFAULT_FRACTIONS

    dates: dict[str, list[float]] = {}
    sizes: dict[str, int] = {}
    for r in records:
        sizes[r.group_id] = sizes.get(r.group_id, 0) + 1
        if r.date_mid is not None:
            dates.setdefault(r.group_id, []).append(r.date_mid)

    def median(values: list[float]) -> float:
        s = sorted(values)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    dated = sorted(
        ((gid, median(v)) for gid, v in dates.items()), key=lambda kv: (kv[1], kv[0])
    )
    undated = sorted(set(sizes) - set(dates))

    group_split: dict[str, str] = dict.fromkeys(undated, TRAIN)
    n_dated_docs = sum(sizes[g] for g, _ in dated)
    train_cut = fractions.get(TRAIN, 0.8) * n_dated_docs
    dev_cut = train_cut + fractions.get(DEV, 0.1) * n_dated_docs

    seen = 0
    for gid, _ in dated:
        group_split[gid] = TRAIN if seen < train_cut else (DEV if seen < dev_cut else TEST)
        seen += sizes[gid]

    return {r.doc_id: group_split[r.group_id] for r in records}


def report_split(
    records: Sequence[DocRecord], assignment: dict[str, str], *, regime: str, seed: int
) -> SplitReport:
    """Summarise a split and verify no group straddles two splits."""
    groups_by_split: dict[str, set[str]] = {name: set() for name in SPLIT_NAMES}
    docs_by_split: dict[str, int] = dict.fromkeys(SPLIT_NAMES, 0)
    strata_by_split: dict[str, dict[str, int]] = {name: {} for name in SPLIT_NAMES}
    dates_by_split: dict[str, list[float]] = {name: [] for name in SPLIT_NAMES}
    group_splits: dict[str, set[str]] = {}
    overall_strata: dict[str, int] = {}

    for r in records:
        split = assignment[r.doc_id]
        groups_by_split[split].add(r.group_id)
        docs_by_split[split] += 1
        strata_by_split[split][r.stratum] = strata_by_split[split].get(r.stratum, 0) + 1
        overall_strata[r.stratum] = overall_strata.get(r.stratum, 0) + 1
        group_splits.setdefault(r.group_id, set()).add(split)
        if r.date_mid is not None:
            dates_by_split[split].append(r.date_mid)

    total = len(records)
    drift = 0.0
    tv: dict[str, float] = {}
    for split, counts in strata_by_split.items():
        n = docs_by_split[split]
        if not n:
            continue
        deviation = 0.0
        for stratum, overall in overall_strata.items():
            gap = abs(counts.get(stratum, 0) / n - overall / total)
            drift = max(drift, gap)
            deviation += gap
        tv[split] = round(deviation / 2, 4)

    train_dates = dates_by_split[TRAIN]
    test_dates = dates_by_split[TEST]
    overlap = 0
    if train_dates and test_dates:
        test_start = min(test_dates)
        overlap = sum(1 for d in train_dates if d >= test_start)

    return SplitReport(
        regime=regime,
        seed=seed,
        counts={
            name: SplitCounts(
                n_docs=docs_by_split[name],
                n_groups=len(groups_by_split[name]),
                fraction=round(docs_by_split[name] / total, 4) if total else 0.0,
            )
            for name in SPLIT_NAMES
        },
        n_docs=total,
        n_groups=len(group_splits),
        n_strata=len(overall_strata),
        max_stratum_drift=round(drift, 4),
        stratum_tv_distance=tv,
        n_train_after_test_start=overlap,
        temporal_overlap_rate=round(overlap / len(train_dates), 4) if train_dates else 0.0,
        date_range_by_split={
            name: [min(v), max(v)] if v else [None, None]
            for name, v in dates_by_split.items()
        },
        leaked_groups=sorted(g for g, s in group_splits.items() if len(s) > 1),
    )


def parse_genres(raw: str | None) -> str:
    """Primary canonical genre for stratification, or ``nogenre``.

    A document may carry several genres; the first is used so that every
    document falls in exactly one stratum. 29% of the corpus has none at all,
    which is why ``nogenre`` is an explicit stratum rather than a dropped row.
    """
    if not raw:
        return NO_GENRE
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return NO_GENRE
    return str(parsed[0]) if parsed else NO_GENRE
