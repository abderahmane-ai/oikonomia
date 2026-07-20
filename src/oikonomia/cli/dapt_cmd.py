"""`oik dapt` subcommands: prepare the packed pretraining shards."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.dapt.pack import META_SUFFIX, read_shard
from oikonomia.dapt.schedule import plan
from oikonomia.dapt.stage import PACKED_SPLITS, BuildDaptShardsStage
from oikonomia.dapt.text import dapt_shard_dir
from oikonomia.pipeline.stage import run_stage

dapt_app = typer.Typer(help="Domain-adaptive pretraining data (Phase 4).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[
    list[str] | None,
    typer.Option("--set", help="Dotted config override, e.g. dapt.seq_len=256."),
]
ForceOpt = Annotated[bool, typer.Option("--force", help="Ignore cache and rerun.")]


@dapt_app.command("prepare")
def prepare(env: EnvOpt = "local", set_: SetOpt = None, force: ForceOpt = False) -> None:
    """Tokenise and pack the train/dev splits into memory-mapped shards."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    manifest = run_stage(BuildDaptShardsStage(), s, force=force)
    typer.echo(json.dumps(manifest.stats, ensure_ascii=False, indent=2))


@dapt_app.command("inspect")
def inspect(env: EnvOpt = "local", set_: SetOpt = None) -> None:
    """Report what is in the packed shards, and prove test was never packed."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    out = dapt_shard_dir(s.paths.processed)
    summary: dict[str, object] = {}
    for split in PACKED_SPLITS:
        meta_path = (out / f"{split}.bin").with_suffix(META_SUFFIX)
        if not meta_path.is_file():
            summary[split] = "missing — run `oik dapt prepare`"
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        arr = read_shard(out / f"{split}.bin")
        meta["shape"] = list(arr.shape)
        summary[split] = meta
    summary["test"] = "not packed by design — Phase 4 must never read it"

    train_shard = out / "train.bin"
    if train_shard.is_file():
        cfg = s.dapt
        summary["schedule"] = plan(
            train_shard,
            batch_size=cfg.per_device_batch_size,
            grad_accum=cfg.grad_accum,
            epochs=cfg.num_epochs,
            max_steps=cfg.max_steps,
        ).model_dump()
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
