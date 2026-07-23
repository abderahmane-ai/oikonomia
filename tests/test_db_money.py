"""Hand-computed fixtures for monetary normalization (Phase 9).

The conversions are fixed classical ratios (talent=6000 dr, drachma=6 obols,
nomisma=24 keratia); each case reduces one amount to its system's base and,
crucially, asserts that the silver and gold systems never share a scale.
"""

from __future__ import annotations

from oikonomia.db.money import GOLD, SILVER, UNKNOWN, is_currency_id, normalize_amount


def test_silver_ladder_reduces_to_drachmas() -> None:
    assert normalize_amount(100, "drachma").value_base == 100.0
    assert normalize_amount(2, "talent").value_base == 12000.0
    assert normalize_amount(3, "obol").value_base == 0.5  # 3/6 dr
    assert normalize_amount(1, "tetrobol").value_base == 4.0 / 6
    assert normalize_amount(48, "chalkous").value_base == 1.0  # 48 chalkoi = 1 dr
    for cid in ("drachma", "talent", "obol", "chalkous"):
        assert normalize_amount(1, cid).system == SILVER


def test_gold_system_reduces_to_nomismata_and_is_separate() -> None:
    assert normalize_amount(1, "nomisma").value_base == 1.0
    assert normalize_amount(12, "keration").value_base == 0.5  # 12/24 nomisma
    assert normalize_amount(1, "keration").system == GOLD
    # The load-bearing invariant: the two systems are different scales. A caller
    # must group by system and never sum a drachma with a nomisma.
    assert normalize_amount(1, "drachma").system != normalize_amount(1, "nomisma").system


def test_generic_money_words_have_no_denomination() -> None:
    # argyrion/chrysion name money but not a countable unit -> value_base None,
    # system still known, so a filter can drop them rather than mis-scale.
    ag = normalize_amount(50, "argyrion")
    assert ag.system == SILVER and ag.value_base is None
    ch = normalize_amount(50, "chrysion")
    assert ch.system == GOLD and ch.value_base is None


def test_missing_value_or_currency_is_recorded_not_guessed() -> None:
    assert normalize_amount(None, "drachma").value_base is None  # amount unread
    unk = normalize_amount(100, None)  # no currency link
    assert unk.system == UNKNOWN and unk.value_base is None
    assert normalize_amount(100, "sheep").system == UNKNOWN  # not a currency id


def test_is_currency_id() -> None:
    assert is_currency_id("drachma") and is_currency_id("nomisma")
    assert not is_currency_id("wheat") and not is_currency_id(None)
