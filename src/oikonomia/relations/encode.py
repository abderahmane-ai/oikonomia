"""Typed, range-aware candidate generation for span-pair relation extraction.

A relation classifier does not look at every ordered pair of entities in a
document — the schema forbids most of them. :data:`RELATION_SIGNATURES` (the one
authority, in :mod:`oikonomia.gold.validate`) fixes, per relation type, the set
of entity labels allowed at each endpoint. So a *candidate* is any ordered index
pair ``(h, t)`` whose ``(label_h, label_t)`` is admissible for at least one type;
everything else is not a relation and never becomes a training example.

This prunes hard and, crucially, **loses no gold**: every gold relation already
satisfies its signature (``oik gold check`` enforces it), so each is generated as
a candidate — :func:`uncovered_relations` is the standing guard on that property.

Two same-signature types make this the interesting problem: ``PAID_BY`` and
``PAID_TO`` share ``PERSON|PERSON_ROLE → MONEY_AMOUNT|COMMODITY``, so for that
label pair the label set is ``{NO_RELATION, PAID_BY, PAID_TO}`` and only the
*verb* (learned by the model, not the rules) fixes the direction.

**Range-aware pruning.** Measured on gold, relations are bimodal: the
economic-quantity links (:data:`LOCAL_FAMILY`) sit within ~400 chars, while the
party/direction/date links anchor on the ~1/doc ``TRANSACTION`` or reach across a
clause (gaps up to ~900). So a character-gap cap is applied *only* to the local
family, where it kills dense-account cross-products without dropping any gold.

Everything here is pure and tokenizer-agnostic; the model side (torch) lives in
``modal_app/relations.py``.
"""

from __future__ import annotations

from collections.abc import Iterable

from oikonomia.gold.validate import RELATION_SIGNATURES

Entity = tuple[int, int, str]  # (char_start, char_end, label)
Relation = tuple[int, int, str]  # (head_index, tail_index, type) into an entity list
Candidate = tuple[int, int]  # (head_index, tail_index)
LabeledCandidate = tuple[int, int, str]  # (head_index, tail_index, type | NO_RELATION)
Offset = tuple[int, int]  # (char_start, char_end) of one token

NO_RELATION = "NO_RELATION"

# The relation types, sorted for a deterministic head-index assignment.
RELATION_TYPES: tuple[str, ...] = tuple(sorted(RELATION_SIGNATURES))
# The classifier's label list: NO_RELATION is id 0, then the types in order.
RELATION_LABELS: list[str] = [NO_RELATION, *RELATION_TYPES]

# Entity labels that can be a relation endpoint (head or tail of some type) — the
# type-embedding vocabulary the span-pair model needs. Labels that appear in no
# signature (AGE, PLACE, PRICE_TERM) can never be a candidate endpoint, so they
# need no embedding; deriving this from the contract avoids scanning the corpus.
ENDPOINT_LABELS: tuple[str, ...] = tuple(
    sorted({lab for head, tail in RELATION_SIGNATURES.values() for lab in (*head, *tail)})
)

# Relation types whose endpoints are always close (economic-quantity links, and
# the 8b attribute appositions — a title/age sits right beside its name, median
# gap ~1). Only these are subject to the character-gap cap; the rest are left
# uncapped. The cap (500) dwarfs any real apposition gap, so no gold is dropped;
# the point is to kill the O(n²) person×attribute cross-product in dense poll-tax
# registers, where hundreds of names and titles co-occur.
LOCAL_FAMILY: frozenset[str] = frozenset(
    {
        "HAS_CURRENCY", "HAS_UNIT", "HAS_QUANTITY", "HAS_PRICE", "CHARGED_UNDER",
        "HAS_OCCUPATION", "HAS_AGE",
    }
)
# Gold local-family gaps top out at 411 chars (HAS_PRICE); 500 keeps every gold
# candidate with margin while still pruning far-apart pairs in dense registers.
DEFAULT_LOCAL_CHAR_GAP = 500


def _build_admissibility() -> tuple[
    dict[str, dict[str, tuple[str, ...]]], dict[tuple[str, str], bool]
]:
    """Precompute ``head -> tail -> types`` and ``(head, tail) -> local-only?``.

    Candidate generation is O(n²) over a document's entities, and the dense
    poll-tax registers reach 200+ entities. Doing the 9-signature scan per pair is
    what made the corpus-scale scan crawl; a two-level dict lookup makes each pair
    O(1).
    """
    table: dict[str, dict[str, list[str]]] = {}
    for rtype, (want_head, want_tail) in RELATION_SIGNATURES.items():
        for hl in want_head:
            for tl in want_tail:
                table.setdefault(hl, {}).setdefault(tl, []).append(rtype)
    admissible: dict[str, dict[str, tuple[str, ...]]] = {
        hl: {tl: tuple(sorted(types)) for tl, types in tails.items()}
        for hl, tails in table.items()
    }
    local_only = {
        (hl, tl): all(ty in LOCAL_FAMILY for ty in types)
        for hl, tails in admissible.items()
        for tl, types in tails.items()
    }
    return admissible, local_only


_ADMISSIBLE, _LOCAL_ONLY = _build_admissibility()


def admissible_types(head_label: str, tail_label: str) -> tuple[str, ...]:
    """Relation types whose signature allows ``head_label -> tail_label`` (sorted).

    Empty when the ordered label pair is not a legal endpoint pair for any type
    (e.g. ``PERSON -> PERSON``). Returns both ``PAID_BY`` and ``PAID_TO`` for
    ``PERSON -> MONEY_AMOUNT`` — the direction the model must disambiguate.
    """
    return _ADMISSIBLE.get(head_label, {}).get(tail_label, ())


def relation_label_maps(
    labels: list[str] | None = None,
) -> tuple[dict[str, int], dict[int, str]]:
    """Return ``(label2id, id2label)`` for the relation label list."""
    labels = labels if labels is not None else RELATION_LABELS
    label2id = {lab: i for i, lab in enumerate(labels)}
    id2label = {i: lab for lab, i in label2id.items()}
    return label2id, id2label


def admissible_mask(
    head_label: str, tail_label: str, labels: list[str] | None = None
) -> list[bool]:
    """Boolean mask over ``labels``: ``NO_RELATION`` plus this pair's legal types.

    Used at inference to blank out logits for types the schema forbids for the
    pair's endpoint labels, so the model can never emit an impossible relation.
    """
    labels = labels if labels is not None else RELATION_LABELS
    allowed = {NO_RELATION, *admissible_types(head_label, tail_label)}
    return [lab in allowed for lab in labels]


def _span_gap(a: Entity, b: Entity) -> int:
    """Character gap between two entity spans (0 if they touch or overlap)."""
    return max(0, max(a[0], b[0]) - min(a[1], b[1]))


def candidate_pairs(
    entities: list[Entity],
    *,
    local_char_gap: int = DEFAULT_LOCAL_CHAR_GAP,
) -> list[Candidate]:
    """Ordered index pairs admissible for some relation type, range-pruned.

    A pair whose admissible types are *all* in :data:`LOCAL_FAMILY` is dropped
    when the two spans are more than ``local_char_gap`` characters apart. Pairs
    with any long-range admissible type (party/direction/date) are never
    gap-pruned — those legitimately span a document.
    """
    pairs: list[Candidate] = []
    for h, eh in enumerate(entities):
        tails = _ADMISSIBLE.get(eh[2])
        if not tails:  # this label heads no relation type — skip it entirely
            continue
        hl = eh[2]
        for t, et in enumerate(entities):
            if h == t or et[2] not in tails:
                continue
            if _LOCAL_ONLY[(hl, et[2])] and _span_gap(eh, et) > local_char_gap:
                continue
            pairs.append((h, t))
    return pairs


def uncovered_relations(
    entities: list[Entity],
    relations: Iterable[Relation],
    *,
    local_char_gap: int = DEFAULT_LOCAL_CHAR_GAP,
) -> list[Relation]:
    """Gold relations that candidate generation would *not* produce.

    The recall guard: this must be empty for gold (checked by ``oik relation
    prepare`` and the test suite). A non-empty result means candidate generation
    silently caps that relation's recall at zero — a schema or cap bug, not noise.
    """
    pairs = set(candidate_pairs(entities, local_char_gap=local_char_gap))
    return [(h, t, ty) for h, t, ty in relations if (h, t) not in pairs]


def label_candidates(
    entities: list[Entity],
    relations: Iterable[Relation],
    *,
    local_char_gap: int = DEFAULT_LOCAL_CHAR_GAP,
) -> list[LabeledCandidate]:
    """Every candidate pair with its gold relation type, or ``NO_RELATION``.

    A relation whose pair is not a candidate (see :func:`uncovered_relations`) is
    ignored here rather than raised on — silver carries a noisy tail and must not
    crash training; the recall guard is where gold coverage is asserted.
    """
    pairs = candidate_pairs(entities, local_char_gap=local_char_gap)
    index = {pair: i for i, pair in enumerate(pairs)}
    labels = [NO_RELATION] * len(pairs)
    for h, t, ty in relations:
        i = index.get((h, t))
        if i is not None:
            labels[i] = ty
    return [(h, t, labels[i]) for i, (h, t) in enumerate(pairs)]


def window_entities(
    entities: list[Entity],
    relations: list[Relation],
    ranges: list[tuple[int, int] | None],
) -> tuple[list[Entity], list[tuple[int, int]], list[Relation], dict[int, int]]:
    """Drop entities outside the token window (``ranges[i] is None``) and reindex.

    A truncated document (the giant silver registers reach ~45k entities) exposes
    only the entities inside its 512-token window; pairing over the rest is both
    wasted and, at O(n²), ruinous. This keeps the in-window entities, remaps the
    surviving relations to the new contiguous indices, and drops any relation with
    a dropped endpoint. Returns ``(kept_entities, kept_ranges, kept_relations,
    old_to_new)``; ``old_to_new`` lets the caller remap parallel data (e.g. silver
    confidences). Gold documents fit whole, so nothing is dropped for them.
    """
    keep = [i for i, r in enumerate(ranges) if r is not None]
    old_to_new = {old: new for new, old in enumerate(keep)}
    kept_entities = [entities[i] for i in keep]
    kept_ranges = [r for r in ranges if r is not None]
    kept_relations = [
        (old_to_new[h], old_to_new[t], ty)
        for h, t, ty in relations
        if h in old_to_new and t in old_to_new
    ]
    return kept_entities, kept_ranges, kept_relations, old_to_new


def char_span_to_token_range(
    offsets: list[Offset], start: int, end: int
) -> tuple[int, int] | None:
    """Map a character span ``[start, end)`` to a token index range ``[lo, hi)``.

    ``offsets`` is the fast tokenizer's ``offset_mapping``. The range covers every
    real token overlapping the span; zero-length offsets (special/padding tokens)
    are skipped. Returns ``None`` when no real token overlaps — the span fell
    outside the (possibly truncated) window and cannot be represented.
    """
    lo: int | None = None
    hi = 0
    for i, (cs, ce) in enumerate(offsets):
        if ce <= cs:  # special / padding token
            continue
        if cs < end and start < ce:  # non-empty overlap
            if lo is None:
                lo = i
            hi = i + 1
    if lo is None:
        return None
    return lo, hi
