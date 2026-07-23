"""Assemble a labeled document into monetary fact rows — the atomic economic fact.

One row per MONEY_AMOUNT that carries a currency: its normalized value, and
whatever the relation graph attaches to it — the commodity it prices (HAS_PRICE),
that commodity's quantity+unit (HAS_QUANTITY/HAS_UNIT, giving a per-unit price),
and the tax it discharges (CHARGED_UNDER). Every row keeps ``(tm_id, char-span)``
so a historian can open the papyrus and check it.

This is deterministic graph-walking, not learning: it reads the entities/relations
some labeler already produced and the corpus's decoded ``<num>`` values, and joins
the document's HGV date and Pleiades place. Noise in, noise out — the point is
that the noise is *auditable and filterable* (by confidence, by resolvability),
which a black-box graph is not.
"""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel

from oikonomia.db.dates import century, date_mid, half_century_start
from oikonomia.db.money import normalize_amount

MONEY_AMOUNT = "MONEY_AMOUNT"
COMMODITY = "COMMODITY"


class Ent(NamedTuple):
    """A labeled entity, decoupled from any labeler's own class."""

    start: int
    end: int
    label: str
    text: str
    entry_id: str | None
    confidence: float


class Rel(NamedTuple):
    """A labeled relation, as indices into the entity list."""

    head: int
    tail: int
    type: str
    confidence: float


class DocMeta(NamedTuple):
    """The corpus metadata joined onto every fact from one document."""

    tm_id: str
    date_lo: float | None
    date_hi: float | None
    place_pleiades: int | None
    genres: str


class MonetaryObservation(BaseModel):
    """One monetary fact, traceable to a character span in one document."""

    tm_id: str
    amount_start: int
    amount_end: int
    amount_text: str
    value_num: float | None
    currency_id: str | None
    system: str
    value_base: float | None  # in drachmas (silver) or nomismata (gold) — group by system
    commodity_id: str | None
    quantity: float | None
    unit_id: str | None
    unit_price_base: float | None  # value_base / quantity, when both known
    tax_id: str | None
    confidence: float
    date_lo: float | None
    date_hi: float | None
    date_mid: float | None
    century: int | None
    bin50: int | None
    place_pleiades: int | None
    genres: str


def value_for(start: int, end: int, value_by_span: dict[tuple[int, int], float]) -> float | None:
    """Decoded ``<num>`` value covering an entity span (exact, else contained)."""
    exact = value_by_span.get((start, end))
    if exact is not None:
        return exact
    for (s, e), v in value_by_span.items():
        if start <= s and e <= end:  # a numeral sitting inside the entity span
            return v
    return None


def assemble_monetary(
    entities: list[Ent],
    relations: list[Rel],
    value_by_span: dict[tuple[int, int], float],
    meta: DocMeta,
) -> list[MonetaryObservation]:
    """Emit a monetary observation for each currency-bearing MONEY_AMOUNT.

    A MONEY_AMOUNT with no HAS_CURRENCY is skipped — without a denomination its
    numeral cannot be normalized, so it is not yet a comparable economic fact.
    """
    # index relations by (type, head) and (type, tail) for O(1) graph walks
    by_head: dict[tuple[str, int], list[int]] = {}  # -> tail indices
    by_tail: dict[tuple[str, int], list[int]] = {}  # -> head indices
    for r in relations:
        by_head.setdefault((r.type, r.head), []).append(r.tail)
        by_tail.setdefault((r.type, r.tail), []).append(r.head)

    def first(m: dict[tuple[str, int], list[int]], key: tuple[str, int]) -> int | None:
        got = m.get(key)
        return got[0] if got else None

    mid = date_mid(meta.date_lo, meta.date_hi)
    obs: list[MonetaryObservation] = []
    for mi, m in enumerate(entities):
        if m.label != MONEY_AMOUNT:
            continue
        cur_i = first(by_head, ("HAS_CURRENCY", mi))
        if cur_i is None:
            continue  # no denomination -> not yet a comparable fact
        value_num = value_for(m.start, m.end, value_by_span)
        money = normalize_amount(value_num, entities[cur_i].entry_id)

        commodity_id = quantity = unit_id = unit_price = None
        com_i = first(by_tail, ("HAS_PRICE", mi))  # COMMODITY -> this amount
        if com_i is not None:
            commodity_id = entities[com_i].entry_id
            q_i = first(by_head, ("HAS_QUANTITY", com_i))
            if q_i is not None:
                quantity = value_for(entities[q_i].start, entities[q_i].end, value_by_span)
                u_i = first(by_head, ("HAS_UNIT", q_i))
                if u_i is not None:
                    unit_id = entities[u_i].entry_id
            if money.value_base is not None and quantity:
                unit_price = money.value_base / quantity

        tax_i = first(by_head, ("CHARGED_UNDER", mi))
        tax_id = entities[tax_i].entry_id if tax_i is not None else None

        obs.append(
            MonetaryObservation(
                tm_id=meta.tm_id,
                amount_start=m.start,
                amount_end=m.end,
                amount_text=m.text,
                value_num=value_num,
                currency_id=money.currency_id,
                system=money.system,
                value_base=money.value_base,
                commodity_id=commodity_id,
                quantity=quantity,
                unit_id=unit_id,
                unit_price_base=unit_price,
                tax_id=tax_id,
                confidence=m.confidence,
                date_lo=meta.date_lo,
                date_hi=meta.date_hi,
                date_mid=mid,
                century=century(mid),
                bin50=half_century_start(mid),
                place_pleiades=meta.place_pleiades,
                genres=meta.genres,
            )
        )
    return obs
