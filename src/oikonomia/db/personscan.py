"""Attribute gender + guardian status to every model-extracted PERSON span.

The relation-free half of the women finding. Where :mod:`oikonomia.db.parties`
needs ``PARTY_OF`` edges (a relation model) to find *principals*, this layer runs
over the raw NER PERSON spans — so it works today, on the corpus-scale reading
(``ner_corpus.jsonl``), with no relation model. For each PERSON span it:

1. **splits** the blob (:mod:`oikonomia.db.names`) to isolate the person's own
   name from the patronymic — gender must read the head, not the father;
2. **genders** the head with the precision-ordered rules
   (:mod:`oikonomia.db.persons`), plus a feminine-ethnic fallback (``Περσίνη``);
3. **types the guardian formula** in the following text as ``with`` / ``without``
   / ``none`` — the μετὰ-vs-χωρὶς-κυρίου axis the autonomy finding turns on.

Every row keeps the head, the father, the rule-of-record for the gender, and the
``(stem, char-span)`` provenance, so each attribution is auditable against the
document. Deterministic and GPU-free.
"""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel

from oikonomia.db.facts import Ent
from oikonomia.db.names import parse_person_name
from oikonomia.db.persons import GenderGuess, classify_gender, guardian_status

PERSON = "PERSON"

# How far past the name to read for the guardian frame. Wider than the party
# scan's 44: a model PERSON span sometimes stops at the head, so the μετὰ/χωρὶς
# κυρίου formula can sit a few words further on (past the patronymic).
_AFTER_WINDOW = 60


class PersonMeta(NamedTuple):
    """Per-document metadata joined onto every person row (date pre-resolved)."""

    stem: str
    tm_id: str
    date_mid: float | None
    century: int | None
    bin50: int | None
    place_pleiades: int | None
    genres: str


class PersonObservation(BaseModel):
    """One gendered PERSON mention, traceable to a character span in a document."""

    stem: str
    tm_id: str
    person_start: int
    person_end: int
    person_text: str
    head_text: str | None
    father_text: str | None  # the patronymic — the CHILD_OF target, when present
    gender: str
    gender_basis: str
    gender_confidence: float
    guardian: str  # with | without | none — the guardian (κύριος) formula
    date_mid: float | None
    century: int | None
    bin50: int | None
    place_pleiades: int | None
    genres: str


def person_gender(head: str, after: str, fem_ethnic: bool) -> GenderGuess:
    """Gender for a head name, with a feminine-ethnic (``Περσίνη``) fallback.

    The precision-ordered rules decide first; only if they abstain does the weaker
    ethnic cue apply, so it never overrides a nomen/guardian/kin signal.
    """
    g = classify_gender(head, after)
    if g.gender == "unknown" and fem_ethnic:
        return GenderGuess("female", "ethnic", 0.7)
    return g


def assemble_persons(
    entities: list[Ent],
    text: str,
    meta: PersonMeta,
) -> list[PersonObservation]:
    """Emit one gendered row per PERSON span in a document.

    ``text`` must be the document view the spans index (``corpus.parquet``'s
    ``edited_text``), so the guardian window and the head slice line up with the
    offsets. Non-PERSON entities are ignored.
    """
    obs: list[PersonObservation] = []
    for e in entities:
        if e.label != PERSON:
            continue
        pn = parse_person_name(e.text, base=e.start)
        head = pn.head.text if pn.head else e.text
        after = text[e.end : e.end + _AFTER_WINDOW]
        g = person_gender(head, after, "fem_ethnic" in pn.flags)
        obs.append(
            PersonObservation(
                stem=meta.stem,
                tm_id=meta.tm_id,
                person_start=e.start,
                person_end=e.end,
                person_text=e.text,
                head_text=head,
                father_text=pn.father.text if pn.father else None,
                gender=g.gender,
                gender_basis=g.basis,
                gender_confidence=g.confidence,
                guardian=guardian_status(after),
                date_mid=meta.date_mid,
                century=meta.century,
                bin50=meta.bin50,
                place_pleiades=meta.place_pleiades,
                genres=meta.genres,
            )
        )
    return obs
