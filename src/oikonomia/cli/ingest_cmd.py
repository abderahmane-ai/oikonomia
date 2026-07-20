"""`oik ingest` subcommands: sync the corpus and build the processed table."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.ingest.build_corpus import BuildCorpusStage
from oikonomia.ingest.sync import ensure_corpus
from oikonomia.pipeline.stage import run_stage

ingest_app = typer.Typer(help="Corpus ingestion (Phase 1).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[
    list[str] | None,
    typer.Option("--set", help="Dotted config override, e.g. ingest.idp_git_rev=<sha>."),
]
ForceOpt = Annotated[bool, typer.Option("--force", help="Ignore cache and rerun.")]


@ingest_app.command("sync")
def sync(
    env: EnvOpt = "local",
    set_: SetOpt = None,
) -> None:
    """Clone/fetch idp.data at the pinned git rev into data/raw/."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    resolved = ensure_corpus(s.paths.raw, s.ingest.idp_repo_url, s.ingest.idp_git_rev)
    typer.echo(f"corpus ready at rev {resolved}")


@ingest_app.command("build")
def build(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    force: ForceOpt = False,
) -> None:
    """Parse + join the corpus into processed/corpus.parquet."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    manifest = run_stage(BuildCorpusStage(), s, force=force)
    typer.echo(json.dumps(manifest.stats, ensure_ascii=False, indent=2))


@ingest_app.command("report")
def report(env: EnvOpt = "local", set_: SetOpt = None) -> None:
    """Print the last ingest failure/coverage report."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    path = s.paths.processed / "ingest_failures.json"
    if not path.is_file():
        typer.echo("No ingest report found. Run `oik ingest build` first.")
        raise typer.Exit(code=1)
    typer.echo(path.read_text(encoding="utf-8"))
