"""Hand-computed fixtures for typed relation-candidate generation.

The entity offsets, admissible pairs, gap-cap outcomes and token ranges are all
worked out by hand, so a regression in the candidate logic is caught without a
model or the corpus. The fixture mimics a small receipt: a payer, a house being
sold, its price in drachmas, the transaction, and a date — plus one far-away
currency word that the local-family gap cap must exclude.
"""

from __future__ import annotations

from oikonomia.relations.encode import (
    NO_RELATION,
    RELATION_LABELS,
    admissible_mask,
    admissible_types,
    candidate_pairs,
    char_span_to_token_range,
    label_candidates,
    relation_label_maps,
    uncovered_relations,
    window_entities,
)

# index: (start, end, label)
ENTITIES = [
    (0, 8, "PERSON"),  # 0  Ἀπολλώνις  (payer)
    (20, 26, "COMMODITY"),  # 1  οἰκίας     (the house)
    (30, 36, "CURRENCY"),  # 2  δραχμῶν
    (37, 38, "MONEY_AMOUNT"),  # 3  Β
    (40, 52, "TRANSACTION"),  # 4
    (60, 68, "DATE_REF"),  # 5
    (600, 606, "CURRENCY"),  # 6  a far currency word (>500 chars from the amount)
]
GOLD = [
    (0, 3, "PAID_BY"),
    (1, 3, "HAS_PRICE"),
    (3, 2, "HAS_CURRENCY"),
    (0, 4, "PARTY_OF"),
    (4, 5, "DATED_TO"),
]


def test_admissible_types_direction_ambiguous_pair() -> None:
    # The crux: PERSON -> MONEY_AMOUNT is legal for BOTH payment directions.
    assert admissible_types("PERSON", "MONEY_AMOUNT") == ("PAID_BY", "PAID_TO")


def test_admissible_types_single_and_empty() -> None:
    assert admissible_types("QUANTITY", "UNIT") == ("HAS_UNIT",)
    assert admissible_types("MONEY_AMOUNT", "CURRENCY") == ("HAS_CURRENCY",)
    assert admissible_types("COMMODITY", "MONEY_AMOUNT") == ("HAS_PRICE",)
    assert admissible_types("TRANSACTION", "DATE_REF") == ("DATED_TO",)
    assert admissible_types("MONEY_AMOUNT", "TAX_TERM") == ("CHARGED_UNDER",)
    # FRACTION is a legal head for both value links, by tail label:
    assert admissible_types("FRACTION", "CURRENCY") == ("HAS_CURRENCY",)
    assert admissible_types("FRACTION", "UNIT") == ("HAS_UNIT",)
    # Not a legal ordered pair for anything:
    assert admissible_types("PERSON", "PERSON") == ()
    assert admissible_types("CURRENCY", "MONEY_AMOUNT") == ()  # head must be MONEY


def test_candidate_pairs_typed_and_gap_pruned() -> None:
    pairs = set(candidate_pairs(ENTITIES))
    assert pairs == {(0, 1), (0, 3), (0, 4), (1, 3), (3, 2), (4, 5)}
    # (3, 6) is a legal HAS_CURRENCY pair but 562 chars apart -> pruned as local.
    assert (3, 6) not in pairs
    # Nothing spurious touches the far currency word.
    assert all(6 not in pair for pair in pairs)


def test_candidate_pairs_long_family_not_gap_pruned() -> None:
    # A PERSON far from the TRANSACTION is still a PARTY_OF candidate (no cap).
    ents = [(0, 8, "PERSON"), (900, 912, "TRANSACTION")]
    assert candidate_pairs(ents) == [(0, 1)]


def test_local_gap_cap_boundary() -> None:
    # gap exactly at the cap is kept; one over is dropped.
    at = [(0, 10, "MONEY_AMOUNT"), (510, 518, "CURRENCY")]  # gap 500
    over = [(0, 10, "MONEY_AMOUNT"), (511, 519, "CURRENCY")]  # gap 501
    assert candidate_pairs(at) == [(0, 1)]
    assert candidate_pairs(over) == []


def test_label_candidates_assigns_gold_then_no_relation() -> None:
    labeled = {(h, t): ty for h, t, ty in label_candidates(ENTITIES, GOLD)}
    assert labeled == {
        (0, 1): NO_RELATION,  # a candidate the gold does not license
        (0, 3): "PAID_BY",
        (0, 4): "PARTY_OF",
        (1, 3): "HAS_PRICE",
        (3, 2): "HAS_CURRENCY",
        (4, 5): "DATED_TO",
    }


def test_uncovered_relations_is_the_recall_guard() -> None:
    # Every gold relation is a generated candidate: the guard is empty.
    assert uncovered_relations(ENTITIES, GOLD) == []
    # A relation whose pair the cap removed is reported, not silently dropped.
    capped = [(3, 6, "HAS_CURRENCY")]
    assert uncovered_relations(ENTITIES, capped) == [(3, 6, "HAS_CURRENCY")]


OFFSETS = [(0, 0), (0, 9), (10, 17), (18, 19), (0, 0)]  # <s> tok tok tok </s>


def test_char_span_to_token_range() -> None:
    assert char_span_to_token_range(OFFSETS, 0, 9) == (1, 2)
    assert char_span_to_token_range(OFFSETS, 0, 17) == (1, 3)  # two tokens
    assert char_span_to_token_range(OFFSETS, 10, 19) == (2, 4)


def test_char_span_out_of_window_or_in_gap_is_none() -> None:
    assert char_span_to_token_range(OFFSETS, 100, 110) is None  # truncated away
    assert char_span_to_token_range(OFFSETS, 9, 10) is None  # falls between tokens


def test_window_entities_drops_and_remaps() -> None:
    # Entities 1 and 3 fall outside the token window (range None); the kept
    # entities reindex to 0,1,2 and the surviving relation is remapped.
    ents = [
        (0, 8, "PERSON"),  # 0 -> 0
        (900, 906, "COMMODITY"),  # 1 dropped (out of window)
        (30, 36, "CURRENCY"),  # 2 -> 1
        (950, 951, "MONEY_AMOUNT"),  # 3 dropped
        (37, 38, "MONEY_AMOUNT"),  # 4 -> 2
    ]
    ranges = [(1, 2), None, (3, 4), None, (5, 6)]
    rels = [
        (4, 2, "HAS_CURRENCY"),  # both kept -> (2, 1)
        (0, 3, "PAID_BY"),  # endpoint 3 dropped -> gone
    ]
    kept_ents, kept_ranges, kept_rels, old2new = window_entities(ents, rels, ranges)
    assert kept_ents == [(0, 8, "PERSON"), (30, 36, "CURRENCY"), (37, 38, "MONEY_AMOUNT")]
    assert kept_ranges == [(1, 2), (3, 4), (5, 6)]
    assert kept_rels == [(2, 1, "HAS_CURRENCY")]
    assert old2new == {0: 0, 2: 1, 4: 2}


def test_window_entities_noop_when_all_fit() -> None:
    # The gold case: every entity has a range, so nothing is dropped or reindexed.
    ranges = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14)]
    kept_ents, _, kept_rels, old2new = window_entities(ENTITIES, GOLD, ranges)
    assert kept_ents == ENTITIES
    assert kept_rels == GOLD
    assert old2new == {i: i for i in range(len(ENTITIES))}


def test_admissible_mask_matches_types() -> None:
    label2id, _ = relation_label_maps()
    mask = admissible_mask("PERSON", "MONEY_AMOUNT")
    allowed = {lab for lab, on in zip(RELATION_LABELS, mask, strict=True) if on}
    assert allowed == {NO_RELATION, "PAID_BY", "PAID_TO"}
    # id 0 (NO_RELATION) is always allowed.
    assert mask[label2id[NO_RELATION]] is True


# --- 8b attribute apposition: a signalement with a person, trade and age -----
ATTR_ENTITIES = [
    (0, 10, "PERSON"),  # 0  the registrant
    (11, 17, "OCCUPATION"),  # 1  his trade (gap 1)
    (25, 27, "AGE"),  # 2  ἐτῶν N (gap 8)
    (900, 906, "OCCUPATION"),  # 3  a far trade in another clause (>500 away)
]
ATTR_GOLD = [
    (0, 1, "HAS_OCCUPATION"),
    (0, 2, "HAS_AGE"),
]


def test_attribute_signatures_are_admissible() -> None:
    # Both subject labels reach both attributes, each with a single type.
    assert admissible_types("PERSON", "OCCUPATION") == ("HAS_OCCUPATION",)
    assert admissible_types("PERSON", "AGE") == ("HAS_AGE",)
    assert admissible_types("PERSON_ROLE", "OCCUPATION") == ("HAS_OCCUPATION",)
    assert admissible_types("PERSON_ROLE", "AGE") == ("HAS_AGE",)
    # OCCUPATION still heads HAS_QUANTITY (a counted category), unchanged.
    assert admissible_types("OCCUPATION", "QUANTITY") == ("HAS_QUANTITY",)


def test_attribute_candidates_and_local_gap_cap() -> None:
    pairs = set(candidate_pairs(ATTR_ENTITIES))
    assert (0, 1) in pairs  # PERSON -> OCCUPATION (near)
    assert (0, 2) in pairs  # PERSON -> AGE
    # The far OCCUPATION (890 chars) is gap-pruned: the appositions are local.
    assert (0, 3) not in pairs


def test_attribute_recall_guard_holds() -> None:
    assert uncovered_relations(ATTR_ENTITIES, ATTR_GOLD) == []
