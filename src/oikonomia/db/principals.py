"""Women as principals across deal types — the relation-driven women finding (step 8).

Where :mod:`oikonomia.db.personscan` genders *every* PERSON mention (the autonomy
finding, steps 4-6), this layer keeps only the people the transaction actually
turns on: the **principals**. A principal is a PERSON that the relation model
links into the deal — a party to it (``PARTY_OF`` → a TRANSACTION term), or the
giver/receiver of an amount (``PAID_BY`` / ``PAID_TO`` → a MONEY_AMOUNT). Onto
each we join the *already-validated* gender + guardian + patronymic from the
person table (steps 3-4), rather than re-deriving them — so the principal share
is consistent, edge for edge, with the autonomy curve.

The extraction engine is the trained pair: the NER model supplies the PERSON /
TRANSACTION / MONEY spans (``ner_corpus.jsonl``), the saved RE model supplies the
``PARTY_OF`` / ``PAID_*`` edges (``re_corpus.jsonl``, end-to-end PARTY_OF ≈ 0.62).
This module is the deterministic, GPU-free assembler that turns those edges plus
the gendered person table into one row per principal, tagged with its deal type
(the document genre) and full ``(stem, char-span)`` provenance.
"""

from __future__ import annotations

import json
from typing import NamedTuple

from pydantic import BaseModel

from oikonomia.db.facts import Ent, Rel

PERSON = "PERSON"
TRANSACTION = "TRANSACTION"

# principal relations → the role the PERSON head plays in the deal
_ROLE_OF = {"PARTY_OF": "party", "PAID_BY": "payer", "PAID_TO": "payee"}


class PersonGender(NamedTuple):
    """The validated gender attribution for one PERSON span (from the person table)."""

    gender: str
    gender_basis: str
    gender_confidence: float
    guardian: str  # with | without | none — the μετὰ/χωρὶς-κυρίου formula
    head_text: str | None
    father_text: str | None  # the patronymic — the CHILD_OF target, when present


class PrincipalMeta(NamedTuple):
    """Per-document metadata joined onto every principal row (date pre-resolved)."""

    stem: str
    tm_id: str
    date_mid: float | None
    century: int | None
    bin50: int | None
    place_pleiades: int | None
    genres: str


# The gender attribution used when a principal PERSON span is absent from the
# person table (should not happen — both come from the same NER run — but the
# assembler must never drop a principal on a missing join).
_UNKNOWN = PersonGender("unknown", "none", 0.0, "none", None, None)


class Principal(BaseModel):
    """One principal (a PERSON the deal turns on), gendered and deal-typed."""

    stem: str
    tm_id: str
    person_start: int
    person_end: int
    person_text: str
    head_text: str | None
    father_text: str | None
    gender: str
    gender_basis: str
    gender_confidence: float
    guardian: str  # with | without | none
    roles: str  # sorted, "|"-joined: party | payer | payee
    transaction_term: str | None
    deal_type: str  # the document's primary genre — the "deal type" axis
    date_mid: float | None
    century: int | None
    bin50: int | None
    place_pleiades: int | None
    genres: str
    confidence: float  # strongest principal-relation confidence for this person


def _primary_genre(genres: str) -> str:
    """The document's primary genre — the "deal type" axis.

    Genres arrive as the canonical JSON-array string (``'["contract", "loan"]'``)
    the corpus stores; the first element is the primary deal type. Falls back to a
    ``|``-split for the plainer gold/party representation, and to ``"?"`` when the
    genre is empty or unparseable.
    """
    if not genres:
        return "?"
    g = genres.strip()
    if g.startswith("["):
        try:
            arr = json.loads(g)
        except (json.JSONDecodeError, ValueError):
            arr = []
        return (str(arr[0]) if arr else "?") or "?"
    return (g.split("|")[0] if g else "?") or "?"


def assemble_principals(
    entities: list[Ent],
    relations: list[Rel],
    gender_by_span: dict[tuple[int, int], PersonGender],
    meta: PrincipalMeta,
) -> list[Principal]:
    """Emit one row per PERSON that the relation model makes a principal.

    A person in several roles (a party who is also the payer) collapses to one
    row carrying every role. Only PERSON principals are emitted — a ``PARTY_OF``
    headed by an unnamed ``PERSON_ROLE`` ("the lessor") has no name to gender, so
    it is skipped, exactly as in :mod:`oikonomia.db.parties`. Gender/guardian/
    father come from ``gender_by_span`` (the person table), keyed by the PERSON's
    exact ``(start, end)`` span — the same NER span both tables share.
    """
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

    deal_type = _primary_genre(meta.genres)
    obs: list[Principal] = []
    for pi in sorted(roles):
        p = entities[pi]
        g = gender_by_span.get((p.start, p.end), _UNKNOWN)
        obs.append(
            Principal(
                stem=meta.stem,
                tm_id=meta.tm_id,
                person_start=p.start,
                person_end=p.end,
                person_text=p.text,
                head_text=g.head_text,
                father_text=g.father_text,
                gender=g.gender,
                gender_basis=g.gender_basis,
                gender_confidence=g.gender_confidence,
                guardian=g.guardian,
                roles="|".join(sorted(roles[pi])),
                transaction_term=tx_term.get(pi),
                deal_type=deal_type,
                date_mid=meta.date_mid,
                century=meta.century,
                bin50=meta.bin50,
                place_pleiades=meta.place_pleiades,
                genres=meta.genres,
                confidence=max(confs[pi]),
            )
        )
    return obs
