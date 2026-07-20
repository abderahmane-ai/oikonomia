"""A proximity baseline for entity and relation extraction.

This exists to be **beaten**. It is written in Phase 2, before any model is
trained, so that the Phase 7/8 models are measured against a real bar rather
than against zero. A rules baseline built after the fact is always suspiciously
weak; one built first is honest.

The rules are deliberately shallow — lexicon lookup plus nearest-neighbour
attachment inside a line. No syntax, no morphology, no learning. What it does
encode are the three facts the corpus measurement actually established:

1. **Units precede their numeral.** Mining the tokens adjacent to every ``<num>``
   showed ``δραχμαι`` to the left of the numeral in 82% of its occurrences and
   ``αρταβαι`` in 80%. Greek accounts read ``πυροῦ ἀρτάβαι ιβ`` — commodity,
   unit, number. So attachment prefers the left neighbour on ties.
2. **Lines bound transactions.** In an account or register the next line is a
   different entry, so nothing attaches across a line break.
3. **A numeral next to a date word is a date, not a quantity.** ``ιϛ ἔτος`` is a
   regnal year; counting it as an amount of something is the single largest
   source of spurious transactions.
"""

from __future__ import annotations

import bisect
import json
from collections import Counter
from collections.abc import Iterable

import pandas as pd
from pydantic import BaseModel, Field

from oikonomia.labeling.matcher import LexiconMatch, Matcher
from oikonomia.schemas.spans import CharSpan

# Categories, as produced by the lexicon files.
CURRENCY = "CURRENCY"
UNIT = "UNIT"
COMMODITY = "COMMODITY"
DATE_REF = "DATE_REF"
TAX_TERM = "TAX_TERM"
FRACTION = "FRACTION"

# Entity labels this baseline emits (see resources/schema/annotation_guidelines.md).
QUANTITY = "QUANTITY"
MONEY_AMOUNT = "MONEY_AMOUNT"

# How far, in characters, a numeral may sit from a term and still attach to it.
# Chosen to span a short Greek phrase ("πυροῦ ἀρτάβας ") without reaching across
# a whole clause; lines cap it anyway.
DEFAULT_WINDOW = 40

# Columns the corpus-wide baseline run needs.
BASELINE_COLUMNS = ("document_json",)


class WeakEntity(BaseModel):
    """One predicted entity mention."""

    label: str
    span: CharSpan
    text: str
    entry_id: str | None = None  # lexicon entry, when it came from the lexicon


class WeakRelation(BaseModel):
    """One predicted relation, as indices into the entity list."""

    type: str
    head: int
    tail: int
    distance: int  # characters between the two mentions, for triage


class WeakLabeling(BaseModel):
    """The baseline's prediction for one document."""

    entities: list[WeakEntity] = Field(default_factory=list)
    relations: list[WeakRelation] = Field(default_factory=list)


class _LineIndex:
    """Line lookup by character position, built once per document.

    Binary search rather than a scan, and the search keys are built once:
    ``line_of`` is called for every numeral against every candidate term, and
    accounts and tax registers run to hundreds of lines with hundreds of
    numerals apiece. Scanning made the corpus-wide run quadratic in exactly the
    documents that matter most, and it did not finish.
    """

    __slots__ = ("_bounds", "_starts")

    def __init__(self, spans: list[CharSpan]) -> None:
        self._bounds = [(s.start, s.end) for s in spans]
        self._starts = [s.start for s in spans]

    def line_of(self, pos: int) -> int:
        idx = bisect.bisect_right(self._starts, pos) - 1
        if idx < 0:
            return -1
        lo, hi = self._bounds[idx]
        return idx if lo <= pos < hi else -1


def _nearest(
    anchor: CharSpan,
    candidates: list[tuple[int, WeakEntity, int]],
    lines: _LineIndex,
    window: int,
) -> int | None:
    """Index of the nearest candidate in the same line, preferring the left.

    Distance is measured between the facing edges of the two spans. Ties break
    left because that is the direction the corpus measurement found units to
    lie in; a right-preferring tie-break would systematically mis-attach the
    ``ἀρτάβαι`` of the *next* entry.
    """
    anchor_line = lines.line_of(anchor.start)
    best: tuple[int, int, int] | None = None  # (distance, side_rank, index)

    for idx, ent, ent_line in candidates:
        if ent_line != anchor_line:
            continue
        if ent.span.end <= anchor.start:
            distance, side_rank = anchor.start - ent.span.end, 0  # left
        elif ent.span.start >= anchor.end:
            distance, side_rank = ent.span.start - anchor.end, 1  # right
        else:
            distance, side_rank = 0, 0  # overlapping
        if distance > window:
            continue
        key = (distance, side_rank, idx)
        if best is None or key < best:
            best = key
    return best[2] if best else None


def label_document(
    text: str,
    numeral_spans: list[CharSpan],
    line_spans: list[CharSpan],
    matcher: Matcher,
    *,
    window: int = DEFAULT_WINDOW,
) -> WeakLabeling:
    """Apply the proximity rules to one document."""
    lines = _LineIndex(line_spans)
    matches: list[LexiconMatch] = matcher.match(text)

    entities: list[WeakEntity] = [
        WeakEntity(label=m.category, span=m.span, text=m.text, entry_id=m.entry_id)
        for m in matches
    ]

    # Each candidate carries its line index, resolved once here rather than
    # re-derived on every nearest-neighbour comparison.
    by_cat: dict[str, list[tuple[int, WeakEntity, int]]] = {}
    for i, ent in enumerate(entities):
        by_cat.setdefault(ent.label, []).append((i, ent, lines.line_of(ent.span.start)))

    # Numerals become QUANTITY, unless a date word sits next to them (rule 3),
    # in which case the numeral belongs to the date expression and is not an
    # amount of anything.
    numeral_indices: list[int] = []
    for span in numeral_spans:
        if _nearest(span, by_cat.get(DATE_REF, []), lines, window=4) is not None:
            continue
        entities.append(WeakEntity(label=QUANTITY, span=span, text=span.slice(text)))
        numeral_indices.append(len(entities) - 1)

    relations: list[WeakRelation] = []

    def _link(rel_type: str, head: int, tail: int) -> None:
        h, t = entities[head].span, entities[tail].span
        distance = max(0, max(h.start, t.start) - min(h.end, t.end))
        relations.append(WeakRelation(type=rel_type, head=head, tail=tail, distance=distance))

    for num_idx in numeral_indices:
        num = entities[num_idx]

        # A numeral governed by a currency term is money, not a count.
        cur_idx = _nearest(num.span, by_cat.get(CURRENCY, []), lines, window)
        if cur_idx is not None:
            entities[num_idx] = num.model_copy(update={"label": MONEY_AMOUNT})
            _link("HAS_CURRENCY", num_idx, cur_idx)
        else:
            unit_idx = _nearest(num.span, by_cat.get(UNIT, []), lines, window)
            if unit_idx is not None:
                _link("HAS_UNIT", num_idx, unit_idx)

        # Whatever the amount is in, it may still be an amount *of* something.
        com_idx = _nearest(num.span, by_cat.get(COMMODITY, []), lines, window)
        if com_idx is not None:
            _link("HAS_QUANTITY", com_idx, num_idx)

        # Money charged under a named heading.
        if entities[num_idx].label == MONEY_AMOUNT:
            tax_idx = _nearest(num.span, by_cat.get(TAX_TERM, []), lines, window)
            if tax_idx is not None:
                _link("CHARGED_UNDER", num_idx, tax_idx)

    return WeakLabeling(entities=entities, relations=relations)


class BaselineReport(BaseModel):
    """What the proximity baseline predicts over a whole corpus.

    These are *yields*, not scores: no gold annotation exists yet, so nothing
    here is precision or recall. They are the bar Phase 7/8 must clear, and the
    denominator the Phase 5 gold sample gets drawn against.
    """

    n_docs: int
    n_entities: int
    n_relations: int
    entities_by_label: dict[str, int]
    relations_by_type: dict[str, int]
    n_numerals: int
    n_numerals_suppressed_as_date: int
    date_suppression_rate: float
    n_numerals_linked: int
    numeral_link_rate: float = Field(
        description="Share of surviving numerals given at least one relation. "
        "The headline number to beat."
    )


def run_baseline(
    batches: Iterable[pd.DataFrame],
    matcher: Matcher,
    *,
    window: int = DEFAULT_WINDOW,
) -> BaselineReport:
    """Run the baseline over corpus record batches and summarise its yield."""
    n_docs = n_entities = n_relations = 0
    n_numerals = n_kept = n_linked = 0
    by_label: Counter[str] = Counter()
    by_type: Counter[str] = Counter()

    for df in batches:
        for doc_json in df["document_json"]:
            doc = json.loads(doc_json)
            text = doc["edited_text"]
            if not text:
                continue
            numerals = [
                CharSpan(start=n["edited"]["start"], end=n["edited"]["end"])
                for n in doc["numerals"]
                if n.get("edited")
            ]
            lines = [
                CharSpan(start=ln["edited"]["start"], end=ln["edited"]["end"])
                for ln in doc["lines"]
                if ln.get("edited")
            ]
            result = label_document(text, numerals, lines, matcher, window=window)

            n_docs += 1
            n_numerals += len(numerals)
            n_entities += len(result.entities)
            n_relations += len(result.relations)
            for ent in result.entities:
                by_label[ent.label] += 1
            for rel in result.relations:
                by_type[rel.type] += 1

            amount_idx = {
                i
                for i, e in enumerate(result.entities)
                if e.label in {QUANTITY, MONEY_AMOUNT}
            }
            n_kept += len(amount_idx)
            n_linked += len({i for r in result.relations for i in (r.head, r.tail)} & amount_idx)

    suppressed = n_numerals - n_kept
    return BaselineReport(
        n_docs=n_docs,
        n_entities=n_entities,
        n_relations=n_relations,
        entities_by_label=dict(by_label.most_common()),
        relations_by_type=dict(by_type.most_common()),
        n_numerals=n_numerals,
        n_numerals_suppressed_as_date=suppressed,
        date_suppression_rate=round(suppressed / n_numerals, 4) if n_numerals else 0.0,
        n_numerals_linked=n_linked,
        numeral_link_rate=round(n_linked / n_kept, 4) if n_kept else 0.0,
    )
