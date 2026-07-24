"""Hand-computed fixtures for the model-span gender/guardian assembler.

Each doc is a small constructed text with a PERSON span placed by ``str.index``,
so the offsets are real and the guardian window, head split and gender rule are
exercised end to end without a model. The with-vs-without guardian typing is the
autonomy finding's axis, so it is pinned explicitly.
"""

from __future__ import annotations

from oikonomia.db.facts import Ent
from oikonomia.db.personscan import PersonMeta, assemble_persons

_META = PersonMeta(
    stem="1", tm_id="42", date_mid=100.0, century=2, bin50=100,
    place_pleiades=736, genres="sale",
)


def _person(text: str, surface: str) -> list:
    s = text.index(surface)
    return assemble_persons([Ent(s, s + len(surface), "PERSON", surface, None, 1.0)], text, _META)


def test_with_guardian_is_female_and_typed_with() -> None:
    text = "ἔτους ιδ Θαῆσις Ὧρου μετὰ κυρίου τοῦ ἀνδρὸς δραχμὰς"
    (r,) = _person(text, "Θαῆσις Ὧρου")
    assert r.gender == "female" and r.gender_basis == "guardian"
    assert r.guardian == "with"
    assert r.head_text == "Θαῆσις" and r.father_text == "Ὧρου"


def test_without_guardian_is_typed_without() -> None:
    text = "ὁμολογεῖ Θαῆσις χωρὶς κυρίου χρηματίζουσα ἀποδοῦναι"
    (r,) = _person(text, "Θαῆσις")
    assert r.gender == "female"
    assert r.guardian == "without"


def test_male_nomen_no_guardian() -> None:
    text = "Αὐρήλιος Ἀπολλώνιος ἀγορανόμος ὁμολογεῖ"
    (r,) = _person(text, "Αὐρήλιος Ἀπολλώνιος")
    assert r.gender == "male" and r.gender_basis == "nomen"
    assert r.guardian == "none"
    assert r.head_text == "Αὐρήλιος" and r.father_text == "Ἀπολλώνιος"


def test_feminine_ethnic_fallback() -> None:
    # No stronger signal fires; Περσίναι ("Persian woman") supplies a female cue.
    text = "παρὰ Τοτοέους Περσίναι δάνειον"
    (r,) = _person(text, "Τοτοέους Περσίναι")
    assert r.gender == "female" and r.gender_basis == "ethnic"
    assert r.father_text is None  # the ethnic word is not filiation


def test_provenance_fields_carried() -> None:
    text = "ἀπέδοτο Ἀγαθῖνος Φιλοξένου δραχμῶν"
    s = text.index("Ἀγαθῖνος Φιλοξένου")
    (r,) = _person(text, "Ἀγαθῖνος Φιλοξένου")
    assert r.stem == "1" and r.tm_id == "42"
    assert r.person_start == s and r.person_end == s + len("Ἀγαθῖνος Φιλοξένου")
    assert r.century == 2 and r.place_pleiades == 736 and r.genres == "sale"
    assert text[r.person_start : r.person_end] == r.person_text


def test_non_person_entities_ignored() -> None:
    text = "Ἀγαθῖνος ἐν Ὀξυρύγχων"
    ents = [
        Ent(0, 8, "PERSON", "Ἀγαθῖνος", None, 1.0),
        Ent(12, 21, "PLACE", "Ὀξυρύγχων", None, 1.0),
    ]
    rows = assemble_persons(ents, text, _META)
    assert len(rows) == 1 and rows[0].person_text == "Ἀγαθῖνος"
