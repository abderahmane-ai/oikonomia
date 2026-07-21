"""Score a weak/silver labeler against the gold draft — per-label P/R/F1.

Until gold existed no labeler had been scored, so nobody knew where it leaks;
this module scores any labeler against the gold, per label.

The functions here are deliberately **pure** — they take gold and predicted
entity/relation lists and return metrics. Running the actual labeler (which
needs the matcher and the corpus's numeral/line spans) lives in the CLI; the
maths lives here so it can be unit-tested with hand-built fixtures.

Two matching modes, because they separate two different failures:

* **strict** — a predicted entity counts only if its ``(start, end, label)``
  equals a gold one exactly. This is the number a trained model is ultimately
  judged on.
* **relaxed** — same label and *any* character overlap. The gap between strict
  and relaxed is "found the right thing, wrong boundary"; a large relaxed
  recall with a small strict one is a boundary problem, not a detection one.

A label the labeler structurally cannot emit (PERSON, PLACE, …) shows up as
``n_pred == 0`` with real ``n_gold`` — recall 0, precision undefined. That row
*is* the finding, so it is kept rather than hidden.

**Caveat carried in the report:** the gold is ``provenance: model_draft`` (not
human-reviewed), so these are agreement-with-the-draft figures, not
ground-truth precision. Useful as a regression and gap signal; not a number to
publish.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

# A located, typed mention: ``(start, end, label)`` into one text view.
Entity = tuple[int, int, str]
# A relation as indices into a document's entity list, plus its type.
Relation = tuple[int, int, str]  # (head_index, tail_index, type)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _div(num: int, den: int) -> float:
    return num / den if den else 0.0


class LabelScore(BaseModel):
    """Precision/recall/F1 for a single entity label."""

    label: str
    n_gold: int
    n_pred: int
    tp: int
    precision: float
    recall: float
    f1: float


class EntityScore(BaseModel):
    """Entity metrics for one matching mode, micro-averaged plus per-label."""

    mode: str  # "strict" | "relaxed"
    n_gold: int
    n_pred: int
    tp: int
    precision: float
    recall: float
    f1: float
    by_label: list[LabelScore]


class RelationScore(BaseModel):
    """Relation metrics. A predicted relation is correct when both endpoints
    map (by span overlap) to the endpoints of a gold relation of the same type
    and direction."""

    n_gold: int
    n_pred: int
    tp: int
    precision: float
    recall: float
    f1: float
    by_type: list[LabelScore]


class SilverScoreReport(BaseModel):
    """The full verdict of a labeler against the gold draft."""

    n_docs: int
    n_docs_scored: int
    n_docs_unmatched: int = Field(
        description="Gold docs whose text was not found in the corpus (skipped)."
    )
    strict: EntityScore
    relaxed: EntityScore
    relations: RelationScore
    labeler_blind_labels: list[str] = Field(
        description="Gold labels the labeler never emits (n_pred == 0) — the hole."
    )
    caveat: str = (
        "Gold is provenance=model_draft (not human-reviewed): these are "
        "agreement-with-draft figures, not ground-truth precision."
    )


def _match_within_label(
    gold: list[tuple[int, int]], pred: list[tuple[int, int]], *, exact: bool
) -> int:
    """Greedy one-to-one match count between same-label spans.

    One-to-one so a single sprawling prediction cannot claim several gold spans
    (or vice versa). Gold spans are consumed in start order against the first
    still-unused prediction that matches; ``exact`` toggles equality vs overlap.
    """
    used = [False] * len(pred)
    tp = 0
    for gs, ge in sorted(gold):
        for j, (ps, pe) in enumerate(pred):
            if used[j]:
                continue
            hit = (gs == ps and ge == pe) if exact else (gs < pe and ps < ge)
            if hit:
                used[j] = True
                tp += 1
                break
    return tp


def score_entities(gold: list[Entity], pred: list[Entity], *, exact: bool) -> EntityScore:
    """Per-label and micro-averaged entity metrics for one matching mode."""
    gold_by: dict[str, list[tuple[int, int]]] = defaultdict(list)
    pred_by: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for s, e, label in gold:
        gold_by[label].append((s, e))
    for s, e, label in pred:
        pred_by[label].append((s, e))

    rows: list[LabelScore] = []
    tot_tp = tot_gold = tot_pred = 0
    for label in sorted(set(gold_by) | set(pred_by)):
        g, p = gold_by.get(label, []), pred_by.get(label, [])
        tp = _match_within_label(g, p, exact=exact)
        precision, recall = _div(tp, len(p)), _div(tp, len(g))
        rows.append(
            LabelScore(
                label=label,
                n_gold=len(g),
                n_pred=len(p),
                tp=tp,
                precision=round(precision, 4),
                recall=round(recall, 4),
                f1=round(_f1(precision, recall), 4),
            )
        )
        tot_tp += tp
        tot_gold += len(g)
        tot_pred += len(p)

    rows.sort(key=lambda r: r.n_gold, reverse=True)
    micro_p, micro_r = _div(tot_tp, tot_pred), _div(tot_tp, tot_gold)
    return EntityScore(
        mode="exact" if exact else "relaxed",
        n_gold=tot_gold,
        n_pred=tot_pred,
        tp=tot_tp,
        precision=round(micro_p, 4),
        recall=round(micro_r, 4),
        f1=round(_f1(micro_p, micro_r), 4),
        by_label=rows,
    )


def _map_pred_to_gold(gold: list[Entity], pred: list[Entity]) -> dict[int, int]:
    """Map each predicted entity index to an overlapping gold entity index.

    Overlap alone (label ignored), because a relation is judged by *which two
    things* it connects, not by whether the labeler also typed them correctly —
    that is already measured by :func:`score_entities`.
    """
    mapping: dict[int, int] = {}
    for pi, (ps, pe, _) in enumerate(pred):
        for gi, (gs, ge, _) in enumerate(gold):
            if ps < ge and gs < pe:
                mapping[pi] = gi
                break
    return mapping


def score_relations(
    gold_entities: list[Entity],
    gold_relations: list[Relation],
    pred_entities: list[Entity],
    pred_relations: list[Relation],
) -> RelationScore:
    """Relation metrics, directed, keyed on span-mapped endpoints and type."""
    mapping = _map_pred_to_gold(gold_entities, pred_entities)
    gold_set = {(h, t, ty) for h, t, ty in gold_relations}

    gold_by_type: dict[str, int] = defaultdict(int)
    pred_by_type: dict[str, int] = defaultdict(int)
    tp_by_type: dict[str, int] = defaultdict(int)
    for _, _, ty in gold_relations:
        gold_by_type[ty] += 1

    used: set[tuple[int, int, str]] = set()
    tp = 0
    for ph, pt, ty in pred_relations:
        pred_by_type[ty] += 1
        gh, gt = mapping.get(ph), mapping.get(pt)
        if gh is None or gt is None:
            continue
        key = (gh, gt, ty)
        if key in gold_set and key not in used:
            used.add(key)
            tp += 1
            tp_by_type[ty] += 1

    rows: list[LabelScore] = []
    for ty in sorted(set(gold_by_type) | set(pred_by_type)):
        ng, npd, t = gold_by_type.get(ty, 0), pred_by_type.get(ty, 0), tp_by_type.get(ty, 0)
        precision, recall = _div(t, npd), _div(t, ng)
        rows.append(
            LabelScore(
                label=ty,
                n_gold=ng,
                n_pred=npd,
                tp=t,
                precision=round(precision, 4),
                recall=round(recall, 4),
                f1=round(_f1(precision, recall), 4),
            )
        )
    rows.sort(key=lambda r: r.n_gold, reverse=True)

    n_gold, n_pred = len(gold_relations), len(pred_relations)
    precision, recall = _div(tp, n_pred), _div(tp, n_gold)
    return RelationScore(
        n_gold=n_gold,
        n_pred=n_pred,
        tp=tp,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(_f1(precision, recall), 4),
        by_type=rows,
    )


def _accumulate_entities(
    per_doc: list[tuple[list[Entity], list[Relation], list[Entity], list[Relation]]],
    *,
    exact: bool,
) -> EntityScore:
    """Score entities per document and sum the counts.

    Entity spans are document-local, so pooling all documents' spans into one
    list before matching would let a span in one document match an identical
    span in another. Matching is done inside each document; only the resulting
    counts are added up.
    """
    g_by: dict[str, int] = defaultdict(int)
    p_by: dict[str, int] = defaultdict(int)
    tp_by: dict[str, int] = defaultdict(int)
    for gold_ents, _, pred_ents, _ in per_doc:
        doc = score_entities(gold_ents, pred_ents, exact=exact)
        for row in doc.by_label:
            g_by[row.label] += row.n_gold
            p_by[row.label] += row.n_pred
            tp_by[row.label] += row.tp

    rows: list[LabelScore] = []
    tot_tp = tot_gold = tot_pred = 0
    for label in set(g_by) | set(p_by):
        ng, npd, t = g_by.get(label, 0), p_by.get(label, 0), tp_by.get(label, 0)
        p, r = _div(t, npd), _div(t, ng)
        rows.append(
            LabelScore(
                label=label,
                n_gold=ng,
                n_pred=npd,
                tp=t,
                precision=round(p, 4),
                recall=round(r, 4),
                f1=round(_f1(p, r), 4),
            )
        )
        tot_tp += t
        tot_gold += ng
        tot_pred += npd
    rows.sort(key=lambda row: row.n_gold, reverse=True)
    mp, mr = _div(tot_tp, tot_pred), _div(tot_tp, tot_gold)
    return EntityScore(
        mode="exact" if exact else "relaxed",
        n_gold=tot_gold,
        n_pred=tot_pred,
        tp=tot_tp,
        precision=round(mp, 4),
        recall=round(mr, 4),
        f1=round(_f1(mp, mr), 4),
        by_label=rows,
    )


def build_report(
    *,
    n_docs: int,
    n_docs_scored: int,
    per_doc: list[tuple[list[Entity], list[Relation], list[Entity], list[Relation]]],
) -> SilverScoreReport:
    """Assemble the full report from per-document (gold, pred) tuples.

    Everything is scored per document and summed: entity spans and relation
    indices are both document-local, so neither may be pooled before matching.
    """
    strict = _accumulate_entities(per_doc, exact=True)
    relaxed = _accumulate_entities(per_doc, exact=False)

    n_gold = n_pred = tp = 0
    type_gold: dict[str, int] = defaultdict(int)
    type_pred: dict[str, int] = defaultdict(int)
    type_tp: dict[str, int] = defaultdict(int)
    for ge, gr, pe, pr in per_doc:
        rel = score_relations(ge, gr, pe, pr)
        n_gold += rel.n_gold
        n_pred += rel.n_pred
        tp += rel.tp
        for row in rel.by_type:
            type_gold[row.label] += row.n_gold
            type_pred[row.label] += row.n_pred
            type_tp[row.label] += row.tp

    rel_rows: list[LabelScore] = []
    for ty in sorted(set(type_gold) | set(type_pred)):
        ng, npd, t = type_gold.get(ty, 0), type_pred.get(ty, 0), type_tp.get(ty, 0)
        p, r = _div(t, npd), _div(t, ng)
        rel_rows.append(
            LabelScore(
                label=ty,
                n_gold=ng,
                n_pred=npd,
                tp=t,
                precision=round(p, 4),
                recall=round(r, 4),
                f1=round(_f1(p, r), 4),
            )
        )
    rel_rows.sort(key=lambda r: r.n_gold, reverse=True)
    rp, rr = _div(tp, n_pred), _div(tp, n_gold)
    relations = RelationScore(
        n_gold=n_gold,
        n_pred=n_pred,
        tp=tp,
        precision=round(rp, 4),
        recall=round(rr, 4),
        f1=round(_f1(rp, rr), 4),
        by_type=rel_rows,
    )

    blind = [row.label for row in strict.by_label if row.n_pred == 0 and row.n_gold > 0]
    return SilverScoreReport(
        n_docs=n_docs,
        n_docs_scored=n_docs_scored,
        n_docs_unmatched=n_docs - n_docs_scored,
        strict=strict,
        relaxed=relaxed,
        relations=relations,
        labeler_blind_labels=blind,
    )
