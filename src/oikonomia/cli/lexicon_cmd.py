"""`oik lexicon` subcommands: mine candidate vocabulary, measure recall."""

from __future__ import annotations

import csv
import json
import sys
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.corpus.io import corpus_path, iter_batches
from oikonomia.labeling.evaluate import EVAL_COLUMNS, evaluate_coverage
from oikonomia.labeling.lexicon import load_lexicon
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.mine import MINE_COLUMNS, mine_batches
from oikonomia.labeling.weak_rules import BASELINE_COLUMNS, run_baseline

lexicon_app = typer.Typer(help="Lexicon mining and evaluation (Phase 2).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[
    list[str] | None,
    typer.Option("--set", help="Dotted config override."),
]


@lexicon_app.command("mine")
def mine(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    window: Annotated[int, typer.Option(help="Tokens of context each side of a numeral.")] = 2,
    min_docs: Annotated[int, typer.Option(help="Drop tokens seen in fewer documents.")] = 5,
    top: Annotated[int, typer.Option(help="How many candidates to emit.")] = 400,
) -> None:
    """Rank tokens adjacent to <num> elements — the raw material for a lexicon.

    Writes CSV to stdout. This is an input to human curation, not a lexicon.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    batches = iter_batches(corpus_path(s.paths.processed), MINE_COLUMNS)
    candidates = mine_batches(batches, window=window, min_docs=min_docs)

    writer = csv.writer(sys.stdout)
    writer.writerow(["token", "n_docs", "n_occurrences", "n_left", "n_right", "right_ratio", "forms"])
    for c in candidates[:top]:
        writer.writerow(
            [c.token, c.n_docs, c.n_occurrences, c.n_left, c.n_right, c.right_ratio,
             " ".join(c.example_forms)]
        )


@lexicon_app.command("eval")
def evaluate(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    view: Annotated[str, typer.Option(help="Text view to match on: edited | diplomatic.")] = "edited",
    top_gaps: Annotated[int, typer.Option(help="How many gap tokens to report.")] = 40,
    top_genres: Annotated[int, typer.Option(help="How many genres to report.")] = 12,
) -> None:
    """Measure lexicon coverage: what share of numerals get a unit attached."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    matcher = Matcher(load_lexicon(s.paths.resources))
    batches = iter_batches(corpus_path(s.paths.processed), EVAL_COLUMNS)
    report = evaluate_coverage(batches, matcher, view=view, top_gaps=top_gaps)

    payload = report.model_dump()
    payload["by_genre"] = payload["by_genre"][:top_genres]
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@lexicon_app.command("baseline")
def baseline(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    window: Annotated[int, typer.Option(help="Max characters between an amount and a term.")] = 40,
) -> None:
    """Run the Phase 2 proximity baseline — the bar the models must beat."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    matcher = Matcher(load_lexicon(s.paths.resources))
    batches = iter_batches(corpus_path(s.paths.processed), BASELINE_COLUMNS)
    report = run_baseline(batches, matcher, window=window)
    typer.echo(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
