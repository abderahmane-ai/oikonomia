"""End-to-end ingestion: mini raw corpus → corpus.parquet with joined metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from oikonomia.config import Settings, load_settings
from oikonomia.ingest.build_corpus import BuildCorpusStage
from oikonomia.ingest.sync import corpus_dir
from oikonomia.pipeline.stage import run_stage

REPO = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_corpus_settings(tmp_path: Path) -> Settings:
    """Assemble a one-document idp.data checkout in the real bucket layout."""
    s = load_settings(
        "local",
        overrides=[
            f"paths.root={tmp_path}",
            f"paths.resources={REPO / 'resources'}",  # use the shipped genre map
            "ingest.idp_git_rev=testrev",
        ],
    )
    root = corpus_dir(s.paths.raw)
    (root / "DDbDP" / "100").mkdir(parents=True)
    (root / "HGV_meta_EpiDoc" / "HGV101").mkdir(parents=True)
    (root / "DDbDP" / "100" / "100042.xml").write_bytes(
        (FIXTURES / "ddb" / "100042.xml").read_bytes()
    )
    (root / "HGV_meta_EpiDoc" / "HGV101" / "100042.xml").write_bytes(
        (FIXTURES / "hgv" / "100042.xml").read_bytes()
    )
    return s


def test_build_corpus_joins_text_and_metadata(mini_corpus_settings: Settings) -> None:
    s = mini_corpus_settings
    run_stage(BuildCorpusStage(), s)

    df = pd.read_parquet(s.paths.processed / "corpus.parquet")
    assert len(df) == 1
    row = df.iloc[0]

    assert row["tm_id"] == 100042
    assert row["ddb_hybrid"] == "sb;30;17708"
    assert row["has_hgv"]
    assert len(row["edited_text"]) > 0
    assert row["n_numerals"] >= 1

    # Date joined from HGV: exact day in 50 CE.
    assert row["date_lo"] == 50 and row["date_hi"] == 50
    assert row["date_precision"] == "day"

    # Linked place (Soknopaiu Nesos) from <provenance>.
    assert row["place_tm"] == 2157

    # Genre mapping: Vertrag→contract, Kauf→sale.
    assert json.loads(row["canonical_genres"]) == ["contract", "sale"]

    # The lossless document JSON round-trips through the schema.
    from oikonomia.schemas.document import Document

    doc = Document.model_validate_json(row["document_json"])
    assert doc.tm_id == 100042


def test_build_corpus_report_and_freshness(mini_corpus_settings: Settings) -> None:
    s = mini_corpus_settings
    manifest = run_stage(BuildCorpusStage(), s)
    assert manifest.stats["n_parsed"] == 1
    assert manifest.stats["hgv_join_rate"] == 1.0

    report = json.loads((s.paths.processed / "ingest_failures.json").read_text(encoding="utf-8"))
    assert report["n_failed"] == 0
    assert report["parse_rate"] == 1.0

    # Manifest records the pinned corpus rev as the inputs key.
    assert manifest.inputs_key == "idp@testrev"
