"""Validate — and repair — hand-annotated gold documents.

Annotation is done by hand against character offsets, and offsets are the one
thing a human cannot check by eye. Three failure modes showed up in the very
first annotated documents, none of which any other check would catch:

1. **``end`` treated as inclusive.** Every span came out one character short,
   and single-character spans (`QUANTITY` "β", the commonest label in an
   account) collapsed to ``start == end`` — an empty span that silently
   contributes nothing to training and nothing to the score.
2. **Annotating against a stale batch.** When the parser fixed
   ``<lb break="no"/>``, joined words removed a character each, so offsets
   drifted further out of true the deeper into the document you read.
3. **Relation direction.** ``HAS_QUANTITY`` is `COMMODITY → QUANTITY`; writing
   it the other way round is invisible until a model trains on it.

Every span carries the text it claims to cover, so all three are mechanically
detectable, and the first two are mechanically *repairable* — the claimed text
is the ground truth and the offset is merely a pointer to it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

# Relation signatures, from resources/schema/annotation_guidelines.md §"Relations".
RELATION_SIGNATURES: dict[str, tuple[str, str]] = {
    "HAS_QUANTITY": ("COMMODITY", "QUANTITY"),
    "HAS_UNIT": ("QUANTITY", "UNIT"),
    "HAS_CURRENCY": ("MONEY_AMOUNT", "CURRENCY"),
    "HAS_PRICE": ("COMMODITY", "MONEY_AMOUNT"),
    "CHARGED_UNDER": ("MONEY_AMOUNT", "TAX_TERM"),
}

# Relations the guidelines define as pointing at "the transaction" — which is
# not an entity, so there is nothing to point at. Reported, never auto-fixed:
# the schema has to decide what anchors a transaction before these can be
# checked. See the Phase 5 notes in CLAUDE.md.
TRANSACTION_ANCHORED = frozenset({"PARTY_OF", "DATED_TO", "PAID_BY", "PAID_TO"})

ProblemKind = Literal[
    "empty_span",
    "out_of_bounds",
    "text_mismatch",
    "relation_index",
    "relation_direction",
    "relation_unanchored",
    "overlap",
]


class Problem(BaseModel):
    """One defect found in one annotated document."""

    doc_id: str
    kind: ProblemKind
    index: int  # entity or relation index it refers to
    detail: str
    repairable: bool = False


class ValidationReport(BaseModel):
    n_docs: int = 0
    n_entities: int = 0
    n_relations: int = 0
    problems: list[Problem] = Field(default_factory=list)
    n_repaired: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems

    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self.problems:
            counts[p.kind] = counts.get(p.kind, 0) + 1
        return counts


def relocate(text: str, claim: str, hint: int) -> int | None:
    """Find where ``claim`` really sits, preferring the occurrence nearest ``hint``.

    Names repeat inside a document (``Ἀρτεμίδωρος`` eleven times in one
    account), so "search for the string" alone would collapse distinct mentions
    onto the first one. Anchoring to the annotator's own offset keeps each
    mention where it was meant.
    """
    if not claim:
        return None
    best: int | None = None
    start = 0
    while (found := text.find(claim, start)) != -1:
        if best is None or abs(found - hint) < abs(best - hint):
            best = found
        start = found + 1
    return best


def _check_entity(doc_id: str, i: int, ent: dict[str, Any], text: str) -> list[Problem]:
    problems: list[Problem] = []
    start, end = int(ent.get("start", -1)), int(ent.get("end", -1))
    claim = ent.get("text")

    if start < 0 or end > len(text) or start > end:
        problems.append(
            Problem(
                doc_id=doc_id,
                kind="out_of_bounds",
                index=i,
                detail=f"span {start}:{end} outside 0:{len(text)}",
                repairable=bool(claim) and relocate(text, str(claim), start) is not None,
            )
        )
        return problems

    if start == end:
        fixed = relocate(text, str(claim), start) if claim else None
        problems.append(
            Problem(
                doc_id=doc_id,
                kind="empty_span",
                index=i,
                detail=(
                    f"span {start}:{end} selects nothing"
                    + (f"; {claim!r} is at {fixed}" if fixed is not None else "")
                ),
                repairable=fixed is not None,
            )
        )
        return problems

    if claim is not None and text[start:end] != claim:
        fixed = relocate(text, str(claim), start)
        problems.append(
            Problem(
                doc_id=doc_id,
                kind="text_mismatch",
                index=i,
                detail=(
                    f"span {start}:{end} selects {text[start:end]!r}, "
                    f"annotated as {claim!r}"
                    + (f"; found at {fixed}:{fixed + len(str(claim))}" if fixed is not None else "")
                ),
                repairable=fixed is not None,
            )
        )
    return problems


def _check_relation(
    doc_id: str, i: int, rel: dict[str, Any], labels: list[str]
) -> list[Problem]:
    problems: list[Problem] = []
    head, tail = int(rel.get("head", -1)), int(rel.get("tail", -1))
    rtype = str(rel.get("type", ""))

    if not (0 <= head < len(labels)) or not (0 <= tail < len(labels)):
        return [
            Problem(
                doc_id=doc_id,
                kind="relation_index",
                index=i,
                detail=f"{rtype} head={head} tail={tail} outside 0:{len(labels)}",
            )
        ]

    if rtype in TRANSACTION_ANCHORED:
        problems.append(
            Problem(
                doc_id=doc_id,
                kind="relation_unanchored",
                index=i,
                detail=(
                    f"{rtype} points at 'the transaction', which is not an entity; "
                    f"here it links {labels[head]} -> {labels[tail]}"
                ),
            )
        )
        return problems

    sig = RELATION_SIGNATURES.get(rtype)
    if sig is None:
        return problems
    want_head, want_tail = sig
    got_head, got_tail = labels[head], labels[tail]
    if (got_head, got_tail) != (want_head, want_tail):
        reversed_hint = " (endpoints are reversed)" if (got_tail, got_head) == sig else ""
        problems.append(
            Problem(
                doc_id=doc_id,
                kind="relation_direction",
                index=i,
                detail=(
                    f"{rtype} should be {want_head} -> {want_tail}, "
                    f"got {got_head} -> {got_tail}{reversed_hint}"
                ),
            )
        )
    return problems


def validate_document(doc: dict[str, Any]) -> list[Problem]:
    """Check one annotated document's spans and relations."""
    doc_id = str(doc.get("doc_id", "?"))
    text = str(doc.get("text", ""))
    entities: list[dict[str, Any]] = list(doc.get("entities") or [])

    problems: list[Problem] = []
    for i, ent in enumerate(entities):
        problems.extend(_check_entity(doc_id, i, ent, text))

    labels = [str(e.get("label", "")) for e in entities]
    for i, rel in enumerate(doc.get("relations") or []):
        problems.extend(_check_relation(doc_id, i, rel, labels))
    return problems


def repair_document(doc: dict[str, Any]) -> int:
    """Move every span onto the offsets its own text implies. Returns the count.

    Only offsets are touched: the annotator's text, label and relations are the
    record of intent and are never rewritten. A span whose text cannot be found
    is left exactly as it is, so it still fails validation and gets a human.
    """
    text = str(doc.get("text", ""))
    repaired = 0
    for ent in doc.get("entities") or []:
        claim = ent.get("text")
        if not claim:
            continue
        start, end = int(ent.get("start", -1)), int(ent.get("end", -1))
        if 0 <= start <= end <= len(text) and text[start:end] == claim:
            continue
        found = relocate(text, str(claim), start)
        if found is None:
            continue
        ent["start"], ent["end"] = found, found + len(str(claim))
        repaired += 1
    return repaired


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(docs: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for doc in docs:
            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
    tmp.replace(path)


def validate_file(path: Path, *, fix: bool = False) -> ValidationReport:
    """Validate an annotated JSONL file, optionally repairing offsets in place."""
    docs = read_jsonl(path)
    report = ValidationReport(n_docs=len(docs))

    if fix:
        report.n_repaired = sum(repair_document(doc) for doc in docs)
        write_jsonl(docs, path)

    for doc in docs:
        report.n_entities += len(doc.get("entities") or [])
        report.n_relations += len(doc.get("relations") or [])
        report.problems.extend(validate_document(doc))
    return report
