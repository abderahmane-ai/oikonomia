"""`oik db` subcommands: assemble the queryable economic database (Phase 9).

``build`` runs the deterministic labeler over the corpus, walks each document's
relation graph into monetary fact rows (:mod:`oikonomia.db.facts`), joins the
corpus's own HGV date + Pleiades place, and writes a parquet fact table — the
first actual rows of deliverable #2. GPU-free and laptop-only: no learned model
is invoked, so every fact traces to a lexicon id, a decoded ``<num>`` and a
character span.

``build`` also prints a **validation view** — median wheat price per artaba by
century, silver system — the first number a papyrologist can check against the
published price literature (Rathbone, Bagnall).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
import typer

from oikonomia.config import load_settings
from oikonomia.corpus.io import corpus_path, iter_batches
from oikonomia.db.facts import DocMeta, Ent, Rel, assemble_monetary
from oikonomia.db.prices import SPECS, clean_prices, price_series
from oikonomia.labeling.lexicon import load_lexicon
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.silver import SilverLabeler, load_patterns
from oikonomia.schemas.spans import CharSpan

db_app = typer.Typer(help="Assemble the queryable economic database (Phase 9).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[list[str] | None, typer.Option("--set", help="Dotted config override.")]

_COLUMNS = ["tm_id", "date_lo", "date_hi", "place_pleiades", "canonical_genres", "document_json"]
FACTS_NAME = "db/monetary.parquet"
PRICES_NAME = "db/prices.parquet"

# Published anchors for the validation view (dr/artaba), so the series is judged
# against scholarship, not eyeballed. Rough consensus ranges, not point claims.
_WHEAT_LIT = {"Ptolemaic (3-1c BC)": "~1-2", "Roman (1-2c AD)": "~7-12", "3c AD+": "inflation ↑"}


def _clean(x: object) -> float | None:
    """A parquet cell to float|None (NaN/None -> None)."""
    if x is None:
        return None
    try:
        f = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN check


def _genres_str(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, (list, tuple)):
        return "|".join(str(g) for g in x)
    return str(x)


def _value_by_span(doc: dict[str, Any]) -> dict[tuple[int, int], float]:
    """Map each decoded ``<num>`` edited span to its value."""
    out: dict[tuple[int, int], float] = {}
    for n in doc.get("numerals", []):
        ed = n.get("edited")
        val = n.get("value")
        if ed and val is not None:
            out[(int(ed["start"]), int(ed["end"]))] = float(val)
    return out


def _iter_docs(processed_root: Path, sample: int) -> Iterator[pd.DataFrame]:
    batches = iter_batches(corpus_path(processed_root), _COLUMNS)
    seen = 0
    for frame in batches:
        if sample and seen >= sample:
            return
        if sample and seen + len(frame) > sample:
            frame = frame.iloc[: sample - seen]
        seen += len(frame)
        yield frame


@db_app.command("build")
def build(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    sample: Annotated[int, typer.Option("--sample", help="Max docs (0 = whole corpus).")] = 12000,
    out: Annotated[Path | None, typer.Option("--out", help="Output parquet (default: processed/db/monetary.parquet).")] = None,
) -> None:
    """Assemble monetary facts from the corpus and write the fact table."""
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    if not corpus_path(s.paths.processed).is_file():
        typer.secho("corpus.parquet missing — run `oik ingest build` first.", fg="red")
        raise typer.Exit(1)

    labeler = SilverLabeler(Matcher(load_lexicon(s.paths.resources)), load_patterns(s.paths.resources))
    rows: list[dict[str, object]] = []
    n_docs = 0
    for frame in _iter_docs(s.paths.processed, sample):
        for tm_id, dlo, dhi, place, genres, blob in zip(
            frame["tm_id"], frame["date_lo"], frame["date_hi"],
            frame["place_pleiades"], frame["canonical_genres"], frame["document_json"],
            strict=True,
        ):
            doc = json.loads(blob)
            text = doc.get("edited_text") or ""
            if not text.strip():
                continue
            n_docs += 1
            vbs = _value_by_span(doc)
            nums = [CharSpan(start=s0, end=e0) for (s0, e0) in vbs]
            lines = [
                CharSpan(start=int(ln["edited"]["start"]), end=int(ln["edited"]["end"]))
                for ln in doc.get("lines", []) if ln.get("edited")
            ]
            pred = labeler.label(text, nums, lines)
            ents = [
                Ent(e.span.start, e.span.end, e.label, e.text, e.entry_id, e.confidence)
                for e in pred.entities
            ]
            rels = [Rel(r.head, r.tail, r.type, r.confidence) for r in pred.relations]
            place_i = _clean(place)
            meta = DocMeta(
                tm_id=str(tm_id),
                date_lo=_clean(dlo),
                date_hi=_clean(dhi),
                place_pleiades=int(place_i) if place_i is not None else None,
                genres=_genres_str(genres),
            )
            for o in assemble_monetary(ents, rels, vbs, meta):
                rows.append(o.model_dump())

    df = pd.DataFrame(rows)
    out_path = out or (Path(s.paths.processed) / FACTS_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    _summarize(df, n_docs, out_path)


def _summarize(df: pd.DataFrame, n_docs: int, out_path: Path) -> None:
    typer.echo(f"\nWrote {out_path}: {len(df)} monetary facts from {n_docs} docs")
    if df.empty:
        return
    norm = df[df["value_base"].notna()]
    typer.echo(f"  normalizable (value + known denomination): {len(norm)} ({len(norm) / len(df):.0%})")
    by_sys = df["system"].value_counts().to_dict()
    typer.echo(f"  by monetary system: {by_sys}")
    priced = df[df["commodity_id"].notna()]
    typer.echo(f"  commodity-linked (a price): {len(priced)}")
    if not priced.empty:
        top = priced["commodity_id"].value_counts().head(8).to_dict()
        typer.echo(f"  top priced commodities: {top}")

    # Validation view: the CLEANED wheat series (see db/prices.py), not the raw
    # ratio — median by century vs the published literature.
    ser = price_series(df, SPECS["wheat"], bucket="century", min_n=4)
    if not ser.empty:
        typer.echo("\n  WHEAT price (dr/artaba), cleaned median [IQR] by century — vs Rathbone/Bagnall:")
        for _, r in ser.iterrows():
            typer.echo(f"    {_cen(r['century']):>7}: {r['median']:7.2f} [{r['p25']:.1f}-{r['p75']:.1f}]  (n={int(r['n'])})")
        typer.echo(f"    literature: {_WHEAT_LIT}")
    else:
        typer.echo("\n  (no clean wheat/artaba prices in this sample — widen --sample)")


def _cen(c: float) -> str:
    c = int(c)
    return f"{abs(c)}c {'BC' if c < 0 else 'AD'}"


@db_app.command("prices")
def prices(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    facts: Annotated[Path | None, typer.Option("--facts", help="Fact table (default: processed/db/monetary.parquet).")] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Cleaned price observations (default: processed/db/prices.parquet).")] = None,
) -> None:
    """Clean commodity price observations into a series (median [IQR] n per century).

    Reads the monetary fact table, applies the price-cleaning rules
    (:mod:`oikonomia.db.prices`), writes the surviving per-observation prices
    (auditable, with provenance) and prints the per-century series per staple.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    facts_path = facts or (Path(s.paths.processed) / FACTS_NAME)
    if not facts_path.is_file():
        typer.secho(f"{facts_path} missing — run `oik db build` first.", fg="red")
        raise typer.Exit(1)
    df = pd.read_parquet(facts_path)

    kept: list[pd.DataFrame] = []
    for name, spec in SPECS.items():
        clean = clean_prices(df, spec)
        kept.append(clean.assign(commodity=name))
        ser = price_series(df, spec, bucket="century", min_n=4)
        head = f"{name} ({spec.unit}, dr/{spec.unit})"
        typer.echo(f"\n=== {head} — {len(clean)} clean obs ===")
        if ser.empty:
            typer.echo("  (too few clean observations for a series)")
            continue
        for _, r in ser.iterrows():
            typer.echo(f"  {_cen(r['century']):>7}: {r['median']:7.2f} [{r['p25']:.1f}-{r['p75']:.1f}]  (n={int(r['n'])})")
    typer.echo(f"\n  wheat literature anchors: {_WHEAT_LIT}")

    out_path = out or (Path(s.paths.processed) / PRICES_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_clean = pd.concat(kept, ignore_index=True) if kept else pd.DataFrame()
    all_clean.to_parquet(out_path, index=False)
    typer.echo(f"\nWrote {out_path}: {len(all_clean)} clean price observations (with provenance)")
