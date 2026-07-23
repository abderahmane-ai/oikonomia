# Phase 1 — Corpus Ingestion

### ✅ Phase 1 — Corpus ingestion (done)
**Deliverables**
- `ingest/paths.py` — the single source of truth for the three (asymmetric)
  idp.data path conventions.
- `ingest/epidoc_text.py` — the load-bearing dual-view EpiDoc parser: edited +
  diplomatic text, bidirectional `OffsetMap`, markup spans, numerals, lines.
- `ingest/hgv_dates.py`, `hgv_places.py`, `hgv_genre.py`, `hgv_meta.py` — HGV
  metadata (interval dates with alternatives, TM/Pleiades place links, genre
  folksonomy → canonical taxonomy).
- `ingest/translations.py` — document-level English translations.
- `ingest/sync.py` — pinned-rev corpus checkout (refuses unpinned).
- `ingest/build_corpus.py` — `BuildCorpusStage`: join → `processed/corpus.parquet`
  (+ failure/coverage report), with lossless `document_json` columns.
- `resources/genre_map.yaml` — seed mapping of frequent HGV terms.
- CLI `oik ingest {sync,build,report}`.
- 49 tests (offset invariants, path conventions, dates, places, genre, numerals,
  config layering, pipeline freshness, end-to-end build). Ruff + mypy clean.

**Validated at scale:** the parser was stress-tested against **120 random real
papyri** drawn from 18 buckets of the live corpus (4,640 files listed):
**120/120 parsed (parse rate 1.000)**, **0 offset-map invariant failures**,
8.96 numerals/doc. 8/120 (6.7%) have empty edition text — real metadata-only or
fully-lost stubs, correctly flagged `empty_edited_text` (kept in the table;
downstream stages filter). This exceeds the ≥98% parse-rate exit target and
confirms the aligned-segment correctness property on real, deeply-nested markup —
not just on the committed fixture.

**Not done here (deferred by design):** full 415-term genre curation (Phase 2),
lexicons (Phase 2), the actual full-corpus sync + build run (needs a pinned rev
and a local 2.8 GB checkout).
