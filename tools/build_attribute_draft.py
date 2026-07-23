"""Draft HAS_OCCUPATION / HAS_AGE edges over gold, for human review (Phase 8b).

The Phase-5c pattern, reused: a *deterministic* rule proposes edges over the
already-validated gold entities, the proposals are written to a **separate**
auditable file, and a human confirms them before anything is merged into gold.
This mirrors ``data/gold/direction_draft.jsonl`` exactly.

**This tool never touches ``annotated.jsonl``.** It only reads it, and writes
``data/gold/attribute_draft.jsonl``. (Contrast ``build_gold_draft.py``, which
overwrites the whole gold file from a spec and must not be run — see CLAUDE.md.)
Regenerating the draft is safe and idempotent: it is a re-derivable proposal, not
a source of truth.

Each drafted edge carries the head/tail **entity indices** (into the document's
``entities`` list, so a reviewer's "yes" merges by index) and the head/tail
**surface strings** (so the reviewer can eyeball it without cross-referencing).
Edges already present in the document's relations are skipped, so the draft only
ever proposes what gold does not already have.

Usage::

    .venv/bin/python tools/build_attribute_draft.py            # write + summarise
    .venv/bin/python tools/build_attribute_draft.py --preview 20   # show context
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oikonomia.labeling.apposition import attribute_relations

GOLD = Path("data/gold/annotated.jsonl")
OUT = Path("data/gold/attribute_draft.jsonl")


def _read_docs(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def draft_edges(doc: dict) -> list[dict]:
    """The apposition edges this document does not already carry."""
    ents = doc.get("entities") or []
    spans = [(int(e["start"]), int(e["end"]), str(e["label"])) for e in ents]
    existing = {(int(r["head"]), int(r["tail"]), str(r["type"])) for r in doc.get("relations") or []}
    edges: list[dict] = []
    for head, tail, rtype in attribute_relations(spans):
        if (head, tail, rtype) in existing:
            continue
        edges.append(
            {
                "type": rtype,
                "head": head,
                "tail": tail,
                "head_text": ents[head]["text"],
                "tail_text": ents[tail]["text"],
            }
        )
    return edges


def build(gold: Path, out: Path, preview: int) -> None:
    docs = _read_docs(gold)
    drafted: list[dict] = []
    by_type: dict[str, int] = {}
    for doc in docs:
        edges = draft_edges(doc)
        if not edges:
            continue
        drafted.append({"doc_id": str(doc.get("doc_id", "?")), "attribute": edges})
        for e in edges:
            by_type[e["type"]] = by_type.get(e["type"], 0) + 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in drafted) + "\n", encoding="utf-8"
    )

    total = sum(by_type.values())
    print(f"Wrote {out}: {total} edges across {len(drafted)}/{len(docs)} docs")
    for ty in sorted(by_type):
        print(f"  {ty:16s} {by_type[ty]}")

    if preview:
        print(f"\n--- first {preview} edges in context (review these) ---")
        text_by_id = {str(d.get("doc_id", "?")): str(d.get("text", "")) for d in docs}
        shown = 0
        for d in drafted:
            text = text_by_id[d["doc_id"]]
            for e in d["attribute"]:
                if shown >= preview:
                    return
                # locate the head to print a window around the whole apposition
                doc = next(x for x in docs if str(x.get("doc_id")) == d["doc_id"])
                hs = int(doc["entities"][e["head"]]["start"])
                te = int(doc["entities"][e["tail"]]["end"])
                snippet = text[max(0, hs - 6):te + 6].replace("\n", "/")
                print(f"  {d['doc_id']:>7} {e['type']:14s} {e['head_text']!r} -> {e['tail_text']!r}   …{snippet}…")
                shown += 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--preview", type=int, default=0, help="print N edges with context")
    args = ap.parse_args()
    if args.out.resolve() == args.gold.resolve():
        raise SystemExit("refusing to overwrite the gold file; --out must differ from --gold")
    build(args.gold, args.out, args.preview)


if __name__ == "__main__":
    main()
