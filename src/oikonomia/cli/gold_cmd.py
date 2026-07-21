"""`oik gold` subcommands: select documents for hand annotation (Phase 5)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from oikonomia.config import load_settings
from oikonomia.corpus.io import corpus_path, iter_batches
from oikonomia.gold.sample import OUTPUT_NAME, build_sample, write_jsonl
from oikonomia.gold.validate import read_jsonl, validate_file
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


def _load_gold_numerals(
    processed_root: Path, wanted_texts: set[str]
) -> dict[str, list[tuple[int, int, str]]]:
    """Corpus ``<num>`` tags (edited-view offsets) for the gold documents only.

    Keyed by ``edited_text`` and stopped as soon as every wanted text is found,
    so the 280 MB ``document_json`` column is only partially scanned.
    """
    out: dict[str, list[tuple[int, int, str]]] = {}
    for frame in iter_batches(corpus_path(processed_root), ["document_json"]):
        for blob in frame["document_json"]:
            doc = json.loads(blob)
            text = doc.get("edited_text")
            if text not in wanted_texts or text in out:
                continue
            numerals: list[tuple[int, int, str]] = []
            for num in doc.get("numerals", []):
                edited = num.get("edited")
                if edited:
                    numerals.append(
                        (int(edited["start"]), int(edited["end"]), str(num.get("text", "")))
                    )
            out[text] = numerals
        if len(out) == len(wanted_texts):
            break
    return out


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
    limit: Annotated[int, typer.Option(help="Problems to print.")] = 60,
) -> None:
    """Verify spans select their text, relations point the right way, and every numeral is decided."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    target = path or Path(s.paths.gold) / "annotated.jsonl"
    if not target.is_file():
        typer.echo(f"no annotations at {target}", err=True)
        raise typer.Exit(code=1)

    # The numeral-coverage gate needs the corpus's own <num> tags. If the
    # processed corpus is absent (clean checkout), fall back to the offset and
    # relation checks and say so, rather than failing.
    wanted = {str(d.get("text", "")) for d in read_jsonl(target)}
    numerals_by_text = None
    if corpus_path(s.paths.processed).is_file():
        numerals_by_text = _load_gold_numerals(s.paths.processed, wanted)
    else:
        typer.echo("  (corpus.parquet absent — numeral-coverage gate skipped)", err=True)

    report = validate_file(target, fix=fix, numerals_by_text=numerals_by_text)

    errors, advisories = report.errors, report.advisories
    for problem in errors[:limit]:
        typer.echo(f"  [{problem.kind}] doc {problem.doc_id} #{problem.index}: {problem.detail}")
    if len(errors) > limit:
        typer.echo(f"  ... and {len(errors) - limit} more errors")
    if advisories:
        typer.echo(f"  --- {len(advisories)} advisories (review, not failures) ---")
        for problem in advisories[:limit]:
            typer.echo(f"  [{problem.kind}] doc {problem.doc_id} #{problem.index}: {problem.detail}")
        if len(advisories) > limit:
            typer.echo(f"  ... and {len(advisories) - limit} more advisories")

    typer.echo(
        json.dumps(
            {
                "path": str(target),
                "n_docs": report.n_docs,
                "n_entities": report.n_entities,
                "n_relations": report.n_relations,
                "n_repaired": report.n_repaired,
                "numerals_checked": report.numerals_checked,
                "n_errors": len(errors),
                "n_advisories": len(advisories),
                "by_kind": report.by_kind(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not report.ok:
        raise typer.Exit(code=1)
