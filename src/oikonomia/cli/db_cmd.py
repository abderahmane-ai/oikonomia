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
from oikonomia.db.autonomy import guardian_curve
from oikonomia.db.dates import century as signed_century
from oikonomia.db.dates import date_mid, half_century_start
from oikonomia.db.export import TableSpec, build_manifest, document_index
from oikonomia.db.facts import DocMeta, Ent, Rel, assemble_monetary
from oikonomia.db.identity import collapse_to_persons
from oikonomia.db.personscan import PersonMeta, PersonObservation, assemble_persons
from oikonomia.db.places import load_place_names
from oikonomia.db.prices import SPECS, clean_prices, price_series
from oikonomia.db.principals import (
    PersonGender,
    PrincipalMeta,
    assemble_principals,
    primary_genre,
)
from oikonomia.db.taxes import clean_tax_payments, fiscal_regime, payments_by_century
from oikonomia.labeling.lexicon import load_lexicon
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.score import build_report
from oikonomia.labeling.silver import SilverLabeler, load_patterns
from oikonomia.schemas.spans import CharSpan

db_app = typer.Typer(help="Assemble the queryable economic database (Phase 9).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[list[str] | None, typer.Option("--set", help="Dotted config override.")]

_COLUMNS = ["tm_id", "date_lo", "date_hi", "place_pleiades", "canonical_genres", "document_json"]
FACTS_NAME = "db/monetary.parquet"
PRICES_NAME = "db/prices.parquet"
TAXES_NAME = "db/taxes.parquet"
PERSONS_NAME = "db/persons.parquet"
PRINCIPALS_NAME = "db/principals.parquet"
AUTONOMY_NAME = "db/autonomy.parquet"
NER_CORPUS_NAME = "ner/ner_corpus.jsonl"
RE_CORPUS_NAME = "re/re_corpus.jsonl"

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


# Taxes worth a regional cut (the poll tax varied by nome) or just a temporal one.
_POLL_TAX = "laographia"
_LAND_TAX = "demosia"


@db_app.command("taxes")
def taxes(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    facts: Annotated[Path | None, typer.Option("--facts", help="Fact table (default: processed/db/monetary.parquet).")] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Clean tax payments (default: processed/db/taxes.parquet).")] = None,
) -> None:
    """The fiscal-regime map + poll-tax payments by century and region.

    Prints (1) which named tax is attested in which era — the fiscal-regime shift,
    validated against the fiscal history — and (2) poll-tax (laographia) payment
    amounts by century and by place (payments, not rates: the poll tax was paid in
    installments). Writes the cleaned poll- and land-tax payments with provenance.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    facts_path = facts or (Path(s.paths.processed) / FACTS_NAME)
    if not facts_path.is_file():
        typer.secho(f"{facts_path} missing — run `oik db build` first.", fg="red")
        raise typer.Exit(1)
    df = pd.read_parquet(facts_path)

    typer.echo("=== FISCAL-REGIME MAP — tax attestations by era (validate vs fiscal history) ===")
    regime = fiscal_regime(df)
    cols = [c for c in ("Ptolemaic", "Roman", "Byzantine+") if c in regime.columns]
    typer.echo(f"  {'tax':20s} " + "".join(f"{c:>13s}" for c in cols) + f"{'total':>8s}")
    for tax, r in regime.iterrows():
        typer.echo(f"  {tax!s:20s} " + "".join(f"{int(r[c]):>13d}" for c in cols) + f"{int(r['total']):>8d}")
    typer.echo("  → laographia (poll tax) is Roman-only; demosia (land tax) dominates Byzantine — as known.")

    typer.echo(f"\n=== POLL TAX ({_POLL_TAX}) — silver payments, median [IQR] by century ===")
    typer.echo("    (payments, NOT the rate: the poll tax was paid in installments)")
    for _, r in payments_by_century(df, _POLL_TAX, min_n=5).iterrows():
        typer.echo(f"  {_cen(r['century']):>7}: {r['median']:6.1f} [{r['p25']:.1f}-{r['p75']:.1f}] dr  (n={int(r['n'])})")
    lao = clean_tax_payments(df, _POLL_TAX)
    typer.echo(f"    full-payment tail (p90) = {lao['payment'].quantile(0.9):.0f} dr — cf. the known annual capitation ~16-40 dr/nome")

    # Regional cut: poll-tax payments by place name (top places by attestation).
    names = load_place_names(s.paths.processed)
    lp = lao[lao["place_pleiades"].notna()].copy()
    lp["place"] = lp["place_pleiades"].map(lambda p: names.get(int(p), f"Pleiades:{int(p)}"))
    typer.echo("\n=== POLL TAX by place (top by n) — regional variation ===")
    g = lp.groupby("place")["payment"].agg(["median", "count"]).sort_values("count", ascending=False)
    for place, r in g.head(8).iterrows():
        typer.echo(f"  {place!s:22s} median {r['median']:6.1f} dr  (n={int(r['count'])})")

    kept = pd.concat(
        [clean_tax_payments(df, _POLL_TAX).assign(tax=_POLL_TAX),
         clean_tax_payments(df, _LAND_TAX).assign(tax=_LAND_TAX)],
        ignore_index=True,
    )
    out_path = out or (Path(s.paths.processed) / TAXES_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    kept.to_parquet(out_path, index=False)
    typer.echo(f"\nWrote {out_path}: {len(kept)} clean tax payments (poll + land tax, with provenance)")


def _share(sub: pd.DataFrame) -> tuple[int, int, float | None]:
    """(n_female, n_gendered, female_share) over a party frame."""
    gendered = sub[sub["gender"].isin(["female", "male"])]
    nf = int((gendered["gender"] == "female").sum())
    ng = len(gendered)
    return nf, ng, (nf / ng if ng else None)


# --- persons: gender over the model's PERSON spans (the autonomy input) -------


def _model_persons(settings: Any) -> Iterator[PersonObservation]:
    """Gender+guardian rows from the trained model's PERSON spans (``ner_corpus.jsonl``).

    Loads the PERSON spans per ``stem``, then streams ``corpus.parquet`` to join the
    exact document text (for the guardian frame) and the HGV date/place/genre. The
    join is on ``stem`` — the unique key — not ``tm_id`` (which repeats across rows).
    """
    ner_path = Path(settings.paths.processed) / NER_CORPUS_NAME
    by_stem: dict[str, list[Ent]] = {}
    with ner_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            ents = [
                Ent(e["start"], e["end"], e["label"], e["text"], None, 1.0)
                for e in r.get("entities", [])
                if e["label"] == "PERSON"
            ]
            if ents:
                by_stem[str(r["stem"])] = ents

    cols = ["stem", "tm_id", "edited_text", "date_lo", "date_hi", "place_pleiades", "canonical_genres"]
    for frame in iter_batches(corpus_path(settings.paths.processed), cols):
        for stem, tm_id, text, dlo, dhi, place, genres in zip(
            frame["stem"], frame["tm_id"], frame["edited_text"],
            frame["date_lo"], frame["date_hi"], frame["place_pleiades"], frame["canonical_genres"],
            strict=True,
        ):
            person_ents = by_stem.get(str(stem))
            if person_ents is None:
                continue
            mid = date_mid(_clean(dlo), _clean(dhi))
            place_i = _clean(place)
            meta = PersonMeta(
                stem=str(stem),
                tm_id=str(tm_id),
                date_mid=mid,
                century=signed_century(mid),
                bin50=half_century_start(mid),
                place_pleiades=int(place_i) if place_i is not None else None,
                genres=_genres_str(genres),
            )
            yield from assemble_persons(person_ents, text or "", meta)


@db_app.command("persons")
def persons(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    out: Annotated[Path | None, typer.Option("--out", help="Person table (default: processed/db/persons.parquet).")] = None,
) -> None:
    """Gender + guardian for every model-extracted PERSON — the autonomy finding's input.

    Runs the deterministic gender rules over the trained model's corpus-scale PERSON
    spans (``ner_corpus.jsonl``, keyed by stem), splitting each blob to gender the
    head and typing the guardian formula (μετὰ vs χωρὶς κυρίου). Writes one row per
    PERSON mention with full provenance, and prints the women's share and the
    with-vs-without-guardian split — the autonomy signal step 5 turns into a curve.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    if not (Path(s.paths.processed) / NER_CORPUS_NAME).is_file():
        typer.secho(
            f"{NER_CORPUS_NAME} missing — run the corpus NER inference first "
            "(oik ner corpus-text → modal ner.py::infer → pull down).",
            fg="red",
        )
        raise typer.Exit(1)
    if not corpus_path(s.paths.processed).is_file():
        typer.secho("corpus.parquet missing — run `oik ingest build` first.", fg="red")
        raise typer.Exit(1)

    rows = list(_model_persons(s))
    df = pd.DataFrame([r.model_dump() for r in rows])
    out_path = out or (Path(s.paths.processed) / PERSONS_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    _summarize_persons(df, out_path)


def _summarize_persons(df: pd.DataFrame, out_path: Path) -> None:
    typer.echo(f"\nWrote {out_path}: {len(df)} PERSON mentions (model spans, gender-attributed)")
    if df.empty:
        typer.echo("  (no persons found)")
        return
    nf, ng, share = _share(df)
    cov = ng / len(df) if len(df) else 0.0
    typer.echo(f"  gender-attributable: {ng}/{len(df)} ({cov:.0%})   [unknown: {len(df) - ng}]")
    if share is not None:
        typer.echo(f"  women's share among gendered mentions: {nf}/{ng} = {share:.1%}")

    typer.echo("\n  gender basis breakdown (which rule fired):")
    for (gen, basis), n in df.groupby(["gender", "gender_basis"]).size().sort_values(ascending=False).items():
        if gen != "unknown":
            typer.echo(f"    {gen:7} via {basis:12} {n:>8,}")

    # THE autonomy signal: among women who carry a guardian formula, with vs without.
    fem = df[df["gender"] == "female"]
    g = fem["guardian"].value_counts().to_dict()
    n_with, n_without = int(g.get("with", 0)), int(g.get("without", 0))
    formulaic = n_with + n_without
    typer.echo(f"\n  women with a guardian FORMULA: {formulaic:,} of {len(fem):,} female mentions")
    if formulaic:
        typer.echo(f"    μετὰ κυρίου  (with guardian):    {n_with:>7,} ({n_with / formulaic:.0%})")
        typer.echo(f"    χωρὶς κυρίου (without / autonomous): {n_without:>7,} ({n_without / formulaic:.0%})")
        typer.echo("    → step 5 breaks this by century and region into the autonomy curve.")

    typer.echo("\n  female sample (person | head | father | basis | guardian):")
    for _, r in fem[fem["guardian"] != "none"].head(10).iterrows():
        typer.echo(
            f"    {_txt(r['person_text'])[:24]:26} {_txt(r['head_text'], '')[:14]:15} "
            f"{_txt(r['father_text'])[:12]:13} {r['gender_basis']:10} {r['guardian']}"
        )


def _txt(v: object, default: str = "-") -> str:
    """A parquet cell to a clean one-line string (NaN/None → default; no newlines)."""
    return v.replace("\n", " ") if isinstance(v, str) else default


# --- autonomy: the with- vs without-guardian curve over time and region -------


@db_app.command("autonomy")
def autonomy(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    min_n: Annotated[int, typer.Option("--min-n", help="Min guardian-formula women per bucket.")] = 8,
    out: Annotated[Path | None, typer.Option("--out", help="Curve table (default: processed/db/autonomy.parquet).")] = None,
) -> None:
    """The autonomy curve — women transacting WITH vs WITHOUT a guardian, by era + region.

    Reads the person table (``oik db persons``) and, among the women who carry a
    guardian formula, reports the share acting *without* a guardian (χωρὶς κυρίου —
    legal autonomy) by century and by region. The headline of the women finding;
    every bucket traces back to gendered, guardian-typed spans with provenance.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    persons_path = Path(s.paths.processed) / PERSONS_NAME
    if not persons_path.is_file():
        typer.secho(f"{PERSONS_NAME} missing — run `oik db persons` first.", fg="red")
        raise typer.Exit(1)
    df = pd.read_parquet(persons_path)

    fem = df[(df["gender"] == "female") & (df["guardian"].isin(["with", "without"]))]
    n_with = int((fem["guardian"] == "with").sum())
    n_without = int((fem["guardian"] == "without").sum())
    total = n_with + n_without
    typer.echo("=== AUTONOMY — women transacting with (μετὰ) vs without (χωρὶς) a guardian ===")
    if not total:
        typer.secho("  no guardian-formula women found — is db/persons.parquet populated?", fg="red")
        raise typer.Exit(1)
    typer.echo(f"  overall: {total} women with a guardian formula — "
               f"{n_without} without ({n_without / total:.0%} autonomous) / {n_with} with")

    cen = guardian_curve(df, "century", min_n=min_n)
    typer.echo(f"\n  BY CENTURY (min n={min_n}) — autonomous share = χωρὶς / (μετὰ+χωρὶς):")
    for _, r in cen.iterrows():
        typer.echo(f"    {_cen(r['bucket']):>7}: {r['autonomous_share']:5.0%} autonomous "
                   f"({int(r['n_without'])} χωρὶς / {int(r['n'])} total)")

    # Region cut: resolve Pleiades ids to nome/place names, then the same curve.
    names = load_place_names(s.paths.processed)
    reg_df = df.copy()
    reg_df["region"] = reg_df["place_pleiades"].map(
        lambda p: names.get(int(p)) if pd.notna(p) else None
    )
    reg = guardian_curve(reg_df, "region", min_n=min_n)
    typer.echo(f"\n  BY REGION (min n={min_n}):")
    for _, r in reg.sort_values("n", ascending=False).iterrows():
        typer.echo(f"    {_txt(r['bucket'])[:22]:24}: {r['autonomous_share']:5.0%} autonomous "
                   f"({int(r['n_without'])} χωρὶς / {int(r['n'])} total)")

    all_curves = pd.concat(
        [cen.assign(dimension="century"), reg.assign(dimension="region")],
        ignore_index=True,
    )
    # century buckets are ints, region buckets strings — store one uniform string
    # column so the frame is parquet-typeable; `dimension` says how to read it.
    all_curves["bucket"] = all_curves["bucket"].astype(str)
    out_path = out or (Path(s.paths.processed) / AUTONOMY_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_curves.to_parquet(out_path, index=False)
    typer.echo(f"\nWrote {out_path}: {len(all_curves)} curve buckets (century + region)")


# --- validate the women pipeline (steps 3-5) against the 115-doc human gold ----


def _guardian_women(rows: list[PersonObservation]) -> tuple[int, int]:
    """(n_with, n_without) female principals carrying a guardian formula."""
    fem = [r for r in rows if r.gender == "female" and r.guardian in ("with", "without")]
    return (
        sum(1 for r in fem if r.guardian == "with"),
        sum(1 for r in fem if r.guardian == "without"),
    )


@db_app.command("validate-women")
def validate_women(env: EnvOpt = "local", set_: SetOpt = None) -> None:
    """Validate the women pipeline (steps 3-5) against the 115-doc human gold.

    Gold has human PERSON spans but no gender (sex is not annotated — the rules
    supply it), so this runs the *same* pipeline on gold spans and on the model's
    spans over the same 115 docs and compares: (A) PERSON extraction quality
    (model vs gold), (B) whether the model recovers the same guardian-bearing
    women, (C) gender agreement on exactly-matched spans. It isolates extraction
    error from rule error — the honest test of whether the corpus autonomy numbers
    are trustworthy.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    gold_path = Path(s.paths.gold) / "annotated.jsonl"
    ner_path = Path(s.paths.processed) / NER_CORPUS_NAME
    if not gold_path.is_file() or not ner_path.is_file():
        typer.secho("need data/gold/annotated.jsonl and ner_corpus.jsonl (run steps 1-2).", fg="red")
        raise typer.Exit(1)

    gold_docs = [json.loads(x) for x in gold_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    gold_ids = {str(d["doc_id"]) for d in gold_docs}
    model_by_id: dict[str, list[Ent]] = {}
    with ner_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["stem"] in gold_ids:
                model_by_id[r["stem"]] = [
                    Ent(e["start"], e["end"], "PERSON", e["text"], None, 1.0)
                    for e in r.get("entities", []) if e["label"] == "PERSON"
                ]

    per_doc: list[Any] = []
    gold_rows: list[PersonObservation] = []
    model_rows: list[PersonObservation] = []
    gender_by_span: dict[tuple[str, int, int], tuple[str, str]] = {}  # (doc,s,e)->(gold_g, model_g)
    for d in gold_docs:
        did, text = str(d["doc_id"]), d.get("text", "")
        gold_p = [Ent(e["start"], e["end"], "PERSON", e["text"], None, 1.0)
                  for e in d.get("entities", []) if e["label"] == "PERSON"]
        model_p = model_by_id.get(did, [])
        per_doc.append((
            [(e.start, e.end, e.label) for e in gold_p], [],
            [(e.start, e.end, e.label) for e in model_p], [],
        ))
        mid = _clean((d.get("meta") or {}).get("date_mid"))
        meta = PersonMeta(
            stem=did, tm_id=did, date_mid=mid, century=signed_century(mid),
            bin50=half_century_start(mid), place_pleiades=None,
            genres=str((d.get("meta") or {}).get("genre") or ""),
        )
        g_rows = assemble_persons(gold_p, text, meta)
        m_rows = assemble_persons(model_p, text, meta)
        gold_rows += g_rows
        model_rows += m_rows
        gm = {(r.person_start, r.person_end): r.gender for r in m_rows}
        for r in g_rows:  # gender agreement on exactly-matched spans
            key = (r.person_start, r.person_end)
            if key in gm:
                gender_by_span[(did, *key)] = (r.gender, gm[key])

    # A. PERSON extraction quality (model vs gold) on the checkable docs
    rep = build_report(n_docs=len(gold_docs), n_docs_scored=len(gold_docs), per_doc=per_doc)
    ps = next((r for r in rep.strict.by_label if r.label == "PERSON"), None)
    pr = next((r for r in rep.relaxed.by_label if r.label == "PERSON"), None)
    typer.echo("=== VALIDATE WOMEN PIPELINE vs 115-doc gold ===")
    typer.echo(f"\n  A. PERSON extraction (model vs gold, {len(gold_docs)} docs):")
    if ps and pr:
        typer.echo(f"     strict : P {ps.precision:.2f}  R {ps.recall:.2f}  F1 {ps.f1:.2f}")
        typer.echo(f"     relaxed: P {pr.precision:.2f}  R {pr.recall:.2f}  F1 {pr.f1:.2f}"
                   f"   (gold {ps.n_gold} PERSON, model {ps.n_pred})")

    # B. Guardian-women recovery: gold-fed vs model-fed pipeline
    gw, gwo = _guardian_women(gold_rows)
    mw, mwo = _guardian_women(model_rows)
    typer.echo("\n  B. Guardian-bearing women (same rules, gold spans vs model spans):")
    typer.echo(f"     gold spans : {gw + gwo:3} women  ({gw} μετὰ / {gwo} χωρὶς)")
    typer.echo(f"     model spans: {mw + mwo:3} women  ({mw} μετὰ / {mwo} χωρὶς)")
    if gw + gwo:
        typer.echo(f"     → model recovers {(mw + mwo) / (gw + gwo):.0%} of the gold guardian-women count")

    # C. Gender agreement where a model span exactly matches a gold span
    matched = list(gender_by_span.values())
    agree = sum(1 for g, m in matched if g == m)
    typer.echo(f"\n  C. Gender agreement on {len(matched)} exactly-matched PERSON spans:")
    if matched:
        typer.echo(f"     agree {agree}/{len(matched)} = {agree / len(matched):.0%} "
                   "(same text+rules; disagreement = span-boundary effects)")
    typer.echo("\n  (model checkpoint provenance silver-vs-gold-FT unverified — if gold-FT, "
               "PERSON F1 here is optimistic; the B/C comparison is the load-bearing check.)")


# --- principals: women as principals across deal types (step 8, RE-driven) -----


def _int(x: object) -> int | None:
    f = _clean(x)
    return int(f) if f is not None else None


def _person_gender_index(
    persons_df: pd.DataFrame,
) -> tuple[dict[str, dict[tuple[int, int], PersonGender]], dict[str, PrincipalMeta]]:
    """Index the person table by ``stem`` → span → gender, plus per-doc metadata.

    The person table (``oik db persons``) is the authority for gender/guardian/
    father *and* the document's date/place/genre (doc-level fields, identical
    across a stem's rows). Both are joined onto the RE principals by the PERSON's
    exact ``(start, end)`` span — the same NER span both tables were built from.
    """
    gender: dict[str, dict[tuple[int, int], PersonGender]] = {}
    meta: dict[str, PrincipalMeta] = {}
    for row in persons_df.itertuples(index=False):
        stem = str(row.stem)
        gender.setdefault(stem, {})[(int(row.person_start), int(row.person_end))] = PersonGender(
            gender=str(row.gender),
            gender_basis=str(row.gender_basis),
            gender_confidence=float(row.gender_confidence),
            guardian=str(row.guardian),
            head_text=_txt(row.head_text, "") or None,
            father_text=_txt(row.father_text, "") or None,
        )
        if stem not in meta:
            meta[stem] = PrincipalMeta(
                stem=stem,
                tm_id=str(row.tm_id),
                date_mid=_clean(row.date_mid),
                century=_int(row.century),
                bin50=_int(row.bin50),
                place_pleiades=_int(row.place_pleiades),
                genres=str(row.genres or ""),
            )
    return gender, meta


@db_app.command("principals")
def principals(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    re_corpus: Annotated[Path | None, typer.Option("--re-corpus", help="RE edges (default: processed/re/re_corpus.jsonl).")] = None,
    persons: Annotated[Path | None, typer.Option("--persons", help="Person table (default: processed/db/persons.parquet).")] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Principal table (default: processed/db/principals.parquet).")] = None,
) -> None:
    """Women as principals across deal types — the RE-driven women finding (step 8).

    Reads the saved RE model's corpus edges (``re_corpus.jsonl``), keeps the
    people the deal turns on (``PARTY_OF`` / ``PAID_*`` heads), and joins each to
    the validated gender + guardian + patronymic from the person table (steps
    3-4). Reports the women's share among named principals overall, **by deal type
    (genre)** and by century, plus the guardian split and the CHILD_OF kinship
    coverage. Every row keeps its span and rule-of-record, so the share is
    auditable. The extraction engine is the trained NER+RE pair (end-to-end
    PARTY_OF ≈ 0.62), not rules.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    re_path = re_corpus or (Path(s.paths.processed) / RE_CORPUS_NAME)
    persons_path = persons or (Path(s.paths.processed) / PERSONS_NAME)
    if not re_path.is_file():
        typer.secho(
            f"{re_path} missing — run the corpus RE inference first "
            "(modal_app/relations.py::infer → modal volume get /predictions/re_corpus.jsonl).",
            fg="red",
        )
        raise typer.Exit(1)
    if not persons_path.is_file():
        typer.secho(f"{persons_path} missing — run `oik db persons` first.", fg="red")
        raise typer.Exit(1)

    gender_by_stem, meta_by_stem = _person_gender_index(pd.read_parquet(persons_path))
    rows: list[dict[str, object]] = []
    with re_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            doc = json.loads(line)
            stem = str(doc["stem"])
            ents = [
                Ent(int(e["start"]), int(e["end"]), str(e["label"]), str(e.get("text", "")), None, 1.0)
                for e in doc.get("entities", [])
            ]
            rels = [
                Rel(int(r["head"]), int(r["tail"]), str(r["type"]), float(r.get("confidence", 1.0)))
                for r in doc.get("relations", [])
            ]
            meta = meta_by_stem.get(stem) or PrincipalMeta(
                stem=stem, tm_id=str(doc.get("tm_id")), date_mid=None,
                century=None, bin50=None, place_pleiades=None, genres="",
            )
            for p in assemble_principals(ents, rels, gender_by_stem.get(stem, {}), meta):
                rows.append(p.model_dump())

    df = pd.DataFrame(rows)
    out_path = out or (Path(s.paths.processed) / PRINCIPALS_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    _summarize_principals(df, out_path)


def _summarize_principals(df: pd.DataFrame, out_path: Path) -> None:
    typer.echo(f"\nWrote {out_path}: {len(df)} principals (RE PARTY_OF/PAID_* heads, gendered)")
    if df.empty:
        typer.echo("  (no principals found — is re_corpus.jsonl populated?)")
        return
    nf, ng, share = _share(df)
    cov = ng / len(df) if len(df) else 0.0
    typer.echo(f"  gender-attributable: {ng:,}/{len(df):,} ({cov:.0%})   [unknown: {len(df) - ng:,}]")
    if share is not None:
        typer.echo(f"  WOMEN'S SHARE among named principals: {nf:,}/{ng:,} = {share:.1%}")

    typer.echo("\n  WOMEN AS PRINCIPALS BY DEAL TYPE (genre, min n=15 attributable):")
    for g, sub in sorted(df.groupby("deal_type"), key=lambda kv: -len(kv[1])):
        nf, ng, sh = _share(sub)
        if ng >= 15 and g:
            typer.echo(f"    {g!s:18}: women {nf:4,}/{ng:5,} = {sh:.0%}")

    typer.echo("\n  by century (min n=15 attributable):")
    for cen, sub in sorted(df.groupby("century"), key=lambda kv: (kv[0] is None, kv[0])):
        nf, ng, sh = _share(sub)
        if ng >= 15 and cen is not None:
            typer.echo(f"    {_cen(cen):>7}: women {nf:4,}/{ng:5,} = {sh:.0%}")

    # Guardian split among women principals — the autonomy axis, now on principals.
    fem = df[df["gender"] == "female"]
    gv = fem["guardian"].value_counts().to_dict()
    n_with, n_without = int(gv.get("with", 0)), int(gv.get("without", 0))
    formulaic = n_with + n_without
    typer.echo(f"\n  women principals with a guardian FORMULA: {formulaic:,} of {len(fem):,}")
    if formulaic:
        typer.echo(f"    μετὰ κυρίου  (with):    {n_with:>6,} ({n_with / formulaic:.0%})")
        typer.echo(f"    χωρὶς κυρίου (without): {n_without:>6,} ({n_without / formulaic:.0%})")

    # Kinship coverage — the split-person CHILD_OF (patronymic) the finding can join.
    kin = int(fem["father_text"].map(lambda v: isinstance(v, str) and bool(v)).sum())
    typer.echo(f"  women principals with a recovered patronymic (CHILD_OF): {kin:,}/{len(fem):,}")

    typer.echo("\n  gender basis breakdown (which rule fired):")
    for (gen, basis), n in df.groupby(["gender", "gender_basis"]).size().sort_values(ascending=False).items():
        if gen != "unknown":
            typer.echo(f"    {gen:7} via {basis:12} {n:>8,}")

    typer.echo("\n  female-principal sample (person | father | guardian | roles | deal):")
    for _, r in fem[fem["guardian"] != "none"].head(12).iterrows():
        typer.echo(
            f"    {_txt(r['person_text'])[:24]:26} {_txt(r['father_text'])[:12]:13} "
            f"{r['guardian']:8} {r['roles']:12} {_txt(r['deal_type'], '')}"
        )


# --- export: package the derived tables into a queryable database (deliverable #2) -


EXPORT_DIRNAME = "db/export"


def _read_or_empty(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.is_file() else pd.DataFrame()


def _document_universe(settings: Any) -> pd.DataFrame:
    """One row per real text document (stem, tm_id, century, place, deal_type).

    The spine of the exported database: the 61,249 non-empty documents, with the
    corpus's own HGV date (→ century) and genre (→ deal type). Empty documents are
    filtered on the text (never on a char count — whitespace lies).
    """
    cols = ["stem", "tm_id", "edited_text", "date_lo", "date_hi", "place_pleiades", "canonical_genres"]
    rows: list[dict[str, object]] = []
    for frame in iter_batches(corpus_path(settings.paths.processed), cols):
        for stem, tm_id, text, dlo, dhi, place, genres in zip(
            frame["stem"], frame["tm_id"], frame["edited_text"],
            frame["date_lo"], frame["date_hi"], frame["place_pleiades"], frame["canonical_genres"],
            strict=True,
        ):
            if not (text or "").strip():
                continue
            mid = date_mid(_clean(dlo), _clean(dhi))
            place_i = _clean(place)
            rows.append({
                "stem": str(stem),
                "tm_id": str(tm_id),
                "century": signed_century(mid),
                "place_pleiades": int(place_i) if place_i is not None else None,
                "deal_type": primary_genre(_genres_str(genres)),
            })
    return pd.DataFrame(rows)


@db_app.command("export")
def export(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir", help="Export directory (default: processed/db/export).")] = None,
) -> None:
    """Package the derived tables into a documented, queryable database (deliverable #2).

    Writes a per-document index (``documents.parquet`` — the spine everything hangs
    off, keyed on ``stem`` with per-doc person/principal/money counts + price/tax
    flags), a coreference-lite distinct-person table (``persons_distinct.parquet``
    — folds principal *mentions* into people so "N distinct women", not mentions,
    is answerable), and a machine-readable ``manifest.json`` (table inventory +
    the pinned corpus revision every span traces to). The schema is documented in
    ``docs/database.md``.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    if not corpus_path(s.paths.processed).is_file():
        typer.secho("corpus.parquet missing — run `oik ingest build` first.", fg="red")
        raise typer.Exit(1)
    proc = Path(s.paths.processed)

    docs = _document_universe(s)
    persons_df = _read_or_empty(proc / PERSONS_NAME)
    principals_df = _read_or_empty(proc / PRINCIPALS_NAME)
    monetary_df = _read_or_empty(proc / FACTS_NAME)
    prices_df = _read_or_empty(proc / PRICES_NAME)
    taxes_df = _read_or_empty(proc / TAXES_NAME)

    idx = document_index(docs, persons_df, principals_df, monetary_df, prices_df, taxes_df)
    distinct = collapse_to_persons(principals_df) if not principals_df.empty else pd.DataFrame()

    export_dir = out_dir or (proc / EXPORT_DIRNAME)
    export_dir.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(export_dir / "documents.parquet", index=False)
    distinct.to_parquet(export_dir / "persons_distinct.parquet", index=False)

    specs: list[tuple[TableSpec, pd.DataFrame]] = [
        (TableSpec("documents", "one text document", "stem", "the spine: metadata + per-doc counts + price/tax flags"), idx),
        (TableSpec("persons_distinct", "one distinct person (coref-lite)", "person_id", "principal mentions folded into people"), distinct),
        (TableSpec("monetary", "one monetary fact", "tm_id + char-span", "money amount + its commodity/quantity/tax links, normalized"), monetary_df),
        (TableSpec("prices", "one clean price observation", "tm_id + char-span", "commodity unit-price (dr/unit), high-precision subset"), prices_df),
        (TableSpec("taxes", "one clean tax payment", "tm_id + char-span", "poll- and land-tax payments"), taxes_df),
        (TableSpec("persons", "one PERSON mention", "stem + char-span", "gender + guardian for every model PERSON span"), persons_df),
        (TableSpec("principals", "one principal mention", "stem + char-span", "PARTY_OF/PAID_* heads, gendered, deal-typed"), principals_df),
    ]
    specs = [(spec, df) for spec, df in specs if not df.empty]
    manifest = build_manifest(specs, corpus_rev=str(s.ingest.idp_git_rev))
    (export_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _summarize_export(idx, distinct, specs, export_dir)


def _summarize_export(
    idx: pd.DataFrame, distinct: pd.DataFrame,
    specs: list[tuple[TableSpec, pd.DataFrame]], export_dir: Path,
) -> None:
    typer.echo(f"\nExported database → {export_dir}  ({len(specs)} tables, see manifest.json)")
    typer.echo(f"  documents.parquet: {len(idx):,} documents (the spine)")
    if not idx.empty:
        with_prin = int((idx["n_principals"] > 0).sum())
        with_price = int(idx["has_price"].sum())
        with_tax = int(idx["has_tax"].sum())
        typer.echo(f"    with a principal: {with_prin:,}   with a price: {with_price:,}   with a tax: {with_tax:,}")

    if not distinct.empty:
        typer.echo(f"  persons_distinct.parquet: {len(distinct):,} distinct people (coref-lite)")
        g = distinct[distinct["gender"].isin(["male", "female"])]
        nf = int((g["gender"] == "female").sum())
        ng = len(g)
        if ng:
            typer.echo(f"    DISTINCT women principals: {nf:,} of {ng:,} gendered = {nf / ng:.1%} "
                       "(vs the mention-level share — the honest headcount)")
        auto = distinct[(distinct["gender"] == "female") & (distinct["guardian"].isin(["with", "without"]))]
        if len(auto):
            nwo = int((auto["guardian"] == "without").sum())
            typer.echo(f"    distinct women with a guardian formula: {len(auto):,}  "
                       f"({nwo} χωρὶς / autonomous)")

    typer.echo("\n  tables in the manifest:")
    for spec, df in specs:
        typer.echo(f"    {spec.name:18} {len(df):>8,} rows  ({spec.grain})")
