"""`oik ner` subcommands: freeze the entity-NER label schema (Phase 7).

GPU-free. Builds the BIO label list from the silver training data and reports
coverage — including any gold label the silver never teaches (unlearnable, so
its recall is capped at zero and that must be visible before a GPU run).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.corpus.io import corpus_path, iter_batches
from oikonomia.ner.data import collect_labels, read_ner_jsonl

ner_app = typer.Typer(help="Downstream entity NER (Phase 7).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[
    list[str] | None,
    typer.Option("--set", help="Dotted config override."),
]


@ner_app.command("prepare")
def prepare(env: EnvOpt = "local", set_: SetOpt = None) -> None:
    """Freeze the BIO label schema from silver; report train/gold label coverage."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    silver = read_ner_jsonl(s.paths.processed / "silver.jsonl")
    gold = read_ner_jsonl(s.paths.gold / "annotated.jsonl")

    labels = collect_labels(silver)  # BIO list from the training vocabulary
    label2id = {lab: i for i, lab in enumerate(labels)}
    out_dir = s.paths.processed / "ner"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "labels.json").write_text(
        json.dumps({"labels": labels, "label2id": label2id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    silver_types = Counter(str(e["label"]) for d in silver for e in d.get("entities") or [])
    gold_types = Counter(str(e["label"]) for d in gold for e in d.get("entities") or [])
    summary = {
        "labels_path": str(out_dir / "labels.json"),
        "n_bio_labels": len(labels),
        "n_train_docs": len(silver),
        "n_eval_docs": len(gold),
        "n_train_entities": sum(silver_types.values()),
        "n_eval_entities": sum(gold_types.values()),
        "train_by_label": dict(silver_types.most_common()),
        "eval_by_label": dict(gold_types.most_common()),
        "gold_labels_not_in_silver": sorted(set(gold_types) - set(silver_types)),
    }
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@ner_app.command("corpus-text")
def corpus_text(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output JSONL (default: processed/ner/corpus_text.jsonl)."),
    ] = None,
) -> None:
    """Materialize ``{stem, tm_id, text}`` for every non-empty doc → a compact JSONL.

    The upload payload for corpus-scale NER inference on Modal: only the columns
    the GPU needs (``stem``, ``tm_id`` + the canonical ``edited_text``), so the
    push is ~100 MB instead of the 293 MB ``corpus.parquet``. Empties are dropped
    on ``text.strip()`` — never on ``n_chars_edited``, which counts whitespace.

    ``stem`` is the join key downstream, not ``tm_id``: ``tm_id`` is **not unique**
    (607 tm_ids span multiple rows, 231 with >1 non-empty row), so re-joining spans
    to text by tm_id would slice the wrong document. ``stem`` is one-per-row.

    After writing, push it to the volume and run inference (Claude does not run
    these — they are the GPU steps)::

        modal volume put oikonomia-ner data/processed/ner/corpus_text.jsonl \\
            /data/corpus_text.jsonl --force
        .venv/bin/modal run --detach modal_app/ner.py::infer
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    cpath = corpus_path(s.paths.processed)
    if not cpath.is_file():
        typer.secho("corpus.parquet missing — run `oik ingest build` first.", fg="red")
        raise typer.Exit(1)

    out_path = out or (s.paths.processed / "ner" / "corpus_text.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_docs = n_empty = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for frame in iter_batches(cpath, ["stem", "tm_id", "edited_text"]):
            for stem, tm_id, text in zip(
                frame["stem"], frame["tm_id"], frame["edited_text"], strict=True
            ):
                if not text or not str(text).strip():
                    n_empty += 1
                    continue
                fh.write(json.dumps(
                    {"stem": str(stem), "tm_id": str(tm_id), "text": str(text)},
                    ensure_ascii=False,
                ))
                fh.write("\n")
                n_docs += 1

    size_mb = out_path.stat().st_size / 1e6
    typer.echo(f"Wrote {out_path}: {n_docs} docs ({size_mb:.0f} MB); skipped {n_empty} empty.")
    typer.echo(
        "Next (GPU steps): `modal volume put oikonomia-ner "
        f"{out_path} /data/corpus_text.jsonl --force` then `modal run modal_app/ner.py::infer`."
    )
