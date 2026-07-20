# CLAUDE.md — OIKONOMIA

Agent instructions and living project record. **Update this file at the end of
every phase.**

---

## 1. What this project is

**OIKONOMIA** turns the ~68,000 ancient Greek documentary papyri of Greco-Roman
Egypt (tax receipts, leases, loans, wage payments, census returns, private
letters) into a structured, auditable database of everyday economic life, and
trains open Greek models to read them.

It is the first attempt to automate the information extraction that economic
historians currently do by hand. The deliverables are three:

1. **Open models** — a papyri-adapted Greek model family (entity + relation
   extraction), released on Hugging Face.
2. **A derived database** — every extracted transaction traceable to a character
   span in a specific document at a specific corpus revision.
3. **Historical findings** — price/wage series across a millennium, women as
   contract principals, ancient credit — things the database makes visible for
   the first time.

**Corpus:** Duke Databank of Documentary Papyri (DDbDP) + HGV metadata, via
[`papyri/idp.data`](https://github.com/papyri/idp.data), **CC BY 3.0**.

**Venue target:** ML4AL / LT4HALA (ACL ancient-languages workshops) or DSH
journal. No fixed deadline — build it properly.

---

## 2. Working rules (non-negotiable)

These are standing instructions for any agent working in this repo.

- **Never guess. Validate before implementing.** Every load-bearing fact (path
  conventions, XML structure, API syntax, licences) must be checked against the
  live source, not recalled. The §7 fact ledger records what was verified and
  how. Modal syntax in particular is **always** re-checked against
  `modal.com/docs` — never written from memory.
- **Tests are progressive and extensive.** Every module ships with tests in the
  same change. Hand-crafted fixtures with hand-computed expected output are
  preferred over smoke tests for anything with subtle semantics (the EpiDoc
  parser especially).
- **Always run ruff, mypy and pytest before considering work done.**
- **Always clean the caches afterwards — every time, not just at phase
  boundaries.** `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache` and
  stray `*.pyc` must never be left behind or committed. One command: `make clean`
  (or the explicit form in §5). The quality gate is: ruff → mypy → pytest →
  clean.
- **Phase discipline.** Before starting the next phase, write a clean summary of
  the finished phase into §6: what was done, deliverables, % progress, what's
  next. Do not silently roll forward.
- **"Save state" means update THIS FILE.** Every pause starts a *new session*,
  and `CLAUDE.md` is the only thing loaded into the next session's context.
  Never park a handoff in a plan file or scratchpad. A state save must record:
  phase log, progress %, machine state the next session cannot re-derive
  (partial downloads, pinned revs, uncommitted edits), and an ordered resume
  checklist (§9).
- **Commit working state.** The repo is under git; commit whenever a phase or a
  coherent unit of work is green (ruff + mypy + pytest), so nothing is ever lost
  to an interrupted session.
- **Efficiency / hardware:** training runs on **Modal, single A10G (24 GB)**.
  Maximise GPU utilisation, minimise CPU work in the training loop (do heavy
  preprocessing offline into the processed corpus; feed the GPU tokenised,
  memory-mapped data; prefer bf16, sensible batch sizes, and packed sequences).
  The pure-Python library must stay importable and testable on a laptop with no
  GPU/Modal dependency.
- **Data separation is structural** (see §3). Raw data is immutable and
  gitignored; only `data/gold/` and `data/.manifests/` are tracked.
- **Licence firewall.** Never build a *releasable* artifact on a NonCommercial
  ancestor (`koine-t5`, `koine-t5-omni` are CC-BY-NC-SA). See `MODEL_LICENSES.md`.

---

## 3. Architecture (boundaries that must hold)

Four hard boundaries, enforced by directory layout and import direction:

1. `src/oikonomia/` — pure-Python library. **No Modal imports, no GPU deps.**
2. `modal_app/` — thin Modal orchestration (Phase 4+). Imports the library,
   never the reverse. Deleting it must not break the library.
3. `data/` — tiered by mutability: `raw/` (immutable, gitignored) → `interim/`,
   `processed/` (gitignored, re-derivable) → `gold/`, `.manifests/` (tracked).
4. `resources/` — curated knowledge (lexicons, genre map, prompts), reviewed as
   source code because model behaviour depends on it.

Config is layered YAML (`configs/base.yaml` → `paths.<env>.yaml` → dotted
overrides → `OIK_*` env). No module constructs a data-path literal; all paths
come from `settings.paths.*`, so the same code runs locally and on Modal.

The pipeline is a set of **deterministic, resumable stages** (`pipeline/`). Each
stage writes a manifest (`data/.manifests/<stage>.json`) recording its input
fingerprint (the pinned corpus git rev, not 68k file hashes), a params hash, and
output sha256s. Freshness = `version + inputs_key + params`; a stage is skipped
when that key is unchanged and its outputs are intact. **Bump a stage's
`version` when you change its logic** (or just run with `--force` while
iterating). Outputs are written temp-then-rename; the manifest is written last.

Full detail: [`docs/architecture.md`](docs/architecture.md).

---

## 4. Commands

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"        # library + dev tools (no GPU stack)

# Phase 1 pipeline
uv run oik ingest sync  --set ingest.idp_git_rev=<sha>   # clone/checkout corpus
uv run oik ingest build                                   # → processed/corpus.parquet
uv run oik ingest report                                  # coverage + failures

# Quality gate — run after ANY unit of work, in this order
.venv/bin/ruff check src tests
.venv/bin/python -m mypy src
.venv/bin/python -m pytest
make clean                        # always clear caches afterwards
```

Modal extras (`.[modal]`, `.[train]`) are installed only when Phase 4 begins.

---

## 5. Pre-phase-transition checklist

Run every time before declaring a phase done and moving on:

1. `.venv/bin/ruff check src tests` — must pass with **All checks passed!**
2. `.venv/bin/python -m mypy src` — must be **Success: no issues found**.
3. `.venv/bin/python -m pytest` — all tests green.
4. Clear caches — `make clean`, or explicitly:
   ```sh
   find . -path ./.venv -prune -o -type d \
     \( -name "__pycache__" -o -name ".pytest_cache" \
        -o -name ".ruff_cache" -o -name ".mypy_cache" \) -exec rm -rf {} + 2>/dev/null || true
   find . -path ./.venv -prune -o -name "*.pyc" -exec rm -f {} + 2>/dev/null || true
   ```
   **Do not use `-delete` here.** `find -delete` implies `-depth`, which
   silently disables `-prune` — the command then walks into `.venv` and deletes
   its bytecode too. Use `-exec rm` as above.
5. Update §6 (phase log), §8 (progress %) and §9 (machine state) of this file.

---

## 6. Phase log

Overall plan (12 phases): Phase 0 Foundation · **Phase 1 Ingestion** · Phase 2
Characterization & schema · Phase 3 Splits · Phase 4 DAPT (Modal) · Phase 5 Gold
annotation · Phase 6 Weak/silver labeling · Phase 7 Entity model · Phase 8
Relation model · Phase 9 Corpus inference → DB · Phase 10 Historical analysis ·
Phase 11 Release.

### ✅ Phase 0 — Foundation (done, folded into Phase 1 delivery)
- src-layout package, layered config, deterministic pipeline runner, logging,
  hashing, typed schemas, tooling (ruff/mypy/pytest), top-level docs
  (README, DATA_ATTRIBUTION, MODEL_LICENSES).

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

### 🔶 Phase 2 — Characterization & schema design (IN PROGRESS)

**Done so far**
- **Corpus revision pinned:** `ingest.idp_git_rev =
  d7a34f302d1e44e271256092c2b780733187b478` (papyri/idp.data HEAD, 2026-07-20)
  in `configs/base.yaml`. Every artifact now records this sha.
- **`sync.py` made efficient:** clone uses `--filter=blob:none` (blobless partial
  clone), fetching only the blobs the pinned rev needs instead of every blob in
  the repo's multi-GB history.
- **Corpus downloaded (partially checked out)** — see §9 for exact state.

**Remaining**
1. Finish the corpus checkout, then run the full `oik ingest build` over all
   67,980 docs; reproduce §7 numbers as a pipeline self-check. Ship as an
   `oik corpus stats` command (testable/reproducible) rather than a notebook.
2. Build lexicons (`resources/lexicon/`): currency, measures, commodities +
   hand-audited `form_expansions.yaml`.
   **Method:** mine the *local* corpus for words adjacent to `<num>` tags and
   build the lexicon from measured frequencies — **never hand-write Greek forms
   from memory**. Then measure recall before committing to it.
3. Lexicon code: `labeling/normalize.py` (diacritic/sigma folding returning text
   *plus* an `OffsetMap`), `lexicon.py`, `matcher.py` (longest-match, offsets in
   original space) + tests.
4. Draft `resources/schema/annotation_guidelines.md` (broad schema: COMMODITY,
   QUANTITY, UNIT, MONEY_AMOUNT, CURRENCY, PERSON, PERSON_ROLE, OCCUPATION, PLACE,
   DATE_REF, TAX_TERM; relations HAS_QUANTITY/HAS_UNIT/HAS_PRICE/PARTY_OF/…).
5. Implement the `weak_rules.py` proximity baseline **before any model exists** so
   it is an honest bar to beat.

**Open judgment call (non-blocking):** match the lexicon on the **edited** view
(abbreviations resolved — better currency recall, `<expan>` covers 65% of docs)
vs the diplomatic view. Current lean: edited. The dual-view `OffsetMap` makes
this reversible.

---

## 7. Verified fact ledger

Facts checked against live sources during planning/implementation. Do not
re-derive; if reality contradicts one, treat it as a finding and update here.

### Corpus (github.com/papyri/idp.data)
- **Pinned revision: `d7a34f302d1e44e271256092c2b780733187b478`** (HEAD on
  2026-07-20). Set in `configs/base.yaml`. Repin deliberately, never incidentally.
- Licence **CC BY 3.0** (in every file; no repo `LICENSE`). README is stale
  (documents `DDB_EpiDoc_XML`/`HGV_trans_EpiDoc`; real dirs are `DDbDP` /
  `Translations`).
- `DDbDP` 67,980 files · `HGV_meta_EpiDoc` 66,872 · `Translations` 8,001
  (6,474 unique DDbDP docs = 9.8%, English, document-level only).
- **Path conventions (asymmetric — verified empirically):**
  - DDbDP `DDbDP/{id//1000}/{stem}.xml`
  - HGV `HGV_meta_EpiDoc/HGV{id//1000+1}/{stem}.xml`  ← **+1 and "HGV" prefix**
  - Translations `Translations/{id//1000}/{id}-{seq}.xml`
  - Letter-suffixed stems exist (`13a`); bucket by numeric part.
- DDbDP↔HGV join 98.3% by TM id.
- HGV dates at `msDesc/history/origin/origDate` (`when=` or `notBefore/notAfter`,
  ISO, BCE = leading `-`), 98.5% machine-readable, ~22% exact-day, ~17% span
  >120y, 2.5% alternative datings (`xml:id="dateAlternativeN"`).
- HGV linkable places in `<provenance type="located">//placeName/@ref`
  (space-separated TM+Pleiades URIs), 77.8%. `<origPlace>` is free German text —
  **never used for joins**.
- DDbDP markup present: `<num value=>` 67%, `<expan>` 65%, `<supplied>` 70%,
  `<unclear>` 72%, `<gap>` 77%, `<choice>/<reg>/<orig>` 47%.
- **Zero entity markup** (`persName`/`placeName`/`measure`/`rs`/`w` = 0% of 200).
  All entity supervision must be built. This makes Phase 5 gold the critical path
  and Phase 8 relations the scientific risk.
- Economic docs are numeral-dense: tax 0.97/line, accounts 0.86, receipts 0.61,
  vs private letters 0.07.

### EpiDoc rendering (confirmed vs EpiDoc Guidelines)
- `<choice>`: edited uses `<reg>`/`<corr>`; diplomatic uses `<orig>`/`<sic>`.
- `<expan>`: `<ex>` (expansion) is edited-only; abbr letters are in both.
- `<supplied>` (lost/omitted): edited-only. `<surplus>`: diplomatic-only.
- `<app>`: render `<lem>` (chosen reading); ignore `<rdg>`.
- papyri.info blocks bots (Anubis) — rendered-text cross-checks are done with
  hand-crafted fixtures, not by scraping.

### Backbones (all are LoRA adapters over `bowphs/GreTa`, T5, apache-2.0)
- `koineformer` r=16, span-corruption DAPT, 512-token, **CC-BY-SA-4.0** — *not*
  an encoder-only model (`task_type: SEQ_2_SEQ_LM`).
- `koine-t5` / `koine-t5-omni` multitask, 256-token, **CC-BY-NC-SA-4.0** (NC).
- GreTa tokenizer **case-folds** (no capitals) — irrelevant to token
  classification, fatal to generative proper-name output.
- Plan: 4-arm ablation A0 GreTa · A1 GreTa+papyri-DAPT (**primary, apache-2.0**) ·
  A2 koineformer+papyri-DAPT (SA) · A3 koine-t5-omni (**NC, comparison only**).

### Modal API (verified at modal.com/docs — re-check before Phase 4)
- `modal.App` (`modal.Stub` is an error in ≥1.0). GPU string `gpu="A10"`
  (`"A10G"` also resolves), 24 GB, $1.10/hr, `"A10:2"` for multi.
- `modal.gpu.*` objects, `modal.Mount`/`mount=`, automounting of local modules:
  **all deprecated/removed** — add local source explicitly
  (`add_local_python_source`, `add_local_dir`).
- Volumes `from_name(create_if_missing=True)`, `volumes={...}`, `.commit()`,
  background commits; set Trainer `output_dir` inside the Volume.
- `@app.function(gpu=, volumes=, secrets=, timeout=, retries=, max_containers=,
  single_use_containers=)`; timeout max 86400; `concurrency_limit`→`max_containers`.
- Preemption-resilient pattern: Volume checkpoints + `retries=` +
  `single_use_containers=True` + resume-from-last-checkpoint.

---

## 8. Progress

**~12% of the full project.** Phase 0 + Phase 1 complete (foundation + a
validated, tested corpus-ingestion pipeline); Phase 2 started (corpus pinned and
downloaded). Remaining: finish the full ingest run, then Phases 2–11 (schema,
splits, DAPT, gold annotation, weak labeling, entity + relation models, corpus
inference, analysis, release).

---

## 9. Current machine state (read this first in a new session)

_Last updated: 2026-07-20._

### Quality gate at last save
**ruff PASS · mypy PASS · 49 tests PASS.** Caches cleared. All work is committed
to git (`main`).

### Corpus on disk — checkout is INCOMPLETE
`data/raw/idp.data` — **5.7 GB**, HEAD correctly at the pinned rev. The blobless
clone succeeded but the **checkout was interrupted partway** (it stopped
alphabetically after `Historical`).

| Directory | State |
|---|---|
| `DDbDP` | ✅ **67,980** xml — exactly the expected count |
| `HGV_meta_EpiDoc` | ✅ **66,872** xml — exactly the expected count |
| `APD`, `APIS`, `Biblio`, `DCLP`, `HGV_metadata`, `Historical` | present |
| `RDF`, `Translations`, `Validation` | ❌ **missing — not yet checked out** |

**Impact: low.** Everything Phase 2 needs is present and count-verified. Only
`Translations` (English, 9.8% coverage, a Phase 6 nice-to-have) is missing.
`oik ingest sync` is idempotent and will fill in just the gaps.

### Not yet done
- The **full `oik ingest build` has never been run** — the parser has only ever
  seen a 120-document sample (100% parse, 0 invariant failures). Running it over
  all 67,980 docs is the next milestone and will surface a real failure tail.
- Disk: ~32 GB free. The corpus is 5.7 GB; watch headroom.

---

## 10. Resume checklist (next session, in order)

```bash
cd /Users/abdoumagico/Development/ACHATES

# 1. Confirm the tree is green before changing anything
.venv/bin/ruff check src tests && .venv/bin/python -m mypy src && .venv/bin/python -m pytest

# 2. Finish the interrupted corpus checkout (idempotent, a few minutes)
.venv/bin/oik ingest sync

# 3. THE MILESTONE: build the corpus table over all 67,980 documents
.venv/bin/oik ingest build
.venv/bin/oik ingest report      # expect parse rate ≥0.98, HGV join ≈0.983
```

Then continue Phase 2 at §6 step 2 (mine the local corpus for vocabulary near
`<num>` tags → build lexicons → measure recall), step 3 (matcher code), step 4
(annotation guidelines), step 5 (proximity baseline).

**Reminder:** commit after each green unit of work, and update §6/§8/§9 of this
file before ending a session.
