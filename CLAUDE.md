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

# Phase 2
uv run oik corpus stats                     # recompute the §7 ledger (~7s)
uv run oik lexicon mine --min-docs 2 --top 200000 > out.csv   # candidate vocab
uv run oik lexicon verify                   # every form corpus-attested? (~26s)
uv run oik lexicon eval                     # lexicon attachment rate (~45s)
uv run oik lexicon baseline                 # proximity baseline (~40s)

# Phase 3
uv run oik splits build                     # dedup + assign (~25s)
uv run oik splits report                    # sizes, drift, duplicate clusters
uv run oik splits check                     # re-verify the artifact on disk

# Quality gate — run after ANY unit of work, in this order
.venv/bin/ruff check src tests
.venv/bin/python -m mypy src
.venv/bin/python -m pytest
make clean                        # always clear caches afterwards
# During iteration, skip the whole-corpus scan: pytest -m "not corpus"
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

### ✅ Phase 2 — Characterization & schema design (done)

**Done so far**
- **Corpus revision pinned:** `ingest.idp_git_rev =
  d7a34f302d1e44e271256092c2b780733187b478` (papyri/idp.data HEAD, 2026-07-20)
  in `configs/base.yaml`. Every artifact now records this sha.
- **`sync.py` made efficient:** clone uses `--filter=blob:none` (blobless partial
  clone), fetching only the blobs the pinned rev needs instead of every blob in
  the repo's multi-GB history.
- **Corpus downloaded (partially checked out)** — see §9 for exact state.

**Delivered (all five planned items)**
1. **Full-corpus build at parse rate 1.000.** All 67,980 DDbDP docs, 0 failures
   (~85s). `oik corpus stats` recomputes the §7 ledger over the whole table in
   ~7s, streaming record batches. See §7 for the numbers this corrected.
2. **Lexicons mined, not recalled** — `resources/lexicon/{currency,measures,
   commodities,tax_terms,fractions,date_terms}.yaml`, 55+ entries. `oik lexicon
   mine` harvests tokens adjacent to every `<num>` (clipped to the numeral's own
   line) and ranks by document frequency; the generator hard-fails on any form
   absent from that evidence.
3. **Lexicon code**: `labeling/normalize.py` (folding + exact per-character
   origin map), `lexicon.py`, `matcher.py` (leftmost-longest, token-boundary
   anchored, spans returned in *original* offsets), `mine.py`, `evaluate.py`.
4. **`resources/schema/annotation_guidelines.md`** — entity/relation contract,
   grounded in real corpus text, with the recurring hard cases in §5.
5. **`weak_rules.py` proximity baseline**, written before any model exists.

**Measured results (the bar Phases 7–8 must beat)**
- Lexicon attachment: **62.35%** of 528,085 numerals get a lexicon term
  (`oik lexicon eval`). By genre it tracks document type: register ~80%,
  account ~68%, list ~67%, vs petition ~35%, contract ~35% — where numerals
  are ages and regnal years, not economic quantities.
- Baseline (`oik lexicon baseline`): **74.50% numeral link rate**, 16.95% of
  numerals suppressed as dates.
- **`oik lexicon verify`: 336/336 forms attested, 0 unattested.** This is the
  standing guard on "measured, never recalled" — an invented form matches
  nothing and raises no error, so nothing else would catch it. Also a test
  (`-m corpus`, skipped when the corpus is absent).

**Resolved judgment call:** match on the **edited** view. Measured basis:
`<expan>` covers 68.8% of documents and `<supplied>` 62.4%, so the diplomatic
view would strip a majority of currency terms and lose restored amounts
outright. Reversible via the `OffsetMap`.

**Deliberately dropped:** `form_expansions.yaml` (planned in the original
Phase 2 step 2) was **not** built, and should not be. It existed to map
abbreviated forms to their expansions — which is precisely what the `edited`
view already does via `<expan><ex>`, and matching on the edited view is now the
resolved decision. The residue is handled by the `abbrev_forms` lists in each
lexicon file, and those account for only **1.15%** of all matches. Revisit only
if diplomatic-view matching is ever adopted.

**Defects found and fixed** (each by checking real usage, not by reasoning
about the words — the context check is `oik lexicon mine` plus reading lines):
- `τιμή` was filed under `TAX_TERM`; `ἡ τιμὴ τοῦ βασιλικοῦ σίτου` is a sale
  price. Now its own `PRICE_TERM`. Cut spurious `CHARGED_UNDER` by 30%
  (9,403 → 6,603).
- `φορά` was a `TAX_TERM`; `ὀνικαὶ φοραὶ β` is "two donkey-loads". Now a
  `UNIT`. `φόρος` (rent/tribute) stays a tax. `φυλακιτικόν` (guard tax) added.
- Adjectival metal dropped from `CURRENCY`: `χαλκοῦν`/`χαλκᾶ`/`χαλκαῖ` describe
  bronze *objects* (`λυχνίαι χαλκαῖ β` = two bronze lampstands), and `χρυσᾶ` is
  also the personal name **Χρυσᾶ**. Monetary `χαλκοῖ` kept.
- `μύρια`/`μυρι` dropped from `myriad`: bare number words, not the multiplier.
- **`occupations.yaml` added** (13 entries, mined + context-checked). Covers the
  stem-sharing false friends: `χαλκεύς`, `σιτολόγος`, `ἐλαιουργός`, `κεραμεύς`.
  Excludes `γεωργίου`/`γεώργιος` — folded, those are the *name* Georgios, not
  the trade `γεωργός`.

Net: 88 entries / 336 forms across 8 categories. Attachment and link rate both
rose slightly; precision rose considerably more than the rates show.

**Still open before Phase 5:**
- No `PERSON` / `PERSON_ROLE` / `PLACE` lexicons. Personal names are the hard
  case: folding erases the capital distinguishing `Γεώργιος` from `γεωργός`.
- `verify` guards *attestation*, not *sense* — it proves a form occurs, not
  that it is filed under the right category. Only gold annotation settles that.

### ✅ Phase 3 — Splits (done)

**Why it got its own phase:** splits are small in code and irreversible in
practice. Once models are trained and numbers published nobody re-does them, so
the only defence against a quietly wrong split is being able to rebuild and
inspect it. `build_splits` is a versioned stage like everything else.

**Deliverables**
- `splits/dedup.py` — MinHash + LSH near-duplicate clustering over character
  5-gram shingles of the *folded* text. 128 permutations, 16 bands, Jaccard
  threshold 0.8, seeded and deterministic.
- `splits/assign.py` — group-aware stratified assignment (`random`) and
  temporal holdout (`chronological`), plus `report_split` which verifies no
  group straddles a split.
- `splits/build.py` — the stage → `processed/splits.parquet` + report.
- CLI `oik splits {build,report,check}`. 26 tests.

**Results over the 61,249 documents with real text**
- **399 duplicate clusters covering 1,553 docs (2.54%)**; largest cluster 454
  documents. These would have leaked across a naive random split.
- 59,720 atomic groups. Grouping unions two signals: shared TM id and
  near-duplicate cluster.
- `random`: 49,004 / 6,145 / 6,100. Max stratum drift **0.0078**, stratum TV
  distance 0.0023 — i.e. every stratum is split ~80/10/10, not just the corpus.
- `chronological`: train −350→466 CE, dev 466→625, test 600→1050. Residual
  temporal overlap **0.07%** (35 docs), reported rather than hidden.

**Two decisions worth keeping**
- **Publication volume is NOT a grouping signal.** It is right in spirit
  (fragments of a roll share a volume) but the largest volume holds 2,023
  documents; grouping there would force whole volumes into one split and make
  stratification impossible. Group on evidence of textual identity instead.
- **Undated documents go to train in the chronological regime.** They cannot
  support a claim about temporal generalisation, and putting them in test would
  dilute the exact measurement the regime exists to make.

**Bug worth remembering:** the first implementation balanced splits against a
*global* deficit. Train's deficit is largest until it is nearly full, so whole
strata landed in train and only the strata processed last were divided —
`receipt|high_roman` came out 33/33/33 and every `nogenre|*` stratum went 100%
to train. **The corpus-level 80/10/10 was exact throughout**, which is what
made it invisible. Only a per-stratum assertion catches it; there is now a test
that fails on the old algorithm and passes on the new one.

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
- `DDbDP` 67,980 files · `HGV_meta_EpiDoc` 66,872 · `Translations` 8,001.
- **Translations are multilingual, and smaller than recorded** (corrected in
  Phase 2 against all 8,001 files; the old "6,474 unique DDbDP docs = 9.8%,
  English" was wrong). Actual: 7,116 `en` · 576 `de` · 190 `fr` · 89 `it` ·
  small tails (`es`, `ar`, `el`, `pl`, `bg`) · 14 with no translation div.
  English covers **6,156 unique docs, of which 5,989 join a DDbDP document =
  8.81%**. Document-level only. Note stray malformed lang codes (`ge`, `fe`).
- **Path conventions (asymmetric — verified empirically):**
  - DDbDP `DDbDP/{id//1000}/{stem}.xml`
  - HGV `HGV_meta_EpiDoc/HGV{id//1000+1}/{stem}.xml`  ← **+1 and "HGV" prefix**
  - Translations `Translations/{id//1000}/{id}-{seq}.xml`
  - Letter-suffixed stems exist (`13a`); bucket by numeric part.
- DDbDP↔HGV join **98.27%** by TM id (whole corpus; the 98.3% sample estimate
  held).
- **Duplicate `xml:id` is endemic and must not be fatal.** 512 of 67,980 DDbDP
  files (0.75%) carry repeated ids (`_ctr`, `column_i`, `_FrA`, `_1`…) from
  editors merging fragments. lxml collects ids and enforces uniqueness by
  default, which rejected all 512. Parse with `collect_ids=False`
  (`ingest/xml_parser.py`, the single parser factory) — nothing resolves
  IDREFs, so the id table is unused. **With this, parse rate is 1.000.**
- HGV dates at `msDesc/history/origin/origDate` (`when=` or `notBefore/notAfter`,
  ISO, BCE = leading `-`). Whole-corpus: **98.63%** machine-readable, **23.68%**
  exact-day, **17.18%** span >120y, **3.71%** alternative datings
  (`xml:id="dateAlternativeN"` — the 2.5% sample estimate was low).
- HGV linkable places in `<provenance type="located">//placeName/@ref`
  (space-separated TM+Pleiades URIs), **77.59%** (Pleiades specifically 75.0%).
  `<origPlace>` is free German text — **never used for joins**.
- **DDbDP markup, whole corpus** (`oik corpus stats`; supersedes the 200-doc
  sample estimates, which ran high on `gap`/`supplied`/`unclear`):
  numerals 64.82% · `<expan>` 68.81% · `<unclear>` 68.18% · `<gap>` 66.16% ·
  `<supplied>` 62.39% · `<choice><reg>` 44.53% · `<abbr>` 15.58% ·
  `<surplus>` 3.45% · `<choice><corr>` 0.20%.
  Numerals are **not** a `MarkupKind` — they live in their own table. Derive
  any kind list from the `MarkupKind` enum, never by hand: a wrong name reports
  0.0, which is indistinguishable from "absent from the corpus".
- Corpus text mass: 37.4M edited chars, 934,923 lines, 568,449 numerals,
  median 233 chars/doc.
- **`n_chars_edited` counts whitespace, so it is not "how much text there is".**
  6,731 docs (**9.90%**, flagged `empty_edited_text`) hold only the newline
  scaffolding left by `<lb>` elements — `n_chars_edited` 4–77, but
  `.strip()` is empty. Filter on `parse_flags` or `.strip()`, never on
  `n_chars_edited > 0`, which is true for every document in the corpus.
- **Usable subset for supervision: 61,249 docs with real text, of which 44,064
  also carry at least one numeral.** These are the denominators Phase 3 should
  sample and split against — not 67,980.
- **Zero entity markup** (`persName`/`placeName`/`measure`/`rs`/`w` = 0% of 200).
  All entity supervision must be built. This makes Phase 5 gold the critical path
  and Phase 8 relations the scientific risk.
- Economic docs are numeral-dense (whole corpus, numerals/line): account 1.34 ·
  list 1.14 · receipt 0.67 · lease 0.65 · loan 0.32 · sale 0.25 · contract 0.21
  · petition 0.15 · **letter_private 0.09**. The genre signal is real and large.
- **Word order: units PRECEDE their numeral.** Measured over every `<num>`
  neighbour: `δραχμαι` sits left of the numeral in 81.5% of occurrences,
  `αρταβαι` in 80.4%. Greek accounts read *commodity, unit, number*
  (`πυροῦ ἀρτάβαι ιβ`). Any proximity rule must break ties leftward.
- **Many alphabetic numerals are never tagged `<num>`.** `ιβ`, `ιϛ`, `κδ`, `λβ`
  and friends are among the most frequent tokens adjacent to tagged numerals —
  i.e. editors tagged one and left the next bare. Do not treat `<num>` as a
  complete inventory of numbers; annotation guidelines say to read the number,
  not the tag.
- **Near-duplication is real but modest: 2.54%** (1,553 of 61,249 texted docs
  in 399 clusters, MinHash Jaccard >=0.8 over folded 5-grams). Largest cluster
  454 documents. Enough to inflate a naive random split; not enough to distort
  corpus statistics.
- **1,706 documents share a TM id with another** — the same papyrus edited or
  republished separately. A real leakage group, and cheap to detect.
- Publication volume is far too coarse to group on: 1,025 volumes, largest
  holding 2,023 documents.
- Lexicon false friends share stems across categories: `χαλκεύς` (coppersmith)
  vs currency `χαλκοῦς`; `σιτολόγος` (grain officer) vs commodity `σῖτος`;
  `ἐλαιουργός` (oil-worker) vs `ἔλαιον`. These are OCCUPATION. Stem matching
  alone will mislabel them.

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

**~28% of the full project.** Phases 0, 1, 2 and 3 complete: foundation, a
validated corpus-ingestion pipeline built over all 67,980 documents at parse
rate 1.000, whole-corpus characterization, mined lexicons with measured recall,
the annotation schema, a proximity baseline at a 74.50% numeral link rate, and
leak-free stratified + chronological splits.

Remaining: Phase 4 DAPT (Modal) · Phase 5 gold annotation ·
Phase 6 weak/silver labeling · Phase 7 entity model · Phase 8 relation model ·
Phase 9 corpus inference → DB · Phase 10 historical analysis · Phase 11 release.

**Phase 5 (gold annotation) is the critical path** — there is zero upstream
entity markup, so all supervision must be created by hand. Phase 8 (relations)
remains the scientific risk.

---

## 9. Current machine state (read this first in a new session)

_Last updated: 2026-07-20 (end of Phase 3)._

### Quality gate at last save
**ruff PASS · mypy PASS · 130 tests PASS.** Caches cleared. All work is
committed to git (`main`).

### Corpus on disk — COMPLETE
`data/raw/idp.data` — **6.1 GB**, working tree clean, HEAD at the pinned rev
`d7a34f30…`. All directories present and count-verified:
`DDbDP` **67,980** · `HGV_meta_EpiDoc` **66,872** · `Translations` **8,001**,
plus `RDF`, `Validation`, `APD`, `APIS`, `Biblio`, `DCLP`, `HGV_metadata`,
`Historical`.

**How the earlier interrupted checkout was repaired** (keep this — it is not
obvious): the interrupted run had left the *index wiped* while the files it had
already written stayed on disk as untracked, so `git checkout <rev>` aborted
with "untracked working tree files would be overwritten" on every retry.
`git reset --mixed <rev>` (rebuild the index, leave the tree alone) followed by
`git checkout -- .` (materialise only what is missing) fixed it without
re-downloading. `sync.py` now does exactly this, so it is genuinely idempotent
and self-healing.

### Derived artifacts present (all gitignored, all re-derivable)
- `data/processed/corpus.parquet` — **280 MB**, 67,980 rows, built at
  `build_corpus` stage version **2**.
- `data/processed/ingest_failures.json` — now an empty failure list.
- `data/.manifests/build_corpus.json`.
- `data/interim/numeral_context*.csv` — mined candidate vocabulary
  (17,540 tokens at `--min-docs 2`). Regenerate with `oik lexicon mine`.
- `data/processed/splits.parquet` + `splits_report.json` — `build_splits`
  stage version **3**. 61,249 rows, both regimes in one table
  (`split_random`, `split_chronological`).

Disk: watch headroom — corpus 6.1 GB + processed 280 MB.

### Notes for the next session
- The lexicon build used a one-off curation script that lived in the scratchpad
  and is **gone**. The reviewed artifacts are `resources/lexicon/*.yaml`; to
  extend them, re-mine and edit the YAML directly.
- `oik corpus stats` is the self-check: if its numbers drift from §7, something
  changed in the corpus or the parser.

---

## 10. Resume checklist (next session, in order)

```bash
cd /Users/abdoumagico/Development/ACHATES

# 1. Confirm the tree is green before changing anything
.venv/bin/ruff check src tests && .venv/bin/python -m mypy src && .venv/bin/python -m pytest

# 2. Confirm the derived artifacts still exist and still agree with §7.
#    Rebuild if missing: `oik ingest build` (~85s), `oik splits build` (~25s).
.venv/bin/oik corpus stats | head -30
.venv/bin/oik splits check
```

Then start **Phase 4 — DAPT on Modal**. Order of business:

1. **Re-verify every Modal API fact in §7 against `modal.com/docs` first.**
   Those were checked during planning, Modal moves, and the standing rule is
   never to write Modal syntax from memory. This is the first thing to do, not
   a detail to confirm later.
2. Install the extras that were deliberately deferred: `uv pip install -e
   ".[modal,train]"`. The core library must stay importable without them —
   `modal_app/` imports the library, never the reverse.
3. Feed the GPU from the **train split only** (`split_random == "train"`, or
   the chronological train set for the temporal arm). Domain-adaptive
   pretraining on dev or test would contaminate every later evaluation, and
   with 2.54% near-duplication already clustered, the split is the only thing
   standing between DAPT and leakage.
4. Preprocess offline into packed, tokenised, memory-mapped shards — the A10G
   (24 GB) should never wait on CPU tokenisation. Prefer bf16 and packed
   sequences.
5. The 4-arm ablation is in §7: A0 GreTa · A1 GreTa+papyri-DAPT (primary,
   apache-2.0) · A2 koineformer+papyri-DAPT (SA) · A3 koine-t5-omni (NC,
   comparison only). **Licence firewall: nothing releasable may descend from
   an NC ancestor.**
6. Checkpoint into a Modal Volume and use `retries=` +
   `single_use_containers=True` + resume-from-checkpoint; A10G capacity is
   preemptible.

**Reminder:** commit after each green unit of work, and update §6/§8/§9 of this
file before ending a session.
