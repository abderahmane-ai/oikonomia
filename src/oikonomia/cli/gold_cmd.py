"""`oik gold` subcommands: select documents for hand annotation (Phase 5)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.gold.sample import OUTPUT_NAME, build_sample, write_jsonl
from oikonomia.gold.validate import validate_file
from oikonomia.labeling.lexicon import load_lexicon
from oikonomia.labeling.matcher import Matcher

gold_app = typer.Typer(help="Gold annotation batches (Phase 5).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[list[str] | None, typer.Option("--set", help="Dotted config override.")]


@gold_app.command("sample")
def sample(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    n: Annotated[int, typer.Option(help="Documents to annotate.")] = 150,
    iaa: Annotated[int, typer.Option(help="Of those, flagged for double annotation.")] = 30,
    blind: Annotated[int, typer.Option(help="Of those, with NO baseline suggestions.")] = 30,
    seed: Annotated[int, typer.Option(help="Sampling seed.")] = 17,
    suggest: Annotated[bool, typer.Option(help="Attach baseline pre-annotations.")] = True,
) -> None:
    """Export a stratified train-split batch to data/gold/to_annotate.jsonl."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    matcher = Matcher(load_lexicon(s.paths.resources)) if suggest else None
    docs = build_sample(
        s, n=n, seed=seed, iaa_n=iaa, blind_n=blind, suggest=suggest, matcher=matcher
    )
    out = Path(s.paths.gold) / OUTPUT_NAME
    write_jsonl(docs, out)

    genres = Counter(d.meta["genre"] for d in docs)
    eras = Counter(d.meta["date_bucket"] for d in docs)
    typer.echo(
        json.dumps(
            {
                "path": str(out),
                "n_docs": len(docs),
                "double_annotate": sum(d.double_annotate for d in docs),
                "blind_no_suggestions": sum(d.suggested_entities is None for d in docs),
                "total_chars": sum(d.meta["n_chars"] for d in docs),
                "by_genre": dict(genres.most_common()),
                "by_era": dict(eras.most_common()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@gold_app.command("check")
def check(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    path: Annotated[
        Path | None, typer.Option("--path", help="Annotated JSONL (default: data/gold/annotated.jsonl).")
    ] = None,
    fix: Annotated[
        bool, typer.Option("--fix", help="Rewrite offsets to match each span's own text.")
    ] = False,
    limit: Annotated[int, typer.Option(help="Problems to print.")] = 40,
) -> None:
    """Verify every annotated span selects the text it claims, and relations point the right way."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    target = path or Path(s.paths.gold) / "annotated.jsonl"
    if not target.is_file():
        typer.echo(f"no annotations at {target}", err=True)
        raise typer.Exit(code=1)

    report = validate_file(target, fix=fix)
    for problem in report.problems[:limit]:
        typer.echo(f"  [{problem.kind}] doc {problem.doc_id} #{problem.index}: {problem.detail}")
    if len(report.problems) > limit:
        typer.echo(f"  ... and {len(report.problems) - limit} more")

    typer.echo(
        json.dumps(
            {
                "path": str(target),
                "n_docs": report.n_docs,
                "n_entities": report.n_entities,
                "n_relations": report.n_relations,
                "n_repaired": report.n_repaired,
                "n_problems": len(report.problems),
                "by_kind": report.by_kind(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not report.ok:
        raise typer.Exit(code=1)
