"""Tests for <num> value parsing."""

from __future__ import annotations

from oikonomia.ingest.numerals import parse_num_value


def test_integers() -> None:
    assert parse_num_value("10") == 10.0
    assert parse_num_value("-3") == -3.0


def test_fractions() -> None:
    assert parse_num_value("1/2") == 0.5
    assert parse_num_value("3/4") == 0.75


def test_decimal() -> None:
    assert parse_num_value("2.5") == 2.5


def test_uninterpretable_returns_none() -> None:
    assert parse_num_value(None) is None
    assert parse_num_value("") is None
    assert parse_num_value("   ") is None
    assert parse_num_value("1-10") is None  # a range, not a value
    assert parse_num_value("many") is None
    assert parse_num_value("1/0") is None  # zero denominator
