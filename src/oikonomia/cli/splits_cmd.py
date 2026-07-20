"""`oik splits` subcommands: build and inspect the train/dev/test partition."""

from __future__ import annotations

import json
from typing import Annotated

import pandas as pd
import typer

from oikonomia.config import load_settings
from oikonomia.pipeline.stage import run_stage
from oikonomia.splits.build import OUTPUT_NAME, REPORT_NAME, BuildSplitsStage

splits_app = typer.Typer(help="Train/dev/test splits (Phase 3).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[
    list[str] | None,
    typer.Option("--set", help="Dotted config override, e.g. splits.dup_threshold=0.85."),
]
ForceOpt = Annotated[bool, typer.Option("--force", help="Ignore cache and rerun.")]


@splits_app.command("build")
def build(env: EnvOpt = "local", set_: SetOpt = None, force: ForceOpt = False) -> None:
    """Deduplicate, group, and assign documents to splits under both regimes."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    manifest = run_stage(BuildSplitsStage(), s, force=force)
    typer.echo(json.dumps(manifest.stats, ensure_ascii=False, indent=2))


@splits_app.command("report")
def report(env: EnvOpt = "local", set_: SetOpt = None) -> None:
    """Print the split report: sizes, stratum drift, duplicate clusters."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    path = s.paths.processed / REPORT_NAME
    if not path.is_file():
        typer.echo("No split report found. Run `oik splits build` first.")
        raise typer.Exit(code=1)
    typer.echo(path.read_text(encoding="utf-8"))


@splits_app.command("check")
def check(env: EnvOpt = "local", set_: SetOpt = None) -> None:
    """Verify the written split table: no group or duplicate cluster straddles a split.

    Re-checks the artifact on disk rather than the in-memory result, so a split
    that was corrupted or hand-edited after the fact is still caught.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    path = s.paths.processed / OUTPUT_NAME
    if not path.is_file():
        typer.echo("No split table found. Run `oik splits build` first.")
        raise typer.Exit(code=1)

    df = pd.read_parquet(path)
    problems: list[str] = []
    for regime in ("split_random", "split_chronological"):
        for key in ("group_id", "dup_cluster", "tm_id"):
            straddling = df.groupby(key)[regime].nunique()
            bad = straddling[straddling > 1]
            if len(bad):
                problems.append(f"{regime}: {len(bad)} {key}(s) span more than one split")

    summary = {
        "n_docs": len(df),
        "random": df.split_random.value_counts().to_dict(),
        "chronological": df.split_chronological.value_counts().to_dict(),
        "problems": problems,
    }
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if problems:
        raise typer.Exit(code=1)
