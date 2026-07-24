"""Hand-built fixture for party (principal) assembly (Phase 9).

One synthetic lease clause — a woman leasing with her guardian and a man paying —
with the PARTY_OF / PAID_BY / PAID_TO graph wired by hand, so role collapse,
gender attribution, the guardian flag and the transaction term are all checked
without a labeler or the corpus.
"""

from __future__ import annotations

from oikonomia.db.facts import Ent, Rel
from oikonomia.db.parties import PartyMeta, assemble_parties

# "μίσθωσις Ταῆσις μετὰ κυρίου πρὸς Ἀπολλώνιον δραχμὰς κ"
# (a lease: Thaesis, with her guardian, to Apollonios, 20 drachmas)
TEXT = "μίσθωσις Ταῆσις μετὰ κυρίου πρὸς Ἀπολλώνιον δραχμὰς κ"
ENTS = [
    Ent(0, 8, "TRANSACTION", "μίσθωσις", "lease", 0.9),  # 0
    Ent(9, 15, "PERSON", "Ταῆσις", None, 0.8),  # 1  lessor (female: guardian)
    Ent(33, 43, "PERSON", "Ἀπολλώνιον", None, 0.8),  # 2  lessee (male: gazetteer)
    Ent(44, 52, "MONEY_AMOUNT", "δραχμὰς κ", None, 0.8),  # 3
]
RELS = [
    Rel(1, 0, "PARTY_OF", 0.6),  # Thaesis  -> lease
    Rel(2, 0, "PARTY_OF", 0.6),  # Apollonios -> lease
    Rel(1, 3, "PAID_TO", 0.5),  # Thaesis receives the amount (payee)
    Rel(2, 3, "PAID_BY", 0.5),  # Apollonios pays (payer)
]
META = PartyMeta(doc_id="42", date_mid=150.0, century=2, bin50=150, place_pleiades=None, genres="lease")


def _by_name(rows: list, name: str) -> object:
    return next(r for r in rows if r.person_text == name)


def test_emits_one_row_per_named_principal() -> None:
    rows = assemble_parties(ENTS, RELS, TEXT, META)
    assert {r.person_text for r in rows} == {"Ταῆσις", "Ἀπολλώνιον"}


def test_roles_collapse_and_sort_per_person() -> None:
    rows = assemble_parties(ENTS, RELS, TEXT, META)
    assert _by_name(rows, "Ταῆσις").roles == "party|payee"
    assert _by_name(rows, "Ἀπολλώνιον").roles == "party|payer"


def test_gender_and_guardian_attributed_from_the_frame() -> None:
    rows = assemble_parties(ENTS, RELS, TEXT, META)
    thaesis = _by_name(rows, "Ταῆσις")
    assert thaesis.gender == "female" and thaesis.gender_basis == "guardian"
    assert thaesis.guardian_present is True
    apoll = _by_name(rows, "Ἀπολλώνιον")
    assert apoll.gender == "male"
    assert apoll.guardian_present is False


def test_transaction_term_and_metadata_carried() -> None:
    rows = assemble_parties(ENTS, RELS, TEXT, META)
    thaesis = _by_name(rows, "Ταῆσις")
    assert thaesis.transaction_term == "μίσθωσις"
    assert thaesis.century == 2 and thaesis.genres == "lease"
    assert thaesis.confidence == 0.6  # strongest of its principal relations


def test_person_role_principals_are_skipped_no_name_to_gender() -> None:
    # A PERSON_ROLE party (an unnamed "lessor") carries no name to gender, so it
    # is not emitted — the table holds only namable principals.
    ents = [*ENTS, Ent(60, 70, "PERSON_ROLE", "μεμισθωκότος", "lessor", 0.7)]
    rels = [*RELS, Rel(4, 0, "PARTY_OF", 0.6)]
    rows = assemble_parties(ents, rels, TEXT, META)
    assert all(r.person_text != "μεμισθωκότος" for r in rows)


def test_no_principals_when_no_party_relations() -> None:
    assert assemble_parties(ENTS, [], TEXT, META) == []
