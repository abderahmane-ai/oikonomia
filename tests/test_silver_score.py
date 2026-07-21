"""Hand-computed tests for the silver scorer's maths (no corpus needed)."""

from __future__ import annotations

from oikonomia.labeling.score import (
    build_report,
    score_entities,
    score_relations,
)


def test_exact_match_perfect():
    gold = [(0, 4, "PERSON"), (5, 9, "PLACE")]
    pred = [(0, 4, "PERSON"), (5, 9, "PLACE")]
    s = score_entities(gold, pred, exact=True)
    assert s.precision == 1.0 and s.recall == 1.0 and s.f1 == 1.0
    assert s.tp == 2


def test_exact_misses_boundary_but_relaxed_catches_it():
    gold = [(0, 5, "PERSON")]  # "Ῥώμης"
    pred = [(0, 4, "PERSON")]  # "Ῥώμη" — one char short
    strict = score_entities(gold, pred, exact=True)
    relaxed = score_entities(gold, pred, exact=False)
    assert strict.tp == 0
    assert relaxed.tp == 1
    # Same detection, wrong boundary: relaxed recall 1, strict recall 0.
    assert strict.recall == 0.0 and relaxed.recall == 1.0


def test_label_must_match():
    gold = [(0, 4, "PERSON")]
    pred = [(0, 4, "PLACE")]
    s = score_entities(gold, pred, exact=False)
    assert s.tp == 0
    assert s.recall == 0.0 and s.precision == 0.0


def test_precision_and_recall_are_distinct():
    # Two gold, three predicted, two correct → P=2/3, R=2/2.
    gold = [(0, 2, "QUANTITY"), (4, 6, "QUANTITY")]
    pred = [(0, 2, "QUANTITY"), (4, 6, "QUANTITY"), (8, 9, "QUANTITY")]
    s = score_entities(gold, pred, exact=True)
    assert s.tp == 2
    assert round(s.precision, 3) == 0.667
    assert s.recall == 1.0


def test_one_to_one_matching_no_double_credit():
    # One sprawling prediction must not claim two gold spans.
    gold = [(0, 2, "PERSON"), (3, 5, "PERSON")]
    pred = [(0, 5, "PERSON")]
    relaxed = score_entities(gold, pred, exact=False)
    assert relaxed.tp == 1  # not 2


def test_blind_label_shows_zero_pred():
    gold = [(0, 4, "PERSON")]
    pred: list = []
    report = build_report(
        n_docs=1, n_docs_scored=1, per_doc=[(gold, [], pred, [])]
    )
    assert "PERSON" in report.labeler_blind_labels
    row = next(r for r in report.strict.by_label if r.label == "PERSON")
    assert row.n_pred == 0 and row.recall == 0.0


def test_relations_need_both_endpoints_and_type():
    gold_ents = [(0, 4, "MONEY_AMOUNT"), (5, 9, "CURRENCY")]
    gold_rels = [(0, 1, "HAS_CURRENCY")]
    pred_ents = [(0, 4, "MONEY_AMOUNT"), (5, 9, "CURRENCY")]
    pred_rels = [(0, 1, "HAS_CURRENCY")]
    r = score_relations(gold_ents, gold_rels, pred_ents, pred_rels)
    assert r.tp == 1 and r.precision == 1.0 and r.recall == 1.0


def test_relation_wrong_direction_is_a_miss():
    gold_ents = [(0, 4, "MONEY_AMOUNT"), (5, 9, "CURRENCY")]
    gold_rels = [(0, 1, "HAS_CURRENCY")]
    pred_ents = [(0, 4, "MONEY_AMOUNT"), (5, 9, "CURRENCY")]
    pred_rels = [(1, 0, "HAS_CURRENCY")]  # reversed
    r = score_relations(gold_ents, gold_rels, pred_ents, pred_rels)
    assert r.tp == 0


def test_relation_endpoints_map_by_overlap():
    # Predicted entity spans differ from gold but overlap them; the relation
    # should still match because the endpoints map to the same gold entities.
    gold_ents = [(0, 4, "MONEY_AMOUNT"), (5, 9, "CURRENCY")]
    gold_rels = [(0, 1, "HAS_CURRENCY")]
    pred_ents = [(1, 4, "MONEY_AMOUNT"), (5, 8, "CURRENCY")]
    pred_rels = [(0, 1, "HAS_CURRENCY")]
    r = score_relations(gold_ents, gold_rels, pred_ents, pred_rels)
    assert r.tp == 1


def test_entities_scored_per_document_not_pooled():
    # Same (start,end,label) in two different docs must not cross-match:
    # doc A has the gold, doc B has the prediction. Correct TP is 0.
    doc_a = ([(0, 4, "PERSON")], [], [], [])
    doc_b = ([], [], [(0, 4, "PERSON")], [])
    report = build_report(n_docs=2, n_docs_scored=2, per_doc=[doc_a, doc_b])
    row = next(r for r in report.strict.by_label if r.label == "PERSON")
    assert row.n_gold == 1 and row.n_pred == 1 and row.tp == 0
