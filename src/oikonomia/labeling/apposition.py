"""Deterministic apposition rules for attribute relations (Phase 8b).

Coverage, not accuracy, is 8b's problem. The entity model already extracts
``OCCUPATION`` (192 in gold) and ``AGE`` (133), yet before this module both sat
in *no* relation at all — together with 79% of every ``PERSON`` — so they never
reached the database. Measured on gold, these attributes are **apposition**: the
title or age stands right next to the name it qualifies (median gap **1** char
for OCCUPATION; the ``(ὡς) ἐτῶν N`` formula for AGE). An adjacency that regular is
recovered by a rule, not a model — deterministic, and every edge auditable to its
two spans, which is exactly what the traceable-database deliverable needs and
what a learned head cannot give.

Direction is fixed by the schema (``PERSON``/``PERSON_ROLE`` → ``OCCUPATION``/
``AGE``) and by Greek word order: the subject **precedes** the attribute
(``Ἀρτεμίδωρος ἰατρός``, ``Φιλουμένη ὡς ἐτῶν ν``). Anchoring on the nearest
subject that *ends at or before* the attribute — never the one after it — is also
what makes the rule survive the dense signalement registers, where the *next*
registrant's name sits immediately after an age and would otherwise be misread as
its subject (33 such false attractors in gold).

Pure and tokenizer-agnostic: it operates on ``(start, end, label)`` entity tuples
and returns ``(head_index, tail_index, type)`` relations, so both the silver
labeler and the gold-draft tool call it, and it is unit-testable without a model
or the corpus.
"""

from __future__ import annotations

Entity = tuple[int, int, str]  # (char_start, char_end, label)
Relation = tuple[int, int, str]  # (head_index, tail_index, type)

HAS_OCCUPATION = "HAS_OCCUPATION"
HAS_AGE = "HAS_AGE"

# Labels that can bear an attribute — the head of every attribute relation.
SUBJECT_LABELS: frozenset[str] = frozenset({"PERSON", "PERSON_ROLE"})

# The attribute (tail) label → relation type it produces.
ATTRIBUTE_TYPES: dict[str, str] = {"OCCUPATION": HAS_OCCUPATION, "AGE": HAS_AGE}

# The label of a counted category's tally — used only by the headcount guard.
QUANTITY = "QUANTITY"

# Max characters between the subject's end and the attribute's start. Measured on
# gold: OCCUPATION sits at median gap 1 (91% within 40); the AGE ``(ὡς) ἐτῶν N``
# formula pushes the subject ~7–9 chars further back, still inside 40. Larger
# would start borrowing a subject from the previous clause.
DEFAULT_MAX_GAP = 40

# An OCCUPATION immediately followed by a QUANTITY within this many characters is
# a *counted category* line (``ἱερεῖς β`` = "priests: 2"), not a person's title:
# it is the head of a HAS_QUANTITY, which the schema already provides for. Such an
# occupation gets no HAS_OCCUPATION edge. Rare in the curated narrative gold (2 of
# 158), but systematic in the dense accounts and tax registers that dominate the
# corpus, where "CATEGORY tally" lines are the norm. AGE is never a headcount (the
# ``ἐτῶν N`` numeral is its own tail), so the guard is OCCUPATION-only.
HEADCOUNT_GAP = 3


def attribute_relations(
    entities: list[Entity],
    *,
    max_gap: int = DEFAULT_MAX_GAP,
    headcount_gap: int = HEADCOUNT_GAP,
) -> list[Relation]:
    """Link each OCCUPATION/AGE to the nearest subject that precedes it.

    For every attribute entity (``OCCUPATION`` or ``AGE``), the head is the
    ``PERSON``/``PERSON_ROLE`` whose span *ends at or before* the attribute's
    start and is closest to it, provided the gap is at most ``max_gap``. An
    attribute with no subject within reach (a lost or distant name) yields no
    edge rather than a wrong one — recall is the model's and the gold-draft
    review's job, precision is this rule's.

    An OCCUPATION that is a counted category — immediately followed by a
    ``QUANTITY`` within ``headcount_gap`` characters — is skipped (see
    :data:`HEADCOUNT_GAP`): it is a HAS_QUANTITY head, not a title.

    Returns edges in attribute order; ``(head, tail)`` never repeats because each
    attribute produces at most one edge.
    """
    subjects = [i for i, (_s, _e, lab) in enumerate(entities) if lab in SUBJECT_LABELS]
    quantity_starts = [s for (s, _e, lab) in entities if lab == QUANTITY]
    rels: list[Relation] = []
    for ti, (ts, te, tlab) in enumerate(entities):
        rtype = ATTRIBUTE_TYPES.get(tlab)
        if rtype is None:
            continue
        if rtype == HAS_OCCUPATION and any(
            te <= qs <= te + headcount_gap for qs in quantity_starts
        ):
            continue  # counted category ("ἱερεῖς β"), not a personal title
        best: tuple[int, int] | None = None  # (gap, subject_index)
        for si in subjects:
            _ss, se, _lab = entities[si]
            if se > ts:  # subject must end at or before the attribute begins
                continue
            gap = ts - se
            if gap <= max_gap and (best is None or gap < best[0]):
                best = (gap, si)
        if best is not None:
            rels.append((best[1], ti, rtype))
    return rels
