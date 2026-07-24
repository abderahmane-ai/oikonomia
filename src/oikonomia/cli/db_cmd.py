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
from oikonomia.db.dates import century as signed_century
from oikonomia.db.dates import date_mid, half_century_start
from oikonomia.db.facts import DocMeta, Ent, Rel, assemble_monetary
from oikonomia.db.name_gender import Votes, build_gazetteer, load_gazetteer, save_gazetteer
from oikonomia.db.parties import PartyMeta, PartyObservation, assemble_parties
from oikonomia.db.places import load_place_names
from oikonomia.db.prices import SPECS, clean_prices, price_series
from oikonomia.db.taxes import clean_tax_payments, fiscal_regime, payments_by_century
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
TAXES_NAME = "db/taxes.parquet"
PARTIES_NAME = "db/parties.parquet"
NAMES_NAME = "db/name_gender.json"

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


# --- women as economic principals (deliverable #3) ---------------------------


def _gold_parties(gold_path: Path, gazetteer: dict[str, str]) -> Iterator[PartyObservation]:
    """Party rows from the human gold: trustworthy PERSON spans + PARTY_OF edges.

    The prototype path — it isolates the gender/party logic from labeler noise, so
    the women-share it reports reflects the *rules*, not extraction error. Gold's
    own ``meta`` carries the date midpoint and genre; place is not annotated there.
    """
    for line in gold_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        ents = [
            Ent(e["start"], e["end"], e["label"], e["text"], None, 1.0)
            for e in doc.get("entities", [])
        ]
        rels = [Rel(r["head"], r["tail"], r["type"], 1.0) for r in doc.get("relations", [])]
        meta_in = doc.get("meta", {})
        mid = _clean(meta_in.get("date_mid"))
        meta = PartyMeta(
            doc_id=str(doc.get("doc_id")),
            date_mid=mid,
            century=signed_century(mid),
            bin50=half_century_start(mid),
            place_pleiades=None,
            genres=str(meta_in.get("genre") or ""),
        )
        yield from assemble_parties(ents, rels, doc.get("text", ""), meta, gazetteer)


def _corpus_parties(settings: Any, sample: int, gazetteer: dict[str, str]) -> Iterator[PartyObservation]:
    """Party rows from the rule labeler over the corpus — a noisy *lower bound*.

    Uses the deterministic labeler (PERSON 71.6% precise, PARTY_OF conf 0.28), so
    the women-share here is an under-precise estimate; the trained model (a Modal
    run) is the higher-quality path when the finding warrants the spend.
    """
    labeler = SilverLabeler(Matcher(load_lexicon(settings.paths.resources)), load_patterns(settings.paths.resources))
    for frame in _iter_docs(settings.paths.processed, sample):
        for tm_id, dlo, dhi, place, genres, blob in zip(
            frame["tm_id"], frame["date_lo"], frame["date_hi"],
            frame["place_pleiades"], frame["canonical_genres"], frame["document_json"],
            strict=True,
        ):
            doc = json.loads(blob)
            text = doc.get("edited_text") or ""
            if not text.strip():
                continue
            nums = [CharSpan(start=int(n["edited"]["start"]), end=int(n["edited"]["end"]))
                    for n in doc.get("numerals", []) if n.get("edited")]
            lines = [CharSpan(start=int(ln["edited"]["start"]), end=int(ln["edited"]["end"]))
                     for ln in doc.get("lines", []) if ln.get("edited")]
            pred = labeler.label(text, nums, lines)
            ents = [Ent(e.span.start, e.span.end, e.label, e.text, e.entry_id, e.confidence) for e in pred.entities]
            rels = [Rel(r.head, r.tail, r.type, r.confidence) for r in pred.relations]
            place_i = _clean(place)
            mid = date_mid(_clean(dlo), _clean(dhi))
            meta = PartyMeta(
                doc_id=str(tm_id),
                date_mid=mid,
                century=signed_century(mid),
                bin50=half_century_start(mid),
                place_pleiades=int(place_i) if place_i is not None else None,
                genres=_genres_str(genres),
            )
            yield from assemble_parties(ents, rels, text, meta, gazetteer)


@db_app.command("women")
def women(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    source: Annotated[str, typer.Option("--source", help="gold (validated logic) | corpus (rule labeler, noisy).")] = "gold",
    sample: Annotated[int, typer.Option("--sample", help="corpus only: max docs (0 = whole corpus).")] = 0,
    gazetteer: Annotated[bool, typer.Option("--gazetteer/--no-gazetteer", help="Use the corpus-learned name→gender map (if built).")] = True,
    out: Annotated[Path | None, typer.Option("--out", help="Party observations (default: processed/db/parties.parquet).")] = None,
) -> None:
    """Women as economic principals — gender of the parties to transactions.

    Assembles a party table (one row per named principal, gender-attributed) and
    reports the women's share among gender-attributable principals, overall and by
    century and transaction type, plus the guardian (``κύριος``) breakdown. Every
    attribution keeps its rule-of-record and span, so the share is auditable.

    ``--source gold`` (default) runs over the human annotations — the honest test
    of the logic. ``--source corpus`` runs the rule labeler over the corpus, a
    noisy lower bound (the trained model is the higher-quality path, spent later).
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    gaz: dict[str, str] = {}
    if gazetteer:
        gaz = load_gazetteer(Path(s.paths.processed) / NAMES_NAME)
        if gaz:
            typer.echo(f"using corpus name gazetteer: {len(gaz)} names")
        else:
            typer.secho("no name gazetteer found — run `oik db names` first for higher coverage.", fg="yellow")
    if source == "gold":
        gold_path = Path(s.paths.gold) / "annotated.jsonl"
        if not gold_path.is_file():
            typer.secho(f"{gold_path} missing.", fg="red")
            raise typer.Exit(1)
        rows = list(_gold_parties(gold_path, gaz))
    elif source == "corpus":
        if not corpus_path(s.paths.processed).is_file():
            typer.secho("corpus.parquet missing — run `oik ingest build` first.", fg="red")
            raise typer.Exit(1)
        rows = list(_corpus_parties(s, sample, gaz))
    else:
        typer.secho(f"unknown --source {source!r} (expected gold | corpus)", fg="red")
        raise typer.Exit(1)

    df = pd.DataFrame([r.model_dump() for r in rows])
    out_path = out or (Path(s.paths.processed) / PARTIES_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    _summarize_women(df, source, out_path)


def _share(sub: pd.DataFrame) -> tuple[int, int, float | None]:
    """(n_female, n_gendered, female_share) over a party frame."""
    gendered = sub[sub["gender"].isin(["female", "male"])]
    nf = int((gendered["gender"] == "female").sum())
    ng = len(gendered)
    return nf, ng, (nf / ng if ng else None)


def _summarize_women(df: pd.DataFrame, source: str, out_path: Path) -> None:
    typer.echo(f"\nWrote {out_path}: {len(df)} principals ({source}) — one row per named party")
    if df.empty:
        typer.echo("  (no principals found)")
        return
    nf, ng, share = _share(df)
    cov = ng / len(df) if len(df) else 0.0
    typer.echo(f"  gender-attributable: {ng}/{len(df)} ({cov:.0%})   [unknown gender: {len(df) - ng}]")
    if share is not None:
        typer.echo(f"  WOMEN'S SHARE among attributable principals: {nf}/{ng} = {share:.1%}")

    typer.echo("\n  by century (min n=8 attributable):")
    for cen, sub in sorted(df.groupby("century"), key=lambda kv: (kv[0] is None, kv[0])):
        nf, ng, sh = _share(sub)
        if ng >= 8 and cen is not None:
            typer.echo(f"    {_cen(cen):>7}: women {nf:3}/{ng:3} = {sh:.0%}")

    typer.echo("\n  by transaction type (genre, min n=8 attributable):")
    prim = df.assign(_g=df["genres"].map(lambda x: (x.split("|")[0] if x else "?") or "?"))
    for g, sub in sorted(prim.groupby("_g"), key=lambda kv: -len(kv[1])):
        nf, ng, sh = _share(sub)
        if ng >= 8:
            typer.echo(f"    {g!s:16}: women {nf:3}/{ng:3} = {sh:.0%}")

    # Guardian (κύριος): the legal marker of a woman transacting.
    fem = df[df["gender"] == "female"]
    if not fem.empty:
        wg = int(fem["guardian_present"].sum())
        typer.echo(f"\n  guardian (κύριος) formula present for {wg}/{len(fem)} female principals")

    # Attribution provenance — how the gender was decided (auditability).
    typer.echo("\n  gender basis breakdown:")
    for (gen, basis), n in df.groupby(["gender", "gender_basis"]).size().sort_values(ascending=False).items():
        if gen != "unknown":
            typer.echo(f"    {gen:7} via {basis:13} {n}")

    # A hand-checkable sample of female principals (the precision spot-check).
    typer.echo("\n  female-principal sample (person | basis | guardian | roles | tx):")
    for _, r in fem.head(12).iterrows():
        guard = "κύριος" if r["guardian_present"] else "-"
        typer.echo(f"    {r['person_text'][:26]:28} {r['gender_basis']:12} {guard:7} {r['roles']:12} {r['transaction_term'] or ''}")


@db_app.command("names")
def names(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    sample: Annotated[int, typer.Option("--sample", help="Max docs to scan (0 = whole corpus).")] = 0,
    min_attest: Annotated[int, typer.Option("--min-attest", help="Min decisive attestations to keep a name.")] = 3,
    min_agree: Annotated[float, typer.Option("--min-agree", help="Min majority-gender share to keep a name.")] = 0.85,
    out: Annotated[Path | None, typer.Option("--out", help="Gazetteer JSON (default: processed/db/name_gender.json).")] = None,
) -> None:
    """Build the corpus name→gender gazetteer — the coverage lever (no external data).

    Scans the corpus with the rule labeler, votes each name-form's gender from its
    *decisive* attestations (guardian / nomen / kin / Egyptian prefix), and keeps
    the forms that vote consistently (:mod:`oikonomia.db.name_gender`). The map
    propagates that evidence to bare-name occurrences, lifting `oik db women`
    coverage. Deterministic, laptop, auditable.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    if not corpus_path(s.paths.processed).is_file():
        typer.secho("corpus.parquet missing — run `oik ingest build` first.", fg="red")
        raise typer.Exit(1)

    labeler = SilverLabeler(Matcher(load_lexicon(s.paths.resources)), load_patterns(s.paths.resources))
    votes = Votes()
    n_docs = 0
    for frame in _iter_docs(s.paths.processed, sample):
        for blob in frame["document_json"]:
            doc = json.loads(blob)
            text = doc.get("edited_text") or ""
            if not text.strip():
                continue
            n_docs += 1
            nums = [CharSpan(start=int(n["edited"]["start"]), end=int(n["edited"]["end"]))
                    for n in doc.get("numerals", []) if n.get("edited")]
            lines = [CharSpan(start=int(ln["edited"]["start"]), end=int(ln["edited"]["end"]))
                     for ln in doc.get("lines", []) if ln.get("edited")]
            pred = labeler.label(text, nums, lines)
            for e in pred.entities:
                if e.label == "PERSON":
                    votes.add(e.text, text[e.span.end : e.span.end + 44])

    gaz = build_gazetteer(votes, min_attest=min_attest, min_agree=min_agree)
    out_path = out or (Path(s.paths.processed) / NAMES_NAME)
    save_gazetteer(gaz, out_path)
    nfem = sum(v == "female" for v in gaz.values())
    typer.echo(f"\nWrote {out_path}: {len(gaz)} names ({nfem} female / {len(gaz) - nfem} male) from {n_docs} docs")
    typer.echo(f"  thresholds: ≥{min_attest} decisive attestations, ≥{min_agree:.0%} agreement")
