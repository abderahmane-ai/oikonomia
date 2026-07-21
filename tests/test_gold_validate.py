"""Tests for gold annotation validation and offset repair.

Each case here is a defect that actually occurred in the first hand-annotated
documents, not a hypothetical.
"""

from __future__ import annotations

import json
from pathlib import Path

from oikonomia.gold.validate import (
    relocate,
    repair_document,
    validate_document,
    validate_file,
)


def _doc(text: str, entities: list[dict], relations: list[dict] | None = None) -> dict:
    return {"doc_id": "t", "text": text, "entities": entities, "relations": relations or []}


def test_inclusive_end_is_caught_and_repaired() -> None:
    """The commonest annotation error: `end` written as the last index, not past it."""
    doc = _doc("πυροῦ ἀρτάβας ιβ", [{"start": 0, "end": 4, "label": "COMMODITY", "text": "πυροῦ"}])
    problems = validate_document(doc)
    assert [p.kind for p in problems] == ["text_mismatch"]
    assert problems[0].repairable

    assert repair_document(doc) == 1
    assert doc["entities"][0] == {"start": 0, "end": 5, "label": "COMMODITY", "text": "πυροῦ"}
    assert validate_document(doc) == []


def test_single_character_span_collapses_to_empty() -> None:
    """`QUANTITY` is usually one character, so an inclusive `end` erases it entirely."""
    doc = _doc("κοτύλαι η", [{"start": 8, "end": 8, "label": "QUANTITY", "text": "η"}])
    problems = validate_document(doc)
    assert [p.kind for p in problems] == ["empty_span"]

    assert repair_document(doc) == 1
    assert doc["entities"][0]["start"] == 8
    assert doc["entities"][0]["end"] == 9
    assert validate_document(doc) == []


def test_drifted_offsets_from_a_stale_batch_are_repaired() -> None:
    """Annotating an older text leaves offsets progressively out of true."""
    text = "Αὐρήλιος Ἄμμων ἔσχον τὸ χρυσοῦ νομισμάτιον ἓν"
    doc = _doc(
        text,
        [
            {"start": 0, "end": 14, "label": "PERSON", "text": "Αὐρήλιος Ἄμμων"},
            {"start": 26, "end": 32, "label": "CURRENCY", "text": "χρυσοῦ"},  # drifted +2
        ],
    )
    assert repair_document(doc) == 1  # the PERSON span was already right
    assert text[doc["entities"][1]["start"] : doc["entities"][1]["end"]] == "χρυσοῦ"


def test_repeated_name_relocates_to_the_nearest_mention() -> None:
    """A name repeats; repair must not collapse every mention onto the first."""
    text = "Ἀρτεμίδωρος ἰατρός ιθ Ἀρτεμίδωρος ἐπιστολογράφος"
    second = text.rindex("Ἀρτεμίδωρος")
    assert relocate(text, "Ἀρτεμίδωρος", hint=second - 1) == second
    assert relocate(text, "Ἀρτεμίδωρος", hint=0) == 0


def test_reversed_relation_is_reported_not_repaired() -> None:
    """Direction is a judgment call against the guidelines, so it is never auto-fixed."""
    doc = _doc(
        "πυροῦ ιβ",
        [
            {"start": 0, "end": 5, "label": "COMMODITY", "text": "πυροῦ"},
            {"start": 6, "end": 8, "label": "QUANTITY", "text": "ιβ"},
        ],
        [{"head": 1, "tail": 0, "type": "HAS_QUANTITY"}],
    )
    problems = validate_document(doc)
    assert [p.kind for p in problems] == ["relation_direction"]
    assert "reversed" in problems[0].detail
    assert repair_document(doc) == 0  # spans are fine; relations untouched


def test_correct_relation_direction_passes() -> None:
    doc = _doc(
        "πυροῦ ιβ",
        [
            {"start": 0, "end": 5, "label": "COMMODITY", "text": "πυροῦ"},
            {"start": 6, "end": 8, "label": "QUANTITY", "text": "ιβ"},
        ],
        [{"head": 0, "tail": 1, "type": "HAS_QUANTITY"}],
    )
    assert validate_document(doc) == []


def test_party_of_must_point_at_a_transaction_trigger() -> None:
    """PARTY_OF is anchored on an explicit TRANSACTION span, not on the goods."""
    ents = [
        {"start": 0, "end": 8, "label": "PERSON", "text": "ὁμολογεῖ"},
        {"start": 9, "end": 15, "label": "COMMODITY", "text": "οἰκίας"},
    ]
    bad = _doc("ὁμολογεῖ οἰκίας", ents, [{"head": 0, "tail": 1, "type": "PARTY_OF"}])
    assert [p.kind for p in validate_document(bad)] == ["relation_direction"]

    good = _doc(
        "ὁμολογεῖ Νεχούτης",
        [
            {"start": 0, "end": 8, "label": "TRANSACTION", "text": "ὁμολογεῖ"},
            {"start": 9, "end": 17, "label": "PERSON", "text": "Νεχούτης"},
        ],
        [{"head": 1, "tail": 0, "type": "PARTY_OF"}],
    )
    assert validate_document(good) == []


def test_bare_fraction_links_to_currency_like_an_amount() -> None:
    """A Byzantine rent of `𐅷` of a solidus is a whole amount, not a defect."""
    doc = _doc(
        "χρυσοῦ νομισματίου 𐅷",
        [
            {"start": 7, "end": 18, "label": "CURRENCY", "text": "νομισματίου"},
            {"start": 19, "end": 20, "label": "FRACTION", "text": "𐅷"},
        ],
        [{"head": 1, "tail": 0, "type": "HAS_CURRENCY"}],
    )
    assert validate_document(doc) == []


def test_counted_people_may_carry_a_quantity() -> None:
    """`ἱερεῖς β` — HAS_QUANTITY accepts OCCUPATION, not only COMMODITY."""
    doc = _doc(
        "ἱερεῖς β",
        [
            {"start": 0, "end": 6, "label": "OCCUPATION", "text": "ἱερεῖς"},
            {"start": 7, "end": 8, "label": "QUANTITY", "text": "β"},
        ],
        [{"head": 0, "tail": 1, "type": "HAS_QUANTITY"}],
    )
    assert validate_document(doc) == []


def test_out_of_range_relation_index() -> None:
    doc = _doc(
        "πυροῦ",
        [{"start": 0, "end": 5, "label": "COMMODITY", "text": "πυροῦ"}],
        [{"head": 0, "tail": 7, "type": "HAS_QUANTITY"}],
    )
    assert [p.kind for p in validate_document(doc)] == ["relation_index"]


def test_unfindable_text_is_left_alone_for_a_human(tmp_path: Path) -> None:
    """A span whose text is not in the document must keep failing, not be moved."""
    doc = _doc("πυροῦ ιβ", [{"start": 0, "end": 3, "label": "COMMODITY", "text": "κριθῆς"}])
    assert repair_document(doc) == 0
    problems = validate_document(doc)
    assert [p.kind for p in problems] == ["text_mismatch"]
    assert not problems[0].repairable


def test_validate_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "annotated.jsonl"
    doc = _doc("κοτύλαι η", [{"start": 8, "end": 8, "label": "QUANTITY", "text": "η"}])
    path.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")

    assert not validate_file(path).ok
    fixed = validate_file(path, fix=True)
    assert fixed.ok and fixed.n_repaired == 1
    # The repair is persisted, and the file still parses.
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["entities"][0]["end"] == 9
