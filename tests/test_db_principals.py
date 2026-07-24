"""Hand-built fixture for principal assembly from RE edges + the person table (step 8).

A synthetic sale clause — a woman (with guardian) selling to a man — with the
PARTY_OF / PAID_* graph wired by hand and the gender join supplied as it would
come from ``persons.parquet``. Checks role collapse, the deal-type tag, the
gender/guardian/father join by span, and that PERSON_ROLE principals are skipped.
"""

from __future__ import annotations

from oikonomia.db.facts import Ent, Rel
from oikonomia.db.principals import (
    PersonGender,
    PrincipalMeta,
    assemble_principals,
)

# "πρᾶσις Ταῆσις μετὰ κυρίου Ἡρώδου πρὸς Ἀπολλώνιον δραχμὰς κ"
ENTS = [
    Ent(0, 6, "TRANSACTION", "πρᾶσις", "sale", 0.9),  # 0
    Ent(7, 13, "PERSON", "Ταῆσις", None, 0.8),  # 1  seller (female, with guardian)
    Ent(38, 48, "PERSON", "Ἀπολλώνιον", None, 0.8),  # 2  buyer (male)
    Ent(49, 58, "MONEY_AMOUNT", "δραχμὰς κ", None, 0.8),  # 3
]
RELS = [
    Rel(1, 0, "PARTY_OF", 0.71),  # Ταῆσις -> sale
    Rel(2, 0, "PARTY_OF", 0.66),  # Ἀπολλώνιον -> sale
    Rel(1, 3, "PAID_TO", 0.40),  # Ταῆσις receives (payee)
    Rel(2, 3, "PAID_BY", 0.35),  # Ἀπολλώνιον pays (payer)
]
# The gender join as it arrives from persons.parquet, keyed by PERSON span.
GENDER = {
    (7, 13): PersonGender("female", "guardian", 0.95, "with", "Ταῆσις", None),
    (38, 48): PersonGender("male", "gazetteer", 0.9, "none", "Ἀπολλώνιον", None),
}
META = PrincipalMeta(
    stem="s1", tm_id="42", date_mid=150.0, century=2, bin50=150,
    place_pleiades=None, genres="sale|contract",
)


def _by_name(rows: list, name: str) -> object:
    return next(r for r in rows if r.person_text == name)


def test_one_row_per_named_principal_with_deal_type() -> None:
    rows = assemble_principals(ENTS, RELS, GENDER, META)
    assert {r.person_text for r in rows} == {"Ταῆσις", "Ἀπολλώνιον"}
    assert all(r.deal_type == "sale" for r in rows)  # primary genre


def test_roles_collapse_and_sort() -> None:
    rows = assemble_principals(ENTS, RELS, GENDER, META)
    assert _by_name(rows, "Ταῆσις").roles == "party|payee"
    assert _by_name(rows, "Ἀπολλώνιον").roles == "party|payer"


def test_gender_and_guardian_joined_from_the_person_table() -> None:
    rows = assemble_principals(ENTS, RELS, GENDER, META)
    thaesis = _by_name(rows, "Ταῆσις")
    assert thaesis.gender == "female" and thaesis.gender_basis == "guardian"
    assert thaesis.guardian == "with"  # the typed μετὰ-κυρίου formula, not a bool
    assert _by_name(rows, "Ἀπολλώνιον").gender == "male"


def test_transaction_term_and_confidence_carried() -> None:
    rows = assemble_principals(ENTS, RELS, GENDER, META)
    thaesis = _by_name(rows, "Ταῆσις")
    assert thaesis.transaction_term == "πρᾶσις"
    assert thaesis.confidence == 0.71  # strongest of its principal edges
    assert thaesis.century == 2


def test_missing_gender_join_does_not_drop_the_principal() -> None:
    # A principal whose span is absent from the person table is still emitted,
    # gender "unknown" — the assembler never loses a principal on a missing join.
    rows = assemble_principals(ENTS, RELS, {}, META)
    assert {r.person_text for r in rows} == {"Ταῆσις", "Ἀπολλώνιον"}
    assert all(r.gender == "unknown" and r.guardian == "none" for r in rows)


def test_person_role_principals_are_skipped() -> None:
    ents = [*ENTS, Ent(60, 70, "PERSON_ROLE", "πωλητοῦ", "seller", 0.7)]
    rels = [*RELS, Rel(4, 0, "PARTY_OF", 0.6)]
    rows = assemble_principals(ents, rels, GENDER, META)
    assert all(r.person_text != "πωλητοῦ" for r in rows)


def test_no_principals_without_principal_relations() -> None:
    assert assemble_principals(ENTS, [], GENDER, META) == []


def test_deal_type_parses_the_canonical_json_genre_string() -> None:
    # The corpus stores genres as a JSON-array string; the deal type is the first.
    meta = META._replace(genres='["lease", "contract"]')
    rows = assemble_principals(ENTS, RELS, GENDER, meta)
    assert all(r.deal_type == "lease" for r in rows)
    # empty / unparseable genres degrade to "?"
    assert assemble_principals(ENTS, RELS, GENDER, META._replace(genres="[]"))[0].deal_type == "?"
    assert assemble_principals(ENTS, RELS, GENDER, META._replace(genres=""))[0].deal_type == "?"
