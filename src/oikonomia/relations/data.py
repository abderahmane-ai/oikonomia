"""Load relation-extraction documents (gold, silver) from JSONL.

Records are the same ``CharSpan``-shaped JSONL the rest of the project emits:
``{"doc_id", "text", "entities": [...], "relations": [{"head", "tail", "type",
"confidence"?}]}`` where ``head``/``tail`` index into ``entities``. Silver
relations carry ``confidence``; gold does not (treated as 1.0). Entity loading
reuses :mod:`oikonomia.ner.data`.
"""

from __future__ import annotations

from typing import Any

from oikonomia.ner.data import entities_of, read_ner_jsonl
from oikonomia.relations.encode import Relation

__all__ = ["entities_of", "read_ner_jsonl", "relations_of"]


def relations_of(doc: dict[str, Any], *, min_confidence: float = 0.0) -> list[Relation]:
    """Extract ``(head, tail, type)`` tuples, dropping edges below a confidence.

    Dropping is only ever used to withhold an *uncertain silver positive* from
    training — never to relabel it as a negative (the model side excludes such a
    pair from the loss entirely rather than teaching it as ``NO_RELATION``).
    """
    out: list[Relation] = []
    for r in doc.get("relations") or []:
        if float(r.get("confidence", 1.0)) < min_confidence:
            continue
        out.append((int(r["head"]), int(r["tail"]), str(r["type"])))
    return out
