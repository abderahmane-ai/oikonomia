"""Hand-built fixture for monetary-fact assembly (Phase 9).

The fixture is one clean price clause — "πυροῦ ἀρτάβας β δραχμὰς ρ" ("wheat, 2
artabas, 100 drachmas") — with its relation graph wired by hand, so the walk from
amount → currency → commodity → quantity → unit and the per-unit price are all
checked without a labeler or the corpus.
"""

from __future__ import annotations

from oikonomia.db.facts import DocMeta, Ent, Rel, assemble_monetary, value_for

# "πυροῦ ἀρτάβας β δραχμὰς ρ" — offsets are illustrative, only their order matters.
ENTS = [
    Ent(0, 5, "COMMODITY", "πυροῦ", "wheat", 0.9),  # 0
    Ent(6, 13, "UNIT", "ἀρτάβας", "artaba", 0.9),  # 1
    Ent(14, 15, "QUANTITY", "β", None, 0.8),  # 2  value 2
    Ent(16, 23, "CURRENCY", "δραχμὰς", "drachma", 0.9),  # 3
    Ent(24, 25, "MONEY_AMOUNT", "ρ", None, 0.8),  # 4  value 100
]
RELS = [
    Rel(0, 4, "HAS_PRICE", 0.5),  # wheat -> 100
    Rel(4, 3, "HAS_CURRENCY", 0.7),  # 100 -> drachma
    Rel(0, 2, "HAS_QUANTITY", 0.7),  # wheat -> 2
    Rel(2, 1, "HAS_UNIT", 0.7),  # 2 -> artaba
]
VBS = {(14, 15): 2.0, (24, 25): 100.0}
META = DocMeta(tm_id="999", date_lo=-100, date_hi=-100, place_pleiades=786084, genres="sale")


def test_full_price_observation_assembled_and_normalized() -> None:
    obs = assemble_monetary(ENTS, RELS, VBS, META)
    assert len(obs) == 1
    o = obs[0]
    assert (o.tm_id, o.amount_text, o.value_num) == ("999", "ρ", 100.0)
    assert (o.currency_id, o.system, o.value_base) == ("drachma", "silver", 100.0)
    assert (o.commodity_id, o.quantity, o.unit_id) == ("wheat", 2.0, "artaba")
    assert o.unit_price_base == 50.0  # 100 dr / 2 artabas
    assert (o.date_mid, o.century, o.bin50) == (-100, -1, -100)
    assert o.place_pleiades == 786084


def test_amount_without_currency_is_skipped() -> None:
    # Drop the HAS_CURRENCY edge: the amount has no denomination, so it is not yet
    # a comparable fact and produces no row.
    rels = [r for r in RELS if r.type != "HAS_CURRENCY"]
    assert assemble_monetary(ENTS, rels, VBS, META) == []


def test_bare_amount_normalizes_without_a_commodity() -> None:
    # A currency-bearing amount with no HAS_PRICE is still a monetary fact; the
    # commodity fields are simply empty.
    ents = ENTS[3:5]  # currency, money
    rels = [Rel(1, 0, "HAS_CURRENCY", 0.7)]  # indices into the 2-entity list
    obs = assemble_monetary(ents, rels, {(24, 25): 100.0}, META)
    assert len(obs) == 1
    assert obs[0].value_base == 100.0 and obs[0].commodity_id is None
    assert obs[0].unit_price_base is None


def test_charged_under_tax_is_attached() -> None:
    ents = [
        Ent(0, 7, "CURRENCY", "δραχμὰς", "drachma", 0.9),
        Ent(8, 9, "MONEY_AMOUNT", "ρ", None, 0.8),
        Ent(10, 20, "TAX_TERM", "λαογραφίας", "poll_tax", 0.6),
    ]
    rels = [Rel(1, 0, "HAS_CURRENCY", 0.7), Rel(1, 2, "CHARGED_UNDER", 0.4)]
    obs = assemble_monetary(ents, rels, {(8, 9): 100.0}, META)
    assert len(obs) == 1 and obs[0].tax_id == "poll_tax"


def test_value_for_exact_then_contained() -> None:
    vbs = {(24, 25): 100.0}
    assert value_for(24, 25, vbs) == 100.0  # exact
    assert value_for(20, 30, vbs) == 100.0  # numeral sits inside the span
    assert value_for(0, 5, vbs) is None
