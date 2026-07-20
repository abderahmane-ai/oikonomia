"""Near-duplicate detection, so a split cannot leak a document to itself.

Papyri repeat. The same text is republished in a new corpus volume, a roll is
edited in fragments that overlap, and a tax register survives in multiple
near-identical copies. A random document split puts those on both sides of the
train/test line, and the model scores well by recognising text it has already
seen. Deduplication is consistently the highest-leverage step in corpus
preparation for exactly this reason.

The method is standard MinHash + LSH banding over character n-gram shingles:

* **shingles** are character n-grams of the *folded* text (accents, case and
  final sigma removed), so an editor's diacritics cannot hide a duplicate;
* **MinHash** compresses each document's shingle set to a fixed-length
  signature whose agreement rate estimates Jaccard similarity;
* **LSH banding** buckets signatures so only plausible pairs are compared,
  turning an O(N²) all-pairs problem into roughly O(N log N);
* candidate pairs are then **checked against the real threshold**, because
  banding is a recall device and admits false positives by design.

Everything is seeded and pure-Python + numpy: the same corpus must always
produce the same clusters, or the splits are not reproducible.

Threshold choice: 0.8 Jaccard over 5-grams. The usable band is roughly
0.7–0.85 — below it, documents merely on the same subject get merged (in this
corpus, every tax receipt resembles every other tax receipt), and above it,
lightly re-edited republications slip through.
"""

from __future__ import annotations

import zlib
from collections.abc import Iterable, Sequence

import numpy as np
from pydantic import BaseModel, Field

from oikonomia.labeling.normalize import normalize

SHINGLE_SIZE = 5
NUM_PERM = 128
BANDS = 16  # BANDS * ROWS must equal NUM_PERM
ROWS = 8
DEFAULT_THRESHOLD = 0.8

# A 61-bit Mersenne prime: the standard modulus for the (a*x + b) mod p
# universal hash family used to simulate independent permutations.
_MERSENNE = (1 << 61) - 1


class DuplicateCluster(BaseModel):
    """A set of document ids judged near-identical."""

    members: list[str]
    size: int


class DedupResult(BaseModel):
    """Cluster assignment for every document."""

    # doc_id -> cluster id. Singletons get their own cluster.
    cluster_of: dict[str, str] = Field(default_factory=dict)
    clusters: list[DuplicateCluster] = Field(default_factory=list)
    n_docs: int = 0
    n_clusters: int = 0
    n_duplicated_docs: int = 0

    @property
    def duplication_rate(self) -> float:
        return round(self.n_duplicated_docs / self.n_docs, 4) if self.n_docs else 0.0


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[int]:
    """Hash the folded character n-grams of ``text``.

    ``zlib.crc32`` rather than the builtin ``hash``: Python randomises string
    hashing per process (PYTHONHASHSEED), so ``hash`` would silently produce
    different clusters on every run and the splits would not be reproducible.
    crc32 is stable across processes and machines, and is ~4x faster here.

    Hashing the shingles rather than keeping the strings keeps memory flat: a
    document contributes at most ``len(text)`` integers regardless of how long
    its words are.
    """
    folded = normalize(text).text
    # Collapse whitespace runs so that layout differences between editions
    # (line breaks, indentation) do not register as textual difference.
    folded = " ".join(folded.split())
    if not folded:
        return set()
    if len(folded) < size:
        return {zlib.crc32(folded.encode())}
    return {
        zlib.crc32(folded[i : i + size].encode()) for i in range(len(folded) - size + 1)
    }


def _hash_coefficients(num_perm: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    a = rng.integers(1, _MERSENNE, size=num_perm, dtype=np.uint64)
    b = rng.integers(0, _MERSENNE, size=num_perm, dtype=np.uint64)
    return a, b


def minhash_signature(
    shingle_hashes: set[int], a: np.ndarray, b: np.ndarray
) -> np.ndarray:
    """Compute the MinHash signature of one shingle set.

    Vectorised over permutations rather than looped: with 128 permutations and
    a few hundred shingles per document, the per-document Python loop is what
    would dominate, not the arithmetic.
    """
    if not shingle_hashes:
        return np.full(len(a), np.iinfo(np.uint64).max, dtype=np.uint64)
    x = np.fromiter(shingle_hashes, dtype=np.uint64, count=len(shingle_hashes))
    # (num_perm, n_shingles) -> min over shingles.
    hashed = (a[:, None] * x[None, :] + b[:, None]) % _MERSENNE
    result: np.ndarray = hashed.min(axis=1)
    return result


class _UnionFind:
    """Disjoint-set over document indices, for merging duplicate pairs."""

    __slots__ = ("_parent", "_rank")

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, i: int) -> int:
        while self._parent[i] != i:
            self._parent[i] = self._parent[self._parent[i]]  # path halving
            i = self._parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri == rj:
            return
        if self._rank[ri] < self._rank[rj]:
            ri, rj = rj, ri
        self._parent[rj] = ri
        if self._rank[ri] == self._rank[rj]:
            self._rank[ri] += 1


def cluster_duplicates(
    doc_ids: Sequence[str],
    texts: Iterable[str],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    num_perm: int = NUM_PERM,
    bands: int = BANDS,
    seed: int = 0,
) -> DedupResult:
    """Cluster near-identical documents. Deterministic for a given seed."""
    if num_perm % bands:
        msg = f"num_perm ({num_perm}) must be divisible by bands ({bands})"
        raise ValueError(msg)
    rows = num_perm // bands

    a, b = _hash_coefficients(num_perm, seed)
    sigs = [minhash_signature(shingles(t), a, b) for t in texts]
    if len(sigs) != len(doc_ids):
        msg = f"doc_ids ({len(doc_ids)}) and texts ({len(sigs)}) must be the same length"
        raise ValueError(msg)
    signatures = (
        np.vstack(sigs) if sigs else np.empty((0, num_perm), dtype=np.uint64)
    )

    # LSH banding: documents sharing a whole band are candidates. Only pairs
    # inside a bucket are ever compared, which is what avoids the O(N^2) scan.
    uf = _UnionFind(len(doc_ids))
    checked: set[tuple[int, int]] = set()
    for band in range(bands):
        buckets: dict[bytes, list[int]] = {}
        chunk = signatures[:, band * rows : (band + 1) * rows]
        for i, row in enumerate(chunk):
            buckets.setdefault(row.tobytes(), []).append(i)
        for bucket in buckets.values():
            if len(bucket) < 2:
                continue
            for idx, i in enumerate(bucket):
                for j in bucket[idx + 1 :]:
                    pair = (i, j)
                    if pair in checked:
                        continue
                    checked.add(pair)
                    # Banding is tuned for recall and admits pairs below the
                    # threshold; confirm against the signature estimate.
                    if float(np.mean(signatures[i] == signatures[j])) >= threshold:
                        uf.union(i, j)

    groups: dict[int, list[str]] = {}
    for i, doc_id in enumerate(doc_ids):
        groups.setdefault(uf.find(i), []).append(doc_id)

    cluster_of: dict[str, str] = {}
    clusters: list[DuplicateCluster] = []
    n_duplicated = 0
    for members in groups.values():
        # Name the cluster after its smallest member, so cluster ids are stable
        # under reordering of the input.
        cid = min(members)
        for m in members:
            cluster_of[m] = cid
        if len(members) > 1:
            clusters.append(DuplicateCluster(members=sorted(members), size=len(members)))
            n_duplicated += len(members)

    clusters.sort(key=lambda c: (-c.size, c.members[0]))
    return DedupResult(
        cluster_of=cluster_of,
        clusters=clusters,
        n_docs=len(doc_ids),
        n_clusters=len(groups),
        n_duplicated_docs=n_duplicated,
    )
