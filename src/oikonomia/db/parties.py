"""Assemble a labeled document into *party* rows — the people who are principals
to an economic transaction, each with an attributed gender.

This is the backbone of the "women as economic principals" finding (deliverable
#3). Where :mod:`oikonomia.db.facts` walks the graph for money, this walks it for
*people who act*: every PERSON that is a party to a transaction (``PARTY_OF``), or
the giver/receiver of an amount (``PAID_BY`` / ``PAID_TO``). Onto each we attach:

- a **gender** attribution with its rule-of-record (:mod:`oikonomia.db.persons`);
- whether a **guardian** (``κύριος``) formula accompanies them — the legal marker
  that a woman is transacting, itself part of the finding;
- the **role** (party / payer / payee) and the transaction term it hangs on;
- the document's date/century/place/genre and ``(doc, char-span)`` provenance.

Deterministic and GPU-free. The person spans + relations come from *some* labeler
(the human gold, or the rule labeler, or later the trained model); this layer only
normalizes and attributes, and every attribution carries the basis that produced
it, so a papyrologist can audit each row against the text.
"""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel

from oikonomia.db.facts import Ent, Rel
from oikonomia.db.persons import classify_gender, has_guardian

PERSON = "PERSON"
TRANSACTION = "TRANSACTION"

# principal relations → the role the PERSON head plays
_ROLE_OF = {"PARTY_OF": "party", "PAID_BY": "payer", "PAID_TO": "payee"}

# how far past the name to read for guardian / kin frames
_AFTER_WINDOW = 44


class PartyMeta(NamedTuple):
    """Per-document metadata joined onto every party row (date pre-resolved)."""

    doc_id: str
    date_mid: float | None
    century: int | None
    bin50: int | None
    place_pleiades: int | None
    genres: str


class PartyObservation(BaseModel):
    """One principal (a named party to a transaction), traceable to a span."""

    doc_id: str
    person_start: int
    person_end: int
    person_text: str
    gender: str
    gender_basis: str
    gender_confidence: float
    guardian_present: bool
    roles: str  # sorted, "|"-joined: party | payer | payee
    transaction_term: str | None
    date_mid: float | None
    century: int | None
    bin50: int | None
    place_pleiades: int | None
    genres: str
    confidence: float  # strongest principal-relation confidence for this person


def assemble_parties(
    entities: list[Ent],
    relations: list[Rel],
    text: str,
    meta: PartyMeta,
) -> list[PartyObservation]:
    """Emit one row per PERSON that is a principal (party / payer / payee).

    A person in several roles collapses to one row carrying all its roles.
    PERSON_ROLE principals (unnamed roles like "the lessor") are skipped — there is
    no name to gender — so the table holds only namable principals.
    """
    # gather, per person-entity index, the roles it plays and the confidences
    roles: dict[int, set[str]] = {}
    confs: dict[int, list[float]] = {}
    tx_term: dict[int, str] = {}
    for r in relations:
        role = _ROLE_OF.get(r.type)
        if role is None:
            continue
        pi = r.head
        if not (0 <= pi < len(entities)) or entities[pi].label != PERSON:
            continue
        roles.setdefault(pi, set()).add(role)
        confs.setdefault(pi, []).append(r.confidence)
        if r.type == "PARTY_OF" and 0 <= r.tail < len(entities):
            tail = entities[r.tail]
            if tail.label == TRANSACTION and pi not in tx_term:
                tx_term[pi] = tail.text

    obs: list[PartyObservation] = []
    for pi in sorted(roles):
        p = entities[pi]
        after = text[p.end : p.end + _AFTER_WINDOW]
        g = classify_gender(p.text, after)
        obs.append(
            PartyObservation(
                doc_id=meta.doc_id,
                person_start=p.start,
                person_end=p.end,
                person_text=p.text,
                gender=g.gender,
                gender_basis=g.basis,
                gender_confidence=g.confidence,
                guardian_present=has_guardian(after),
                roles="|".join(sorted(roles[pi])),
                transaction_term=tx_term.get(pi),
                date_mid=meta.date_mid,
                century=meta.century,
                bin50=meta.bin50,
                place_pleiades=meta.place_pleiades,
                genres=meta.genres,
                confidence=max(confs[pi]),
            )
        )
    return obs
