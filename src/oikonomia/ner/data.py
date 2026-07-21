"""Load NER documents (gold, silver) from JSONL and derive the label schema.

Records are the ``CharSpan``-shaped JSONL the rest of the project already emits:
``{"doc_id", "text", "entities": [{"start", "end", "label", "confidence"?}]}``.
Silver carries ``confidence``; gold does not (treated as 1.0).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oikonomia.ner.encode import Entity, build_label_list


def read_ner_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL corpus of annotated documents."""
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def entities_of(doc: dict[str, Any], *, min_confidence: float = 0.0) -> list[Entity]:
    """Extract ``(start, end, label)`` tuples, dropping spans below a confidence."""
    out: list[Entity] = []
    for e in doc.get("entities") or []:
        if float(e.get("confidence", 1.0)) < min_confidence:
            continue
        out.append((int(e["start"]), int(e["end"]), str(e["label"])))
    return out


def collect_labels(docs: list[dict[str, Any]]) -> list[str]:
    """Build the BIO label list from every entity label present in ``docs``."""
    labels = {str(e["label"]) for d in docs for e in d.get("entities") or []}
    return build_label_list(labels)
