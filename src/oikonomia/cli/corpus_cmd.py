"""`oik corpus` subcommands: characterize the built corpus table."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.corpus.stats import corpus_stats

corpus_app = typer.Typer(help="Corpus characterization (Phase 2).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[
    list[str] | None,
    typer.Option("--set", help="Dotted config override, e.g. ingest.idp_git_rev=<sha>."),
]
TopOpt = Annotated[int, typer.Option("--top-genres", help="How many genres to list.")]


@corpus_app.command("stats")
def stats(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    top_genres: TopOpt = 15,
) -> None:
    """Recompute the corpus fact-ledger numbers from processed/corpus.parquet."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    result = corpus_stats(s.paths.processed / "corpus.parquet")

    payload = result.model_dump()
    payload["genres"] = payload["genres"][:top_genres]
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
