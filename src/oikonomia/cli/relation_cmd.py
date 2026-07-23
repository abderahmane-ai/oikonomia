"""`oik relation` subcommands: freeze the RE schema and set the baseline (Phase 8).

GPU-free. ``prepare`` freezes the relation label list and entity-label vocabulary
the span-pair model needs, and reports candidate-generation statistics — most
importantly the **recall guard**: every gold relation must be a generated
candidate, or typed candidate generation is silently capping that relation's
recall at zero.

``score`` runs the *nearest-admissible-pair* baseline over **gold** entities (the
oracle setting) — the trivial null linker the trained model must beat. It is
deliberately direction-blind (emits ``PAID_BY``, never ``PAID_TO``), so its zero
on ``PAID_TO`` and its coin-flip precision on direction are exactly the gap a
learned model has to close.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.gold.validate import RELATION_SIGNATURES
from oikonomia.labeling.score import Entity, Relation, build_report
from oikonomia.ner.data import entities_of, read_ner_jsonl
from oikonomia.relations.data import relations_of
from oikonomia.relations.encode import (
    ENDPOINT_LABELS,
    RELATION_LABELS,
    label_candidates,
    relation_label_maps,
    uncovered_relations,
)

relation_app = typer.Typer(help="Downstream relation extraction (Phase 8).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[list[str] | None, typer.Option("--set", help="Dotted config override.")]

# The nearest-pair baseline cannot tell payer from payee (that is the model's
# job), so it commits to the majority direction and never emits PAID_TO.
_DIRECTION_BLIND_SKIP = "PAID_TO"


def _stream_jsonl(path: Path, limit: int) -> Iterator[dict]:  # type: ignore[type-arg]
    """Yield parsed JSONL rows one at a time (no whole-file materialisation).

    Silver is 146 MB; loading it into a list to tally candidate stats is what made
    an earlier ``prepare`` swap for minutes. Streaming with a ``limit`` keeps the
    scan bounded and light.
    """
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit and i >= limit:
                return
            if line.strip():
                yield json.loads(line)


@relation_app.command("prepare")
def prepare(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    silver_sample: Annotated[
        int, typer.Option(help="Silver docs to tally candidate stats over (0 = all).")
    ] = 4000,
    max_entities: Annotated[
        int, typer.Option(help="Skip dense docs above this entity count in the stats.")
    ] = 300,
) -> None:
    """Freeze the relation schema; report candidate stats + the gold recall guard."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    gold = read_ner_jsonl(s.paths.gold / "annotated.jsonl")

    label2id, _ = relation_label_maps()
    # The type-embedding vocab is the labels that can be relation endpoints —
    # derived from the contract, not scanned from the corpus (see ENDPOINT_LABELS).
    entity_labels = list(ENDPOINT_LABELS)
    out_dir = s.paths.processed / "relations"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "relation_labels.json").write_text(
        json.dumps(
            {
                "relation_labels": RELATION_LABELS,
                "relation_label2id": label2id,
                "entity_labels": entity_labels,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Recall guard over ALL gold: candidate generation must lose no gold relation.
    uncovered: list[tuple[str, Relation]] = []
    gold_pos = Counter[str]()
    for d in gold:
        ents = entities_of(d)
        rels = relations_of(d)
        for r in rels:
            gold_pos[r[2]] += 1
        for miss in uncovered_relations(ents, rels):
            uncovered.append((str(d.get("doc_id", "?")), miss))

    # Candidate density over a streamed silver sample (positives vs negatives).
    # Candidate generation is O(n²); a few silver docs are giant concatenated
    # registers (up to ~45k entities) that the model truncates to 512 tokens
    # anyway, so they are skipped here rather than allowed to dominate the scan.
    n_docs = n_dense = n_cand = n_pos = 0
    pos_by_type = Counter[str]()
    for d in _stream_jsonl(s.paths.processed / "silver.jsonl", silver_sample):
        n_docs += 1
        ents = entities_of(d)
        if len(ents) > max_entities:
            n_dense += 1
            continue
        for _, _, ty in label_candidates(ents, relations_of(d)):
            n_cand += 1
            if ty != "NO_RELATION":
                n_pos += 1
                pos_by_type[ty] += 1

    summary = {
        "labels_path": str(out_dir / "relation_labels.json"),
        "n_relation_labels": len(RELATION_LABELS),
        "n_entity_labels": len(entity_labels),
        "gold": {
            "n_docs": len(gold),
            "n_relations": int(sum(gold_pos.values())),
            "by_type": dict(gold_pos.most_common()),
            "recall_guard_uncovered": len(uncovered),  # MUST be 0
            "uncovered_examples": [f"{doc}:{r}" for doc, r in uncovered[:10]],
        },
        "silver_candidates": {
            "docs_sampled": n_docs,
            "docs_skipped_dense": n_dense,
            "n_candidates": n_cand,
            "n_positive": n_pos,
            "n_negative": n_cand - n_pos,
            "positive_rate": round(n_pos / n_cand, 4) if n_cand else 0.0,
            "positives_by_type": dict(pos_by_type.most_common()),
        },
    }
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    if uncovered:
        typer.echo(
            f"\nRECALL GUARD FAILED: {len(uncovered)} gold relations are not candidates.",
            err=True,
        )
        raise typer.Exit(code=1)


def _nearest_baseline(entities: list[Entity]) -> list[Relation]:
    """Link each head to its single nearest admissible tail, per relation type.

    The trivial oracle linker: for every relation type a head's label can front,
    attach the nearest entity whose label is a legal tail. Direction-blind — it
    emits ``PAID_BY`` only, leaving ``PAID_TO`` (and thus half of direction) for
    a model to earn.
    """
    rels: list[Relation] = []
    n = len(entities)
    for h in range(n):
        hs, he, hl = entities[h]
        for ty, (want_head, want_tail) in RELATION_SIGNATURES.items():
            if ty == _DIRECTION_BLIND_SKIP or hl not in want_head:
                continue
            best_t: int | None = None
            best_gap = -1
            for t in range(n):
                if t == h or entities[t][2] not in want_tail:
                    continue
                ts, te, _ = entities[t]
                gap = max(0, max(hs, ts) - min(he, te))
                if best_t is None or gap < best_gap:
                    best_t, best_gap = t, gap
            if best_t is not None:
                rels.append((h, best_t, ty))
    return rels


@relation_app.command("score")
def score(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    path: Annotated[
        Path | None, typer.Option("--path", help="Gold JSONL (default: data/gold/annotated.jsonl).")
    ] = None,
) -> None:
    """Nearest-admissible-pair baseline over gold entities — the bar to beat."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    target = path or s.paths.gold / "annotated.jsonl"
    if not target.is_file():
        typer.echo(f"no gold at {target}", err=True)
        raise typer.Exit(code=1)

    gold = read_ner_jsonl(target)
    per_doc: list[tuple[list[Entity], list[Relation], list[Entity], list[Relation]]] = []
    for d in gold:
        ents = entities_of(d)
        gold_rels = relations_of(d)
        pred_rels = _nearest_baseline(ents)
        # Oracle entities: pred entities == gold entities, so relation scoring is
        # exact on indices (score_relations maps pred->gold spans identically).
        per_doc.append((ents, gold_rels, ents, pred_rels))

    report = build_report(n_docs=len(gold), n_docs_scored=len(gold), per_doc=per_doc)
    rel = report.relations
    typer.echo("nearest-admissible-pair baseline over GOLD entities (oracle setting)")
    typer.echo(f"\n  {'type':14} {'gold':>5} {'pred':>5} {'tp':>5} {'P':>6} {'R':>6} {'F1':>6}")
    for row in rel.by_type:
        typer.echo(
            f"  {row.label:14} {row.n_gold:>5} {row.n_pred:>5} {row.tp:>5} "
            f"{row.precision:>6.3f} {row.recall:>6.3f} {row.f1:>6.3f}"
        )
    typer.echo(
        f"  {'MICRO':14} {rel.n_gold:>5} {rel.n_pred:>5} {rel.tp:>5} "
        f"{rel.precision:>6.3f} {rel.recall:>6.3f} {rel.f1:>6.3f}"
    )
