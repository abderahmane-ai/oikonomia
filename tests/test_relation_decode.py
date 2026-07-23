"""Hand-computed fixtures for schema-constrained relation decoding."""

from __future__ import annotations

from oikonomia.relations.decode import FUNCTIONAL_IN_HEAD, constrain


def test_functional_head_keeps_only_best_tail() -> None:
    # One MONEY_AMOUNT (0) scored against two currencies (1, 2): keep the best.
    edges = [
        (0, 1, "HAS_CURRENCY", 0.6),
        (0, 2, "HAS_CURRENCY", 0.9),
    ]
    assert constrain(edges) == [(0, 2, "HAS_CURRENCY")]


def test_distinct_heads_both_kept() -> None:
    # Two different amounts each keep their own currency.
    edges = [
        (0, 1, "HAS_CURRENCY", 0.8),
        (3, 4, "HAS_CURRENCY", 0.7),
    ]
    assert set(constrain(edges)) == {(0, 1, "HAS_CURRENCY"), (3, 4, "HAS_CURRENCY")}


def test_non_functional_types_pass_through() -> None:
    # Two payees for one amount, and two parties: never collapsed.
    edges = [
        (0, 5, "PAID_TO", 0.4),
        (0, 6, "PAID_TO", 0.3),
        (7, 8, "PARTY_OF", 0.9),
        (9, 8, "PARTY_OF", 0.5),
    ]
    assert set(constrain(edges)) == {
        (0, 5, "PAID_TO"),
        (0, 6, "PAID_TO"),
        (7, 8, "PARTY_OF"),
        (9, 8, "PARTY_OF"),
    }


def test_different_functional_types_on_same_head_coexist() -> None:
    # An amount can have a currency AND a tax — different functional types.
    edges = [
        (0, 1, "HAS_CURRENCY", 0.9),
        (0, 2, "CHARGED_UNDER", 0.8),
    ]
    assert set(constrain(edges)) == {(0, 1, "HAS_CURRENCY"), (0, 2, "CHARGED_UNDER")}


def test_has_price_is_not_constrained() -> None:
    # HAS_PRICE is excluded (gold has a good priced in two denominations).
    assert "HAS_PRICE" not in FUNCTIONAL_IN_HEAD
    edges = [(0, 1, "HAS_PRICE", 0.6), (0, 2, "HAS_PRICE", 0.9)]
    assert set(constrain(edges)) == {(0, 1, "HAS_PRICE"), (0, 2, "HAS_PRICE")}
