"""`oik silver` subcommands: measure a weak/silver labeler against gold (Phase 6).

The first Phase 6 tool. It runs the existing proximity baseline
(:mod:`oikonomia.labeling.weak_rules`) over the hand-drafted gold documents and
reports per-label precision/recall/F1 — the first time the labeler is scored
against anything rather than merely reporting yields.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from oikonomia.config import load_settings
from oikonomia.corpus.io import corpus_path, iter_batches
from oikonomia.gold.validate import read_jsonl
from oikonomia.labeling.lexicon import load_lexicon
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.score import Entity, Relation, build_report
from oikonomia.labeling.silver import (
    SilverLabeler,
    _derive_place_gazetteer,
    doc_spans,
    fit_label_dist,
    load_label_dist,
    load_patterns,
    save_label_dist,
)
from oikonomia.labeling.weak_rules import DEFAULT_WINDOW, WeakLabeling, label_document
from oikonomia.schemas.spans import CharSpan

LABEL_DIST_NAME = "silver_label_dist.json"

silver_app = typer.Typer(help="Weak/silver labeling and its evaluation (Phase 6).", no_args_is_help=True)

EnvOpt = Annotated[str, typer.Option("--env", help="Config environment: local | modal.")]
SetOpt = Annotated[list[str] | None, typer.Option("--set", help="Dotted config override.")]


def _load_numerals_and_lines(
    processed_root: Path, wanted_texts: set[str]
) -> dict[str, tuple[list[CharSpan], list[CharSpan]]]:
    """Corpus ``<num>`` and line spans (edited view) for the wanted texts only.

    Keyed by ``edited_text`` — which the gold ``text`` is byte-identical to
    (verified in Phase 5) — and stopped once every wanted text is found, so the
    large ``document_json`` column is only partially scanned.
    """
    out: dict[str, tuple[list[CharSpan], list[CharSpan]]] = {}
    for frame in iter_batches(corpus_path(processed_root), ["document_json"]):
        for blob in frame["document_json"]:
            doc = json.loads(blob)
            text = doc.get("edited_text")
            if text not in wanted_texts or text in out:
                continue
            numerals = [
                CharSpan(start=int(n["edited"]["start"]), end=int(n["edited"]["end"]))
                for n in doc.get("numerals", [])
                if n.get("edited")
            ]
            lines = [
                CharSpan(start=int(ln["edited"]["start"]), end=int(ln["edited"]["end"]))
                for ln in doc.get("lines", [])
                if ln.get("edited")
            ]
            out[text] = (numerals, lines)
        if len(out) == len(wanted_texts):
            break
    return out


@silver_app.command("distmap")
def distmap(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    sample: Annotated[int, typer.Option(help="Documents to learn from (0 = whole corpus).")] = 20000,
    min_count: Annotated[int, typer.Option(help="Drop forms seen fewer times.")] = 3,
    out: Annotated[
        Path | None, typer.Option("--out", help=f"Output JSON (default: processed/{LABEL_DIST_NAME}).")
    ] = None,
) -> None:
    """Tally each surface form's corpus label distribution (Move 2 input).

    NOT a majority-vote denoiser — that was validated harmful (it flips real
    places to persons). This table feeds a *directional* place gazetteer:
    forms that are place-dominant and almost never a person. Cache it once,
    then pass ``--place-gaz`` to ``score``/``label``.
    """
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    if not corpus_path(s.paths.processed).is_file():
        typer.echo("corpus.parquet absent — build it first (oik ingest build)", err=True)
        raise typer.Exit(code=1)

    base = SilverLabeler(Matcher(load_lexicon(s.paths.resources)), load_patterns(s.paths.resources))
    batches = _limited_batches(corpus_path(s.paths.processed), sample)
    dist = fit_label_dist(base, batches, min_count=min_count)

    out_path = out or Path(s.paths.processed) / LABEL_DIST_NAME
    save_label_dist(dist, out_path)

    gaz = _derive_place_gazetteer(dist, 5, 0.75, 0.15)
    typer.echo(
        json.dumps(
            {
                "out": str(out_path),
                "n_forms": len(dist),
                "place_gazetteer_size": len(gaz),
                "place_gazetteer_sample": sorted(gaz)[:20],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _limited_batches(path: Path, sample: int) -> Iterator[pd.DataFrame]:
    """Yield record batches, stopping once ``sample`` documents are seen."""
    if sample <= 0:
        yield from iter_batches(path, ["document_json"])
        return
    seen = 0
    for frame in iter_batches(path, ["document_json"]):
        if seen + len(frame) <= sample:
            seen += len(frame)
            yield frame
        else:
            yield frame.iloc[: sample - seen]
            return


@silver_app.command("score")
def score(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Gold JSONL (default: data/gold/annotated.jsonl)."),
    ] = None,
    window: Annotated[
        int, typer.Option(help="Max characters between an amount and a term.")
    ] = DEFAULT_WINDOW,
    labeler: Annotated[
        str, typer.Option(help="Which labeler to score: silver | baseline.")
    ] = "silver",
    place_gaz: Annotated[
        bool, typer.Option("--place-gaz/--no-place-gaz", help="Promote toponyms via corpus gazetteer.")
    ] = False,
    place_min_share: Annotated[
        float, typer.Option(help="Min place-share of a form to trust it as a toponym.")
    ] = 0.75,
    place_max_person: Annotated[
        float, typer.Option(help="Max person-share allowed for a gazetteer toponym.")
    ] = 0.15,
    json_out: Annotated[
        Path | None, typer.Option("--json-out", help="Also write the full report as JSON here.")
    ] = None,
) -> None:
    """Score a labeler against the gold draft, per label.

    ``--labeler silver`` (default) is the full Phase-6 labeler; ``baseline`` is
    the Phase-2 proximity rules alone. Requires ``data/processed/corpus.parquet``
    for the numeral and line spans the labeler reads. Gold is
    provenance=model_draft, so the numbers are agreement-with-draft, not
    ground-truth precision.
    """
    if labeler not in {"silver", "baseline"}:
        typer.echo(f"unknown labeler {labeler!r} (silver | baseline)", err=True)
        raise typer.Exit(code=1)
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    target = path or Path(s.paths.gold) / "annotated.jsonl"
    if not target.is_file():
        typer.echo(f"no gold at {target}", err=True)
        raise typer.Exit(code=1)
    if not corpus_path(s.paths.processed).is_file():
        typer.echo("corpus.parquet absent — build it first (oik ingest build)", err=True)
        raise typer.Exit(code=1)

    gold_docs = read_jsonl(target)
    wanted = {str(d.get("text", "")) for d in gold_docs}
    spans_by_text = _load_numerals_and_lines(s.paths.processed, wanted)
    matcher = Matcher(load_lexicon(s.paths.resources))
    dist = None
    if place_gaz:
        dist_path = Path(s.paths.processed) / LABEL_DIST_NAME
        if not dist_path.is_file():
            typer.echo(f"no label-dist at {dist_path} — build it with `oik silver distmap`", err=True)
            raise typer.Exit(code=1)
        dist = load_label_dist(dist_path)
    silver = (
        SilverLabeler(
            matcher,
            load_patterns(s.paths.resources),
            window=window,
            label_dist=dist,
            place_min_share=place_min_share,
            place_max_person_share=place_max_person,
        )
        if labeler == "silver"
        else None
    )

    def _predict(text: str, numerals: list[CharSpan], lines: list[CharSpan]) -> WeakLabeling:
        if silver is not None:
            return silver.label(text, numerals, lines)
        return label_document(text, numerals, lines, matcher, window=window)

    per_doc: list[tuple[list[Entity], list[Relation], list[Entity], list[Relation]]] = []
    scored = 0
    for doc in gold_docs:
        text = str(doc.get("text", ""))
        if text not in spans_by_text:
            continue
        numerals, lines = spans_by_text[text]
        pred = _predict(text, numerals, lines)

        gold_ents: list[Entity] = [
            (int(e["start"]), int(e["end"]), str(e["label"])) for e in doc.get("entities") or []
        ]
        gold_rels: list[Relation] = [
            (int(r["head"]), int(r["tail"]), str(r["type"])) for r in doc.get("relations") or []
        ]
        pred_ents: list[Entity] = [
            (e.span.start, e.span.end, e.label) for e in pred.entities
        ]
        pred_rels: list[Relation] = [(r.head, r.tail, r.type) for r in pred.relations]
        per_doc.append((gold_ents, gold_rels, pred_ents, pred_rels))
        scored += 1

    report = build_report(n_docs=len(gold_docs), n_docs_scored=scored, per_doc=per_doc)

    _print_summary(report)
    if json_out is not None:
        json_out.write_text(
            json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        typer.echo(f"\nfull report → {json_out}")


def _print_summary(report) -> None:  # type: ignore[no-untyped-def]
    """A compact, human-readable table plus the headline numbers."""
    typer.echo(f"scored {report.n_docs_scored}/{report.n_docs} gold docs")
    if report.n_docs_unmatched:
        typer.echo(f"  ({report.n_docs_unmatched} unmatched to corpus — skipped)")

    for score_obj, title in ((report.strict, "ENTITIES (exact span)"),
                             (report.relaxed, "ENTITIES (relaxed / overlap)")):
        typer.echo(f"\n{title}")
        typer.echo(f"  {'label':14} {'gold':>5} {'pred':>5} {'tp':>5} "
                   f"{'P':>6} {'R':>6} {'F1':>6}")
        for row in score_obj.by_label:
            typer.echo(f"  {row.label:14} {row.n_gold:>5} {row.n_pred:>5} {row.tp:>5} "
                       f"{row.precision:>6.3f} {row.recall:>6.3f} {row.f1:>6.3f}")
        typer.echo(f"  {'MICRO':14} {score_obj.n_gold:>5} {score_obj.n_pred:>5} "
                   f"{score_obj.tp:>5} {score_obj.precision:>6.3f} "
                   f"{score_obj.recall:>6.3f} {score_obj.f1:>6.3f}")

    typer.echo("\nRELATIONS (directed, endpoints span-matched)")
    typer.echo(f"  {'type':14} {'gold':>5} {'pred':>5} {'tp':>5} {'P':>6} {'R':>6} {'F1':>6}")
    for row in report.relations.by_type:
        typer.echo(f"  {row.label:14} {row.n_gold:>5} {row.n_pred:>5} {row.tp:>5} "
                   f"{row.precision:>6.3f} {row.recall:>6.3f} {row.f1:>6.3f}")
    rel = report.relations
    typer.echo(f"  {'MICRO':14} {rel.n_gold:>5} {rel.n_pred:>5} {rel.tp:>5} "
               f"{rel.precision:>6.3f} {rel.recall:>6.3f} {rel.f1:>6.3f}")

    if report.labeler_blind_labels:
        typer.echo(f"\nblind spots (labeler never emits): {', '.join(report.labeler_blind_labels)}")
    typer.echo(f"\n{report.caveat}")


@silver_app.command("label")
def label(
    env: EnvOpt = "local",
    set_: SetOpt = None,
    split: Annotated[
        str, typer.Option(help="Which split to label: train | all.")
    ] = "train",
    out: Annotated[
        Path | None, typer.Option("--out", help="Output JSONL (default: processed/silver.jsonl).")
    ] = None,
    exclude_gold: Annotated[
        bool, typer.Option(help="Skip documents already hand-drafted in gold.")
    ] = True,
    place_gaz: Annotated[
        bool, typer.Option("--place-gaz/--no-place-gaz", help="Promote toponyms via corpus gazetteer.")
    ] = True,
    min_confidence: Annotated[
        float, typer.Option(help="Abstain: drop spans/relations below this confidence.")
    ] = 0.0,
    limit: Annotated[int, typer.Option(help="Stop after N documents (0 = all).")] = 0,
) -> None:
    """Emit silver labels over the corpus — the Phase-6 training material.

    Writes one JSON object per document (same schema as gold, plus a per-span
    ``confidence``) with ``provenance: silver``. Silver is for *training*, so it
    defaults to the train split only and skips the gold documents (those get
    their reviewed labels instead), leaving dev/test untouched. Raise
    ``--min-confidence`` to abstain on the noisy tail rather than feed it.
    """
    if split not in {"train", "all"}:
        typer.echo(f"unknown split {split!r} (train | all)", err=True)
        raise typer.Exit(code=1)
    s = load_settings(env=env, overrides=set_ or [])  # type: ignore[arg-type]
    if not corpus_path(s.paths.processed).is_file():
        typer.echo("corpus.parquet absent — build it first (oik ingest build)", err=True)
        raise typer.Exit(code=1)

    train_ids: set[str] | None = None
    if split == "train":
        splits_file = Path(s.paths.processed) / "splits.parquet"
        if not splits_file.is_file():
            typer.echo("splits.parquet absent — build it first (oik splits build)", err=True)
            raise typer.Exit(code=1)
        sp = pd.read_parquet(splits_file, columns=["doc_id", "split_random"])
        train_ids = {str(d) for d in sp.loc[sp["split_random"] == "train", "doc_id"]}

    gold_ids: set[str] = set()
    if exclude_gold:
        gold_path = Path(s.paths.gold) / "annotated.jsonl"
        if gold_path.is_file():
            gold_ids = {str(d.get("doc_id")) for d in read_jsonl(gold_path)}

    dist = None
    dist_path = Path(s.paths.processed) / LABEL_DIST_NAME
    if (place_gaz or min_confidence > 0) and dist_path.is_file():
        dist = load_label_dist(dist_path)
    elif (place_gaz or min_confidence > 0) and not dist_path.is_file():
        typer.echo(f"  (no {LABEL_DIST_NAME}; run `oik silver distmap` for gazetteer/confidence)", err=True)
    labeler = SilverLabeler(
        Matcher(load_lexicon(s.paths.resources)),
        load_patterns(s.paths.resources),
        label_dist=dist,
    )
    out_path = out or Path(s.paths.processed) / "silver.jsonl"

    n_docs = n_entities = n_relations = 0
    by_label: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    with out_path.open("w", encoding="utf-8") as fh:
        for frame in iter_batches(corpus_path(s.paths.processed), ["stem", "document_json"]):
            for stem, blob in zip(frame["stem"], frame["document_json"], strict=True):
                doc_id = str(stem)
                if train_ids is not None and doc_id not in train_ids:
                    continue
                if doc_id in gold_ids:
                    continue
                doc = json.loads(blob)
                text = doc.get("edited_text") or ""
                if not text.strip():
                    continue
                numerals, lines = doc_spans(doc)
                pred = labeler.label(text, numerals, lines)

                # Abstain: drop spans below the confidence floor and remap the
                # relations that referenced them (dropping any now dangling).
                keep = [i for i, e in enumerate(pred.entities) if e.confidence >= min_confidence]
                remap = {old: new for new, old in enumerate(keep)}
                ents = [pred.entities[i] for i in keep]
                rels = [
                    r
                    for r in pred.relations
                    if r.head in remap and r.tail in remap and r.confidence >= min_confidence
                ]

                record = {
                    "doc_id": doc_id,
                    "text": text,
                    "entities": [
                        {
                            "start": e.span.start,
                            "end": e.span.end,
                            "label": e.label,
                            "confidence": round(e.confidence, 3),
                        }
                        for e in ents
                    ],
                    "relations": [
                        {
                            "head": remap[r.head],
                            "tail": remap[r.tail],
                            "type": r.type,
                            "confidence": round(r.confidence, 3),
                        }
                        for r in rels
                    ],
                    "provenance": "silver",
                    # Frozen tag, not a version to bump: it is baked into the
                    # 146 MB silver.jsonl on disk and on the Modal volume, whose
                    # sha is the stale-data canary `push`/`train` compare. Changing
                    # it re-emits the corpus and invalidates that fingerprint.
                    "labeler": "silver-v1",
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                n_docs += 1
                n_entities += len(ents)
                n_relations += len(rels)
                for e in ents:
                    by_label[e.label] += 1
                for r in rels:
                    by_type[r.type] += 1
                if limit and n_docs >= limit:
                    break
            if limit and n_docs >= limit:
                break

    typer.echo(
        json.dumps(
            {
                "out": str(out_path),
                "split": split,
                "n_docs": n_docs,
                "n_entities": n_entities,
                "n_relations": n_relations,
                "entities_per_doc": round(n_entities / n_docs, 2) if n_docs else 0.0,
                "by_label": dict(by_label.most_common()),
                "by_type": dict(by_type.most_common()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
