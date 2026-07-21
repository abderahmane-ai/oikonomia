"""Hand-computed fixtures for the char-span ↔ BIO alignment.

The offsets here are what a fast tokenizer returns for the given text (specials
as zero-length ``(0, 0)``); the expected BIO ids and decoded spans are worked
out by hand, so a regression in either direction is caught without a model.
"""

from __future__ import annotations

from oikonomia.ner.encode import (
    IGNORE_INDEX,
    align_bio,
    build_label_list,
    decode_spans,
    label_maps,
)

# Text: "Ἀπολλώνις δραχμῶν β"  (a name, a currency word, a one-char amount)
#        0........9 10.....17 18
OFFSETS = [(0, 0), (0, 9), (10, 17), (18, 19), (0, 0)]  # <s> tok tok tok </s>
ENTITIES = [(0, 9, "PERSON"), (10, 17, "CURRENCY"), (18, 19, "MONEY_AMOUNT")]
LABELS = build_label_list(["PERSON", "CURRENCY", "MONEY_AMOUNT"])
LABEL2ID, ID2LABEL = label_maps(LABELS)


def test_build_label_list_is_sorted_bio() -> None:
    assert LABELS == [
        "O",
        "B-CURRENCY",
        "I-CURRENCY",
        "B-MONEY_AMOUNT",
        "I-MONEY_AMOUNT",
        "B-PERSON",
        "I-PERSON",
    ]
    assert LABELS[0] == "O" and LABEL2ID["O"] == 0


def test_align_specials_are_ignored() -> None:
    ids = align_bio(OFFSETS, ENTITIES, LABEL2ID)
    assert ids[0] == IGNORE_INDEX and ids[-1] == IGNORE_INDEX


def test_align_single_token_entities() -> None:
    ids = align_bio(OFFSETS, ENTITIES, LABEL2ID)
    assert ID2LABEL[ids[1]] == "B-PERSON"
    assert ID2LABEL[ids[2]] == "B-CURRENCY"
    assert ID2LABEL[ids[3]] == "B-MONEY_AMOUNT"


def test_roundtrip_recovers_entities() -> None:
    ids = align_bio(OFFSETS, ENTITIES, LABEL2ID)
    assert sorted(decode_spans(ids, OFFSETS, ID2LABEL)) == sorted(ENTITIES)


def test_multi_token_entity_merges() -> None:
    # "Κροκοδίλων πόλει" as one PLACE across two tokens (space at 55-56 uncovered).
    offsets = [(0, 0), (45, 55), (56, 61), (0, 0)]
    label2id, id2label = label_maps(build_label_list(["PLACE"]))
    ids = align_bio(offsets, [(45, 61, "PLACE")], label2id)
    assert [id2label[i] if i != IGNORE_INDEX else "X" for i in ids] == [
        "X",
        "B-PLACE",
        "I-PLACE",
        "X",
    ]
    assert decode_spans(ids, offsets, id2label) == [(45, 61, "PLACE")]


def test_decode_lenient_on_leading_inside_tag() -> None:
    # An I- with no preceding B- still opens a span rather than being dropped.
    label2id, id2label = label_maps(build_label_list(["PLACE"]))
    ids = [label2id["I-PLACE"], label2id["O"]]
    offsets = [(0, 5), (6, 9)]
    assert decode_spans(ids, offsets, id2label) == [(0, 5, "PLACE")]


def test_label_outside_schema_is_skipped() -> None:
    # AGE is not in the schema: its token stays O, others unaffected.
    ids = align_bio(OFFSETS, [*ENTITIES, (10, 17, "AGE")], LABEL2ID)
    assert ID2LABEL[ids[2]] == "B-CURRENCY"  # first entity keeps the token
