"""Join DDbDP text with HGV metadata into the processed corpus table.

This is the terminal Phase-1 stage. It walks every DDbDP edition, parses it into
a :class:`~oikonomia.schemas.document.Document`, joins the matching HGV metadata
by TM id, attaches any English translation, and emits one row per document to
``processed/corpus.parquet`` plus a parse-failure report.

Row design: fast scalar columns for filtering/stratification (dates, genre,
numeral counts, damage) *and* two lossless JSON columns (`document_json`,
`hgv_json`) so the offset map, markup spans, and numerals survive round-trip
without re-opening XML. Every downstream stage reads this table, never the raw
corpus.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from oikonomia.config import Settings
from oikonomia.ingest import paths as idp_paths
from oikonomia.ingest.epidoc_text import parse_ddbdp
from oikonomia.ingest.hgv_genre import load_genre_map
from oikonomia.ingest.hgv_meta import parse_hgv
from oikonomia.ingest.sync import corpus_dir
from oikonomia.ingest.translations import parse_translation
from oikonomia.logging import get_logger
from oikonomia.pipeline.stage import StageContext
from oikonomia.schemas.document import Document
from oikonomia.schemas.metadata import HgvMetadata

logger = get_logger(__name__)

CORPUS_PARQUET = "corpus.parquet"
FAILURE_REPORT = "ingest_failures.json"


def iter_ddbdp_files(corpus_root: Path) -> Iterator[Path]:
    """Yield every DDbDP edition XML path under a corpus checkout, sorted."""
    ddb = corpus_root / idp_paths.DDBDP_DIR
    yield from sorted(ddb.rglob("*.xml"))


def _row(doc: Document, hgv: HgvMetadata | None, translation: str | None) -> dict[str, Any]:
    primary_date = hgv.primary_date if hgv else None
    primary_place = hgv.primary_place if hgv else None
    return {
        "tm_id": doc.tm_id,
        "stem": doc.stem,
        "ddb_hybrid": doc.ddb_hybrid,
        "edited_text": doc.edited_text,
        "diplomatic_text": doc.diplomatic_text,
        "n_chars_edited": len(doc.edited_text),
        "n_numerals": doc.n_numerals,
        "damage_ratio": round(doc.damage_ratio(), 4),
        "has_hgv": hgv is not None,
        "date_lo": primary_date.lo if primary_date else None,
        "date_hi": primary_date.hi if primary_date else None,
        "date_precision": primary_date.precision.value if primary_date else None,
        "n_alt_dates": sum(d.is_alternative for d in hgv.dates) if hgv else 0,
        "place_tm": primary_place.trismegistos_geo_id if primary_place else None,
        "place_pleiades": primary_place.pleiades_id if primary_place else None,
        "canonical_genres": json.dumps(hgv.canonical_genres if hgv else [], ensure_ascii=False),
        "hgv_terms": json.dumps(hgv.hgv_terms if hgv else [], ensure_ascii=False),
        "title": hgv.title if hgv else None,
        "has_translation": translation is not None,
        "parse_flags": json.dumps(
            doc.parse_flags + (hgv.parse_flags if hgv else []), ensure_ascii=False
        ),
        "document_json": doc.model_dump_json(),
        "hgv_json": hgv.model_dump_json() if hgv else None,
        "translation_en": translation,
    }


def _find_translation(corpus_root: Path, tm_id: int) -> str | None:
    """Return the first English translation text for ``tm_id``, if any."""
    bucket = corpus_root / idp_paths.translations_bucket(tm_id)
    if not bucket.is_dir():
        return None
    for path in sorted(bucket.glob(f"{tm_id}-*.xml")):
        seq_str = path.stem.split("-")[-1]
        seq = int(seq_str) if seq_str.isdigit() else 1
        try:
            td = parse_translation(path.read_bytes(), tm_id, seq)
        except Exception:
            continue
        if td and (td.lang is None or td.lang.startswith("en")):
            return td.text
    return None


def build_rows(
    corpus_root: Path, genre_map: dict[str, dict[str, str]], cfg: Settings
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse and join the whole corpus. Returns ``(rows, failure_report)``."""
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    n_total = n_hgv = 0

    for xml_path in iter_ddbdp_files(corpus_root):
        stem = xml_path.stem
        n_total += 1
        try:
            doc = parse_ddbdp(xml_path.read_bytes(), stem, cfg.ingest)
        except Exception as exc:
            failures.append({"stem": stem, "path": str(xml_path), "error": repr(exc)})
            continue

        hgv: HgvMetadata | None = None
        hgv_rel = idp_paths.hgv_meta_relpath(stem)
        hgv_path = corpus_root / hgv_rel
        if hgv_path.is_file():
            try:
                numeric, _ = idp_paths.parse_stem(stem)
                hgv = parse_hgv(hgv_path.read_bytes(), numeric, genre_map)
                n_hgv += 1
            except Exception as exc:
                failures.append({"stem": stem, "path": str(hgv_path), "error": f"hgv: {exc!r}"})

        translation = _find_translation(corpus_root, doc.tm_id)
        rows.append(_row(doc, hgv, translation))

    report = {
        "n_ddbdp": n_total,
        "n_parsed": len(rows),
        "n_failed": len(failures),
        "parse_rate": round(len(rows) / n_total, 4) if n_total else 0.0,
        "n_with_hgv": n_hgv,
        "hgv_join_rate": round(n_hgv / len(rows), 4) if rows else 0.0,
        "failures": failures[:500],  # cap the embedded list; count is authoritative
    }
    return rows, report


def write_corpus_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    """Write the corpus rows to parquet atomically (temp + rename)."""
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    pd.DataFrame(rows).to_parquet(tmp, index=False)
    tmp.replace(path)


class BuildCorpusStage:
    """Pipeline stage: raw idp.data checkout → ``processed/corpus.parquet``."""

    name = "build_corpus"
    # 2: parse with collect_ids=False, recovering the 512 duplicate-xml:id files.
    version = "2"

    def inputs_key(self, s: Settings) -> str:
        # The pinned corpus rev is the exact, cheap fingerprint of all inputs.
        return f"idp@{s.ingest.idp_git_rev or 'UNPINNED'}"

    def params(self, s: Settings) -> dict[str, Any]:
        return {
            "gap_placeholder": s.ingest.gap_placeholder,
            "drop_non_greek_langs": s.ingest.drop_non_greek_langs,
        }

    def outputs(self, s: Settings) -> list[Path]:
        return [s.paths.processed / CORPUS_PARQUET, s.paths.processed / FAILURE_REPORT]

    def run(self, ctx: StageContext) -> dict[str, float | int | str]:
        s = ctx.settings
        s.paths.ensure_writable()
        genre_map = load_genre_map(s.paths.resources / "genre_map.yaml")
        root = corpus_dir(s.paths.raw)
        if not root.is_dir():
            msg = f"Corpus not found at {root}. Run the sync step first."
            raise FileNotFoundError(msg)

        rows, report = build_rows(root, genre_map, s)
        write_corpus_parquet(rows, s.paths.processed / CORPUS_PARQUET)
        (s.paths.processed / FAILURE_REPORT).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            f"build_corpus: parsed={report['n_parsed']} failed={report['n_failed']} "
            f"hgv_join_rate={report['hgv_join_rate']}"
        )
        return {
            "n_parsed": report["n_parsed"],
            "n_failed": report["n_failed"],
            "parse_rate": report["parse_rate"],
            "hgv_join_rate": report["hgv_join_rate"],
        }
