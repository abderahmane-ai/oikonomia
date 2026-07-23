"""Schema-constrained decoding for relation extraction (Phase 8a).

The span-pair model scores each candidate pair independently, so it can emit
structurally impossible sets — one MONEY_AMOUNT with two currencies, one QUANTITY
with two units. That over-generation is exactly the nearest-pair baseline's
failure mode (precision 0.30 at recall 0.85). Several relations are *functional
in their head*: an amount has one currency, a quantity one unit, a payment one
tax. Enforcing that after scoring keeps only the best-scoring tail per head and
removes those false positives, lifting precision without dropping the true edge.

The functional set is chosen to be **recall-safe on gold**: every head of these
types has exactly one tail across all 115 gold docs (checked). ``HAS_PRICE`` is
deliberately excluded — gold has a commodity priced in two denominations, so it
is not functional.

Pure: operates on scored ``(head, tail, type, score)`` edges, so it is
unit-testable without a model.
"""

from __future__ import annotations

ScoredEdge = tuple[int, int, str, float]  # (head_index, tail_index, type, score)
Edge = tuple[int, int, str]

# Relations with exactly one tail per head — keep only the highest-scoring tail.
# Verified against gold: 0 heads of these types have >1 tail (recall-safe).
FUNCTIONAL_IN_HEAD: frozenset[str] = frozenset({"HAS_CURRENCY", "HAS_UNIT", "CHARGED_UNDER"})


def constrain(
    edges: list[ScoredEdge],
    *,
    functional_in_head: frozenset[str] = FUNCTIONAL_IN_HEAD,
) -> list[Edge]:
    """Apply schema constraints to scored edges, returning the kept ``(h, t, type)``.

    For each functional-in-head relation, only the highest-scoring ``(head, tail)``
    survives per ``(head, type)``; all other relations pass through unchanged.
    Ties keep the first seen, so decoding is deterministic given a stable input
    order.
    """
    best: dict[tuple[int, str], ScoredEdge] = {}
    passthrough: list[Edge] = []
    for edge in edges:
        h, t, ty, s = edge
        if ty in functional_in_head:
            key = (h, ty)
            cur = best.get(key)
            if cur is None or s > cur[3]:
                best[key] = edge
        else:
            passthrough.append((h, t, ty))
    kept = [(h, t, ty) for (h, t, ty, _) in best.values()]
    return kept + passthrough
