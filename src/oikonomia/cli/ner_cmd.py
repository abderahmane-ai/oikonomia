"""`oik ner` subcommands: freeze the entity-NER label schema (Phase 7).

GPU-free. Builds the BIO label list from the silver training data and reports
coverage — including any gold label the silver never teaches (unlearnable, so
its recall is capped at zero and that must be visible before a GPU run).
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Annotated

import typer

from oikonomia.config import load_settings
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
