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
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

# Relation signatures, from resources/schema/annotation_guidelines.md §"Relations".
# Each side is the set of labels allowed at that endpoint.
RELATION_SIGNATURES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "HAS_QUANTITY": (frozenset({"COMMODITY", "OCCUPATION", "PERSON_ROLE"}), frozenset({"QUANTITY"})),
    "HAS_UNIT": (frozenset({"QUANTITY", "FRACTION"}), frozenset({"UNIT"})),
    # FRACTION heads: a bare fraction is a complete amount (𐅷 of a nomismation
    # is a Byzantine rent; 𐅵 of an aroura is real land), so it links like a
    # MONEY_AMOUNT/QUANTITY would.
    "HAS_CURRENCY": (frozenset({"MONEY_AMOUNT", "FRACTION"}), frozenset({"CURRENCY"})),
    "HAS_PRICE": (frozenset({"COMMODITY"}), frozenset({"MONEY_AMOUNT", "FRACTION"})),
    "CHARGED_UNDER": (frozenset({"MONEY_AMOUNT"}), frozenset({"TAX_TERM"})),
    # Anchored on an explicit TRANSACTION trigger — see the guidelines. Before
    # TRANSACTION existed these pointed at "the transaction", which was not an
    # entity, so there was nothing to point at and they could not be checked.
    "PARTY_OF": (frozenset({"PERSON", "PERSON_ROLE"}), frozenset({"TRANSACTION"})),
    "DATED_TO": (frozenset({"TRANSACTION"}), frozenset({"DATE_REF"})),
    "PAID_BY": (frozenset({"PERSON", "PERSON_ROLE"}), frozenset({"MONEY_AMOUNT", "COMMODITY"})),
    "PAID_TO": (frozenset({"PERSON", "PERSON_ROLE"}), frozenset({"MONEY_AMOUNT", "COMMODITY"})),
    # Attribute apposition (Phase 8b): a person's title or age stands right next
    # to the name it qualifies. Before these, OCCUPATION and AGE appeared in no
    # signature, so they could never be a candidate endpoint and 79% of every
    # PERSON reached the database in no relation at all. Recovered by a
    # deterministic adjacency rule (oikonomia.labeling.apposition), each edge
    # auditable to its two spans. PERSON_ROLE is an admissible head too: a bare
    # role can bear the attribute ("the priest, 40 years old").
    "HAS_OCCUPATION": (frozenset({"PERSON", "PERSON_ROLE"}), frozenset({"OCCUPATION"})),
    "HAS_AGE": (frozenset({"PERSON", "PERSON_ROLE"}), frozenset({"AGE"})),
}

# A numeral the annotator *deliberately* leaves unlabelled records the reason,
# so "I didn't get to it" and "it is not an economic quantity" never look the
# same in the data (§0 rule III). These are the only admissible reasons.
SKIP_REASONS: frozenset[str] = frozenset(
    {"isopsephism", "sheet_number", "line_reference", "non_referential"}
)

# Imperial and consular titulature: the folded stems of the epithets and honours
# that trail a ruler's name in a dating formula. They are absorbed into the
# ruler's PERSON span (guidelines §5), so a bare one left over is a real gap —
# but a *covered* one is expected, and this list keeps the name-coverage
# advisory from re-flagging the parts of a PERSON span it cannot see the label
# of. Matched by folded prefix, so declensions are covered.
TITULATURE_STEMS: tuple[str, ...] = (
    "σεβαστ", "αυτοκρατ", "καισαρ", "γερμανικ", "μεγιστ", "ευσεβ", "ευτυχ",
    "βρεταννικ", "αραβικ", "αδιαβηνικ", "παρθικ", "μηδικ", "αρμενιακ",
    "περτινακ", "αυγουστ", "ρωμαι", "δακικ", "σαρματικ", "αιγυπτιακ", "νικητ",
)

ProblemKind = Literal[
    "empty_span",
    "out_of_bounds",
    "text_mismatch",
    "relation_index",
    "relation_direction",
    "overlap",
    # completeness (errors): every tagged numeral gets a decision
    "uncovered_numeral",
    "phantom_skip",
    "skip_text_mismatch",
    "skip_reason",
    # completeness (advisories): candidate omissions a human confirms
    "uncovered_name",
    "money_no_currency",
    "quantity_unlinked",
    "transaction_no_party",
]

Severity = Literal["error", "advisory"]

_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]+")


def _fold(s: str) -> str:
    """Lowercase and strip accents, so titulature matches across declensions."""
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def _is_capitalized(tok: str) -> bool:
    """True if the token's first cased letter is uppercase (a proper name cue)."""
    for ch in tok:
        cat = unicodedata.category(ch)
        if cat == "Lu":
            return True
        if cat == "Ll":
            return False
    return False


def _is_titulature(tok: str) -> bool:
    folded = _fold(tok)
    return any(folded.startswith(stem) for stem in TITULATURE_STEMS)


class Problem(BaseModel):
    """One defect found in one annotated document."""

    doc_id: str
    kind: ProblemKind
    index: int  # entity or relation index it refers to (-1 if positional)
    detail: str
    repairable: bool = False
    severity: Severity = "error"


class ValidationReport(BaseModel):
    n_docs: int = 0
    n_entities: int = 0
    n_relations: int = 0
    problems: list[Problem] = Field(default_factory=list)
    n_repaired: int = 0
    numerals_checked: bool = False

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == "error"]

    @property
    def advisories(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == "advisory"]

    @property
    def ok(self) -> bool:
        """Green iff no *error*-severity problems. Advisories never fail a run."""
        return not self.errors

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

    sig = RELATION_SIGNATURES.get(rtype)
    if sig is None:
        return problems
    want_head, want_tail = sig
    got_head, got_tail = labels[head], labels[tail]
    if got_head not in want_head or got_tail not in want_tail:
        swapped = got_tail in want_head and got_head in want_tail
        problems.append(
            Problem(
                doc_id=doc_id,
                kind="relation_direction",
                index=i,
                detail=(
                    f"{rtype} should be {'|'.join(sorted(want_head))} -> "
                    f"{'|'.join(sorted(want_tail))}, got {got_head} -> {got_tail}"
                    + (" (endpoints are reversed)" if swapped else "")
                ),
            )
        )
    return problems


def _entity_spans(doc: dict[str, Any]) -> list[tuple[int, int]]:
    return [(int(e.get("start", -1)), int(e.get("end", -1))) for e in doc.get("entities") or []]


def _covered(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    """True if some entity span contains ``[start, end)`` (numeral inside a span)."""
    return any(a <= start and end <= b for a, b in spans)


def check_numeral_coverage(
    doc: dict[str, Any], numerals: list[tuple[int, int, str]]
) -> list[Problem]:
    """Every tagged ``<num>`` must be inside a span or a declared skip (§0 rule III).

    ``numerals`` is ``(start, end, text)`` for each ``<num>`` in the document's
    *edited* view — the corpus's own tagging, an independent ground truth the
    annotator cannot see while reading. Coverage is the one completeness property
    a reading pass structurally cannot check: you cannot eyeball the absence of a
    span you never wrote.
    """
    doc_id = str(doc.get("doc_id", "?"))
    text = str(doc.get("text", ""))
    spans = _entity_spans(doc)
    numeral_pos = {(s, e) for s, e, _ in numerals}
    skips = list(doc.get("skipped_numerals") or [])
    problems: list[Problem] = []

    skip_pos: set[tuple[int, int]] = set()
    for j, sk in enumerate(skips):
        s, e = int(sk.get("start", -1)), int(sk.get("end", -1))
        skip_pos.add((s, e))
        reason = str(sk.get("reason", ""))
        claim = sk.get("text")
        if reason not in SKIP_REASONS:
            problems.append(Problem(
                doc_id=doc_id, kind="skip_reason", index=j,
                detail=f"skip reason {reason!r} not in {sorted(SKIP_REASONS)}",
            ))
        if (s, e) not in numeral_pos:
            problems.append(Problem(
                doc_id=doc_id, kind="phantom_skip", index=j,
                detail=f"skip {s}:{e} does not match any tagged <num>",
            ))
        elif claim is not None and text[s:e] != claim:
            problems.append(Problem(
                doc_id=doc_id, kind="skip_text_mismatch", index=j,
                detail=f"skip {s}:{e} selects {text[s:e]!r}, recorded as {claim!r}",
            ))

    for s, e, ntext in numerals:
        if _covered(spans, s, e) or (s, e) in skip_pos:
            continue
        problems.append(Problem(
            doc_id=doc_id, kind="uncovered_numeral", index=-1,
            detail=f"<num> {ntext!r} at {s}:{e} has no label and no skipped_numerals entry",
        ))
    return problems


def check_name_coverage(doc: dict[str, Any]) -> list[Problem]:
    """Advisory: capitalised tokens covered by no span — candidate missed names.

    Capitals mark proper names in papyri, so an unlabelled capitalised token is
    the same inconsistent negative a stray numeral is. Titulature (folded into
    the ruler's PERSON span), very short fragments, and tokens abutting a span
    are filtered out; the residue is for a human to confirm or annotate.
    """
    doc_id = str(doc.get("doc_id", "?"))
    text = str(doc.get("text", ""))
    spans = _entity_spans(doc)
    problems: list[Problem] = []
    for m in _GREEK.finditer(text):
        tok, s, e = m.group(), m.start(), m.end()
        if not _is_capitalized(tok) or _covered(spans, s, e):
            continue
        if len(tok) <= 3 or _is_titulature(tok):
            continue
        if any(abs(b - s) <= 1 or abs(a - e) <= 1 for a, b in spans):
            continue  # abuts a span — a split token, not a missed entity
        problems.append(Problem(
            doc_id=doc_id, kind="uncovered_name", index=s, severity="advisory",
            detail=f"capitalised {tok!r} at {s} is annotated by nothing",
        ))
    return problems


def check_relation_completeness(doc: dict[str, Any]) -> list[Problem]:
    """Advisory: economic entities that should carry a relation but do not."""
    doc_id = str(doc.get("doc_id", "?"))
    ents = list(doc.get("entities") or [])
    rels = list(doc.get("relations") or [])
    labels = [str(e.get("label", "")) for e in ents]
    problems: list[Problem] = []

    has_cur = {int(r.get("head", -1)) for r in rels if r.get("type") == "HAS_CURRENCY"}
    unit_head = {int(r.get("head", -1)) for r in rels if r.get("type") == "HAS_UNIT"}
    qty_tail = {int(r.get("tail", -1)) for r in rels if r.get("type") == "HAS_QUANTITY"}
    party_tail = {int(r.get("tail", -1)) for r in rels if r.get("type") == "PARTY_OF"}

    for i, label in enumerate(labels):
        text = str(ents[i].get("text", ""))
        if label == "MONEY_AMOUNT" and i not in has_cur:
            problems.append(Problem(
                doc_id=doc_id, kind="money_no_currency", index=i, severity="advisory",
                detail=f"MONEY_AMOUNT {text!r} has no HAS_CURRENCY",
            ))
        elif label == "QUANTITY" and i not in unit_head and i not in qty_tail:
            problems.append(Problem(
                doc_id=doc_id, kind="quantity_unlinked", index=i, severity="advisory",
                detail=f"QUANTITY {text!r} is neither a HAS_UNIT head nor a HAS_QUANTITY tail",
            ))
        elif label == "TRANSACTION" and i not in party_tail:
            problems.append(Problem(
                doc_id=doc_id, kind="transaction_no_party", index=i, severity="advisory",
                detail=f"TRANSACTION {text!r} has no PARTY_OF (confirm parties are lost)",
            ))
    return problems


def validate_document(
    doc: dict[str, Any],
    numerals: list[tuple[int, int, str]] | None = None,
    *,
    advisories: bool = False,
) -> list[Problem]:
    """Check one annotated document's spans, relations and completeness.

    ``numerals`` (the corpus ``<num>`` tags for this document) enables the
    numeral-coverage gate — always error-severity. ``advisories`` adds the
    non-fatal name- and relation-completeness hints; it is off by default so a
    document's hard defects can be asserted in isolation, and on for whole-file
    validation where the hints are a review aid.
    """
    doc_id = str(doc.get("doc_id", "?"))
    text = str(doc.get("text", ""))
    entities: list[dict[str, Any]] = list(doc.get("entities") or [])

    problems: list[Problem] = []
    for i, ent in enumerate(entities):
        problems.extend(_check_entity(doc_id, i, ent, text))

    labels = [str(e.get("label", "")) for e in entities]
    for i, rel in enumerate(doc.get("relations") or []):
        problems.extend(_check_relation(doc_id, i, rel, labels))

    if numerals is not None:
        problems.extend(check_numeral_coverage(doc, numerals))
    if advisories:
        problems.extend(check_name_coverage(doc))
        problems.extend(check_relation_completeness(doc))
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


def validate_file(
    path: Path,
    *,
    fix: bool = False,
    numerals_by_text: dict[str, list[tuple[int, int, str]]] | None = None,
) -> ValidationReport:
    """Validate an annotated JSONL file, optionally repairing offsets in place.

    ``numerals_by_text`` maps a document's ``text`` to its corpus ``<num>`` tags
    (``(start, end, text)``); when supplied, the numeral-coverage gate runs. It
    is keyed by text rather than ``doc_id`` because the text is the thing spans
    index, and matching on it also proves the gold text is byte-identical to the
    corpus.
    """
    docs = read_jsonl(path)
    report = ValidationReport(n_docs=len(docs), numerals_checked=numerals_by_text is not None)

    if fix:
        report.n_repaired = sum(repair_document(doc) for doc in docs)
        write_jsonl(docs, path)

    for doc in docs:
        report.n_entities += len(doc.get("entities") or [])
        report.n_relations += len(doc.get("relations") or [])
        numerals = numerals_by_text.get(str(doc.get("text", ""))) if numerals_by_text else None
        report.problems.extend(validate_document(doc, numerals, advisories=True))
    return report
