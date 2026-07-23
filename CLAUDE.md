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
fingerprint, a params hash, and output sha256s. Freshness =
`version + inputs_key + params`; a stage is skipped when that key is unchanged
and its outputs are intact.

**`inputs_key` must name what the stage actually reads.** Stages that read the
raw corpus fingerprint it with the pinned git rev (cheap and exact — not 68k
file hashes). Stages that read *another stage's output* must use
`pipeline.manifest.upstream_key(...)`, which hashes the upstream manifest's
output sha256s. Keying a downstream stage on the corpus rev is a silent
staleness bug: when the EpiDoc parser was fixed, `build_corpus` rewrote
`corpus.parquet` from unchanged raw files and `build_splits` reported
"skipped (fresh)" over text that no longer existed. **Bump a stage's
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
uv run oik lexicon mine --min-docs 2 --top 200000 > out.csv   # units/currency
uv run oik lexicon mine-titles > titles.csv  # occupations (after a NAME)

# Phase 5
uv run oik gold sample --n 150 --iaa 30 --blind 30   # -> data/gold/
uv run oik gold check                       # every span selects its own text?
uv run oik gold check --fix                 # repair offsets from the text field
uv run oik lexicon verify                   # every form corpus-attested? (~26s)
uv run oik lexicon eval                     # lexicon attachment rate (~45s)
uv run oik lexicon baseline                 # proximity baseline (~40s)

# Phase 3
uv run oik splits build                     # dedup + assign (~25s)
uv run oik splits report                    # sizes, drift, duplicate clusters
uv run oik splits check                     # re-verify the artifact on disk

# Phase 4 (needs the train extra for the tokenizer)
uv run oik dapt prepare                     # pack train/dev shards (~20s)
uv run oik dapt inspect                     # shard contents + derived schedule
modal run modal_app/dapt.py::push           # upload shards to the Volume
modal run modal_app/dapt.py::launch         # DAPT on an A10

# Phase 6 (silver labeling)
uv run oik silver score                     # score the silver labeler vs gold (per label)
uv run oik silver score --labeler baseline  # the Phase-2 proximity bar
uv run oik silver distmap --sample 20000    # corpus label distribution -> gazetteer/confidence
uv run oik silver label                     # emit silver over the train split (~5 min)
uv run oik silver label --min-confidence 0.5  # abstain on the noisy tail

# Phase 7 (entity NER — does DAPT beat off-the-shelf GreBerta?)
uv run oik ner prepare                          # freeze BIO label schema from silver
.venv/bin/modal run --detach modal_app/ner.py::push     # upload silver/gold/labels
.venv/bin/modal run --detach modal_app/ner.py::xval               # b1: silver-only vs silver→gold (5-fold CV)
.venv/bin/modal run --detach modal_app/ner.py::xval --loss gce    # step 2: noise-robust silver loss
.venv/bin/modal run --detach modal_app/ner.py::xval --backbone b0 # control's two-stage numbers
# NOTE: ner.py imports oikonomia in the container, so run with the venv's modal
# (not global). b1 needs the DAPT run to have saved /dapt/.../full/final. The
# git-committed Phase-7 silver-only b0-vs-b1 result predates `xval`.

# Quality gate — run after ANY unit of work, in this order
.venv/bin/ruff check src tests modal_app
.venv/bin/python -m mypy src
.venv/bin/python -m pytest
make clean                        # always clear caches afterwards
# During iteration, skip the whole-corpus scan: pytest -m "not corpus"
```

Modal extras (`.[modal]`, `.[train]`) are installed only when Phase 4 begins.

---

## 5. Pre-phase-transition checklist

Run every time before declaring a phase done and moving on:

1. `.venv/bin/ruff check src tests modal_app` — must pass with **All checks passed!**
   (`modal_app/` was omitted from the gate until Phase 4 and had accumulated lint.)
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
- **475 duplicate clusters covering 1,769 docs (2.89%)**. These would have
  leaked across a naive random split. *(Was 399 / 1,553 / 2.54% before the
  `<lb break="no"/>` parser fix — see §7. Split words made near-duplicates look
  different from each other, so the old figure understated leakage by 216
  documents. Detected only because the fixed parser forced a rebuild.)*
- 59,581 atomic groups. Grouping unions two signals: shared TM id and
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

### 🔶 Phase 4 — DAPT on Modal (built and priced; TRAINING NOT YET RUN)

**Status: everything up to the GPU is built, tested and verified. No training
has been launched.** Do not read a DAPT result into this.

**Backbone changed from the original plan.** Primary is **B1 = GreBerta +
papyri DAPT**, not GreTa: encoder-only beats encoder-decoder on NER by ~15-17
F1, GreBerta is apache-2.0, half the size, 512 context, and T5's decoder would
be discarded anyway. koine-t5-omni is out on four counts (NC licence,
biblical-literary register, wrong architecture, 256-token truncation of ~25%
of documents).

#### The number that governs every other decision here

GreBerta is 110M params; the packed train shard is **8.3M tokens** — **0.075
tokens per parameter**. The DAPT literature used 2.1–8.1 **billion**-token
corpora: **250–1000x more**. Its recipe does not transfer, and this must be
checked before importing any published hyperparameter.

**There is no more in-domain data.** DCLP (literary papyri, already on disk,
14,842 files) parses 300/300 with the existing parser but yields only ~1.4M
tokens (+17%) and pulls the register *away* from documentary Greek — the same
objection that ruled out koine-t5-omni. Rejected unless the dev curve shows
genuine starvation.

#### What was decided, and why

1. **Epoch count is not guessed — the dev set ends the run.** Early stopping on
   held-out perplexity (`load_best_model_at_end`, `metric_for_best_model=
   eval_loss`, patience 5) with `max_steps` as a generous *ceiling* (4,048
   ≈ 16 epochs). The earlier "12,500 vs 2,024 steps" argument was the wrong
   argument: the dev curve knows the answer and we do not.
2. **LoRA is the default; full fine-tuning is the challenger.** This reverses
   the first draft. At 0.075 tokens/param the binding constraint is *data, not
   capacity*, so "LoRA learns less and forgets less" costs nothing here — and
   koineformer adapted this same backbone family with LoRA r=16 on 1.5M tokens.
   **Falsifiable prediction: LoRA wins or ties.**
3. **It is decided by measurement, because measuring is cheap.** A full run is
   **15–45 min, ~$0.25–0.80** on an A10. `modal run modal_app/dapt.py::sweep`
   runs LoRA and full in parallel and reports dev perplexity for both. Arguing
   about it costs more than running it.
4. **`hit_ceiling` in the sweep output is the data-starvation signal.** If a
   run is still improving when the ceiling stops it, raise the ceiling — and
   only then reconsider DCLP.
5. **seq_len is a live variable, not a default.** Median papyrus ≈ 74 tokens,
   so a 512-block packs ~7 unrelated documents and most attention is
   cross-document noise. 256 halves that and doubles the block count.

**Deliverables**
- `dapt/text.py` — train-split-only stream; **refuses to run without a split
  table**, since DAPT is unsupervised and would otherwise language-model the
  test set with nothing complaining. Lowercases (GreBerta's BPE merges are
  lowercase-only) while keeping accents (its vocabulary has them).
- `dapt/pack.py` — uint16 memmap blocks, packed not padded.
- `dapt/schedule.py` — derives steps from the shard.
- `dapt/stage.py` — packs **train and dev only**; no test shard is ever
  written, the cheapest possible guarantee it is not read.
- `modal_app/dapt.py` — A10, LoRA/full, early stopping, Volume checkpoints
  with retry+resume, `push` / `launch` / `sweep` entrypoints.
- `tests/test_architecture.py` — enforces §3: no heavy module-level imports in
  the library, and the library never imports `modal_app`.
- CLI `oik dapt {prepare,inspect}`. 190 tests total.

**Built for real (GreBerta's actual tokenizer, not a mock):** train 16,109
blocks x 512 = **8.25M tokens** from 46,166 docs; dev 2,146 blocks = 1.10M
tokens; ~15s on a laptop. *(Token count fell slightly after the
`<lb break="no"/>` fix — a whole word costs fewer BPE pieces than two
fragments, so this is the same text more efficiently encoded.)*

**Verified live, not recalled:** `transformers` 5.14 removed
`evaluation_strategy` for `eval_strategy` (image pins `>=5.0,<6`);
`DataCollatorForLanguageModeling(tokenizer=, mlm=, mlm_probability=)` current;
Modal `gpu="A10"` not `"A10G"`; `Volume.from_name(create_if_missing=True)`;
**`.map()`/`.starmap()` are positional-only and cannot vary kwargs — use
`.spawn()` + `FunctionCall.get()`** for the sweep.

**Corrections made after the first draft — all were wrong on inference, right
only after testing:**
- **Case is preserved now.** The first version lowercased everything, reasoning
  from GreBerta's vocabulary file that capitals would shatter. Tokenising shows
  the opposite (see §7): it keeps case, `Γεώργιος`≠`γεωργός`, and keeping case
  is **−0.59% tokens**. Lowercasing discarded the best PERSON/PLACE cue.
- **Blocks are framed `<s> … </s>`.** Raw packed streams are off-distribution
  for RoBERTa at position 0 and the loss never reports it.
- **LoRA is attention+FFN**, names qualified to exclude the tied LM head.
  Attention-only was an over-correction; FFN is where domain content lives.
- **Gap tokens excluded from masking.** `…` is 6.0% of the token stream and was
  eating the masking budget *and* deflating the dev perplexity that early
  stopping selects on.

**Next action:** `modal run modal_app/dapt.py::push`, then `::sweep`.
**But the honest recommendation is to do Phase 5 first** — every sweep result
is a perplexity proxy for a task F1 that cannot be measured until gold exists.

**Still not built:** the B0 (no-DAPT) control. Without it no DAPT gain is
believable.

### ✅ Phase 5 — Gold annotation (115 docs, ALL human_validated)

**Status: 115 documents** (`data/gold/annotated.jsonl`, **2,995 entities /
623 relations**, `oik gold check` **0 errors**, `numerals_checked: true`, every
text byte-identical to `corpus.parquet`). **All 115 are now
`provenance: human_validated` / `reviewed_by: abderahmane-ai`** — the owner
reviewed this session's 20 model-drafts (13 hard-batch + 7 AGE-targeted), so the
whole set is a clean eval/fine-tune anchor with no draft-scoring-draft
circularity (the Phase-7b "±few pts from un-reviewed drafts" caveat is now
retired). Drafted by `claude-opus-4-8`, reviewed by the owner. Guidelines **v0.3**.

#### AGE un-starved: 6 → 133 (2026-07-22, second half of session)

AGE was the last unlearnable class (6 instances; Phase-7b scored it 0.0). Fixed
by mining the **train split** for the census/signalement age formula
`(ὡς) ἐτῶν N` (`scratchpad/find_age_docs*.py`: rank by age-numeral density, dedup
by `group_id`, exclude gold), then annotating **7 age-dense docs** →
**+127 AGE** (now 133, a fully learnable class):
- `25173 26167 27453 11440 29529` — signalement/poll-tax lists where **every
  tagged numeral is an age**; AGE spans generated **directly from the corpus
  `<num>` offsets** (`scratchpad/age_build.py`, `age_all=True`) — zero surface
  ambiguity — with names forward-scanned. `11440` alone: 33 ages + 62 PERSON
  (registrant + mother, per the mother rule). `29529`'s trailing `N φυλῆς` tribe
  ordinals are `non_referential` skips.
- `12351` (grazing lease, 12 witness-ages + a freedman `ἀπελεύθερος`) and
  `12906` (epikrisis, 14 ages + `δοῦλος`/`ἰδιώτης` statuses) — mixed age+date
  docs, every span explicit; the `θ ἔτει`/`ιζ ἔτους` regnal years correctly went
  to DATE_REF, not AGE (verified: no date numeral mislabeled as age).

Session entity lift (committed HEAD 85 docs → 115): **AGE +127, PERSON +288,
TAX_TERM +45, FRACTION +35, PERSON_ROLE +23, OCCUPATION +70** (total +1,042
entities). Every AGE numeral gate-verified; `find_age_docs2.py` still lists ~900
more train age-docs (and huge poll-tax registers of 100–220 ages each) if more
is ever wanted.

#### Hard-batch extension + a silent-corruption fix (2026-07-22 session)

The owner curated a **hard batch** (`data/gold/hard_data_batch.jsonl`, 24 docs)
to feed the starved rare classes and hand-annotated the first 10 into gold; a
`batch_2.jsonl` holds the leftover 15 (14 hard + `702571`). This session:

1. **Verified the owner's 10 hard docs and fixed 3 load-bearing bugs.** Three of
   them (`7797`, `40966`, `41308`) had gold `text` that was **not byte-identical
   to `corpus.parquet`** — the hard-batch file itself carried a silently
   *normalized* text (`γίνεται`→`γίνονται`, final-sigma→medial-sigma). Because
   the numeral-coverage gate keys on an exact `text` match, a non-matching text
   **silently disabled the gate for those docs** (`numerals=None`), so their
   coverage was never actually checked. Fixed by rebasing each onto canonical
   corpus text and remapping all 135 entity/skip offsets through a `difflib`
   alignment (every remapped span's corpus substring re-verified against its
   recorded text). Also removed **3 phantom `skipped_numerals`** (`ω`, `μα`,
   `πρώτῃ`) that pointed at tokens the corpus never tagged `<num>`. Result: every
   gold doc byte-identical, gate live on every doc, **0 errors**.
2. **Annotated 13 more hard docs from scratch** (`77576 78637 77107 75749 79378
   702571 793 5344 7560 5414 703351 76201 43027`) via surface-string forward-scan
   (offsets computed, never hand-written — same method as
   `tools/build_gold_draft.py`, text pulled from `corpus.parquet`, **not** the
   corrupted batch files). +352 entities / +81 relations. The pre-existing
   `entities` in `hard_data_batch.jsonl` are low-quality auto-suggestions
   (broken relation indices, many uncovered numerals) — **do not trust them**;
   re-annotate.
3. **Rare-class yield** (HEAD 85 → now 108): **TAX_TERM 23→66 (+43)**,
   **FRACTION 61→96 (+35)**, **PERSON_ROLE 21→38 (+17)**, **OCCUPATION
   122→182 (+60)**, AGE 6→9 (+3, all from the owner's `7797`). The 13
   model_drafts are TAX_TERM- and FRACTION-heavy (poll/sales/rent-tax receipts,
   aroura fractions ιϛ=1/16 λβ=1/32, Byzantine occupation lists) plus `43027`'s
   two guardian-formula `PERSON_ROLE`s and a freedwoman (`ἀπελευθέρᾳ`).

**AGE was then un-starved 9→133** by a dedicated pass over 7 census/signalement
docs (see the AGE subsection above). Rare classes now: TAX_TERM 68, FRACTION 96,
PERSON_ROLE 44, AGE 133 — all comfortably learnable.

The generating spec for the original gold is `tools/build_gold_draft.py`; **note
it `write_text`-overwrites the whole file from its 85-doc SPEC**, so running it
now would drop the owner's 10 + this session's 20 (none is in its SPEC) —
append future docs, do not regenerate. The session's appender specs lived in the
scratchpad and are gone; the artifacts are the JSONL rows.

**Phase 5 was closed at 65 of the planned 150** (owner decision) so training
can begin; the remaining 85 batch documents stay available in
`data/gold/to_annotate.jsonl` and can extend the gold later. 65 validated
documents is a usable first gold set (the literature's floor for a first eval).

**The completeness pass (this session).** A reading audit had rated the 50 docs
"9.8/10", but that could not verify *completeness* — you cannot eyeball the
absence of a span you never wrote. Cross-referencing the corpus's own `<num>`
tags against the gold found **34 tagged numerals with no decision** across 15
docs — including real money (the account doc 16219 left 12 solidi/carat figures
unlabelled; the sale 20815 left the `Αφ`=1500 / `Γ`=3000 sums). All 34 are now
fixed. To make this a standing guarantee, `oik gold check` gained a
**numeral-coverage gate**: it loads the corpus `<num>` offsets (keyed by text,
which also re-proves byte-identity) and **fails** on any numeral neither inside
a span nor in a new per-document `skipped_numerals` list (reasons:
`isopsephism` / `sheet_number` / `line_reference` / `non_referential`). It also
prints non-fatal **advisories** (capitalised tokens with no span → candidate
missed names; lone money amounts; unlinked quantities; party-less
transactions). Advisory count was driven 48 → 27; the residue is theonyms,
damaged name-fragments, fused money-words (`τετρώβολον`) and `γίνεται` summary
totals — each reviewed and deliberately left (guidelines §5 "completeness
pass", v0.3). **Lesson reinforced: the numeral gate is now the mechanical
backstop the reading audit could not be — run it, and honour its advisories,
before every batch.**



**This is the bottleneck for the whole project.** There is zero entity markup
upstream (verified 0% over 200 documents), so every label must be created by
hand. Nothing in Phases 7–11 can be evaluated until this exists, and Phase 4's
sweep is currently optimising *perplexity* as a proxy for a task F1 nobody can
yet measure.

#### What a document actually looks like

Real example, `doc_id 134`, a receipt from the train split (394 chars):

> ἔτους νβ Παχὼν κα. τέτακται ἐπὶ τὴν ἐν Κροκοδίλων πόλει τράπεζαν ἐφʼ ἧς
> Ἀπολλώνις δεκάτης ἐνκυκλίου … παρὰ Πανίσκου καὶ Κεφάλωνος τελωνῶν … ὑπογράφει
> Πολυδεύκης ὁ ἀντιγραφεὺς / Νεχούτης ὃς καὶ Εὔνομος Πατσεοῦτος οἰκίας
> ᾠκοδομημένης … ἣν τέθεικεν Πατσεοῦς ὁ πατὴρ αὐτοῦ χαλκοῦ δραχμῶν Β, οὗ ἀλλαγὴ σ.

*(Year 52, Pachon 21. Paid to the bank in Krokodilon Polis over which Apollonis
presides, for the 10% sales tax … from Paniskos and Kephalon the tax-farmers …
signed by Polydeukes the checking-clerk: Nechoutes also called Eunomos, son of
Patseous, for a house … which his father Patseous deposited, of bronze drachmas
2000, of which the exchange fee 200.)*

#### What annotating it means, concretely

Marking **character spans** into `edited_text` and typing them, then linking
them. For this document, 18 entities:

| span | label | text |
|---|---|---|
| 6:14 | DATE_REF | `ἔτους νβ` |
| 15:23 | DATE_REF | `Παχὼν κα` |
| 45:61 | PLACE | `Κροκοδίλων πόλει` |
| 78:87 | PERSON | `Ἀπολλώνις` |
| 88:105 | TAX_TERM | `δεκάτης ἐνκυκλίου` |
| 127:135, 140:149 | PERSON | `Πανίσκου`, `Κεφάλωνος` |
| 150:157 | OCCUPATION | `τελωνῶν` |
| 185:195 | PERSON | `Πολυδεύκης` |
| 198:209 | OCCUPATION | `ἀντιγραφεὺς` |
| 217:225, 233:240, 241:251 | PERSON | `Νεχούτης`, `Εὔνομος`, `Πατσεοῦτος` |
| 252:258 | COMMODITY | `οἰκίας` |
| 340:348 | PERSON | `Πατσεοῦς` |
| 363:369, 370:377 | CURRENCY | `χαλκοῦ`, `δραχμῶν` |
| 378:379 | MONEY_AMOUNT | `Β` (=2000) |
| 384:390 | PRICE_TERM | `ἀλλαγὴ` |
| 391:392 | MONEY_AMOUNT | `σ` (=200) |

…plus relations: `Β —HAS_CURRENCY→ δραχμῶν`, `οἰκίας —HAS_PRICE→ Β`,
`Β —CHARGED_UNDER→ δεκάτης ἐνκυκλίου`, `Νεχούτης —PARTY_OF→` the transaction,
`transaction —DATED_TO→ ἔτους νβ`.

**The baseline finds 6 of those 18.** It gets the money right and misses every
PERSON, PLACE and OCCUPATION. That gap is precisely the value gold annotation
adds, and the reason Phase 5 gates everything.

#### Two defects this example exposed — both fixed

1. **`DATE_REF` now absorbs its numeral.** The code used to emit `ἔτους` alone
   and suppress `νβ`, discarding the year while the guidelines required one
   span. It now merges in either order (`ἔτους νβ`, `Παχὼν κα`, `ιϛ ἔτος`),
   with adjacency capped at `DATE_ADJACENCY = 4` chars so a later amount on the
   same line is not swallowed.
2. **Occupations are now mined from title position** (`oik lexicon mine-titles`).
   Occupations follow a *name*, not a numeral, so the numeral-context miner
   structurally could not see them. Names are located by **capitalisation** —
   the signal recovered by not lowercasing (see §7). Added 9 entries
   (praktor 594 docs, banker 359, priest 210, tax_farmer 177, village_scribe
   173, overseer 127, notary 123, logistes 96, checking_clerk 67), curated
   against false friends: `ἀντίγραφον` ("a copy") is not `ἀντιγραφεύς` (the
   clerk), and `τράπεζα` (the bank) is not `τραπεζίτης` (the banker).

OCCUPATION coverage went 13,938 → **21,470** matches corpus-wide; the lexicon
is now 97 entries / 378 forms, all corpus-attested (`oik lexicon verify`).
On document 134 the baseline went from **6 to 8** of the 18 gold entities. The
remaining 10 are PERSON (×7), PLACE, COMMODITY and TAX_TERM mentions that no
lexicon will reach — which is exactly what gold annotation is for.

#### The batch is built — `oik gold sample`

`data/gold/to_annotate.jsonl` — **150 documents, 90.5k characters**, tracked in
git. Regenerate deterministically with
`oik gold sample --n 150 --iaa 30 --blind 30`. Format, labels, workflow and all
decision rules live in the single authority
[`resources/schema/annotation_guidelines.md`](resources/schema/annotation_guidelines.md)
(v0.2; §6 covers the batch file format and workflow, §0 the ten rules).

The sampler enforces four things that are easy to get wrong by hand:
- **train split only, one document per group** — near-duplicates and shared-TM
  documents cannot both be drawn, which would spend the budget twice and
  inflate agreement;
- **genre-capped**: 12–13 documents each across 11 genres, against a corpus
  that is 25% receipts;
- **spread over time**: 17–24 documents per era, not clustered in the 2nd
  century where the mass is;
- **20% deliberately low-numeral**, so PERSON/PLACE are seen in prose and not
  only in accounting lines.

It also filters what would waste annotator time: **Latin documents** (idp.data
carries them; 3 were in the first draft at 0% Greek) and documents more than
10% lacunae. Length is bounded to 120–1,600 characters.

30 documents are flagged `double_annotate` for agreement. **30 carry no
suggestions at all** (`suggested_entities: null`) — pre-annotation anchors the
annotator, so the blind subset is the only honest basis for a later
baseline-vs-gold comparison. Annotate those first, while unanchored.

#### Interlude: the batch was rebuilt after a parser fix (2026-07-20)

Reading a real document during annotation review surfaced `ναύκλη ρος` — a
single word split by a space. The parser emitted a separator at every `<lb>`,
ignoring `break="no"`, which marks a break *inside* a word. 35.28% of documents
were affected, 96,323 occurrences. §7 has the full anatomy, including why the
obvious one-line fix changes nothing visible (the space comes from the XML's
indentation, not from the parser's newline).

Fixing it exposed that the stored text was full of the XML's indentation
anyway (a line boundary read `'\n\n    \n'`), which each consumer was quietly
collapsing on its own — so the parser now canonicalises whitespace and remaps
every span (v4; see "Resolved" below).

**Everything downstream was rebuilt**: `build_corpus` v2→v4, splits, DAPT
shards, and the annotation batch (94.6k → 90.5k chars; `Ἡρά κλειαν` is now
`Ἡράκλειαν`). Parse rate stayed 1.000 (67,980/67,980, 0 failures) and the
HGV join rate stayed 0.9827.

**The rebuild found a second, worse bug.** `build_splits` refused to re-run —
"skipped (fresh)" — because its `inputs_key` was the pinned corpus rev, which
had not changed. Forced through, the duplicate clusters moved **399 → 475**
(1,553 → 1,769 documents, 2.54% → 2.89%): split words had been hiding real
near-duplicates, i.e. real train/test leakage. Downstream stages now key on
upstream output hashes (§3), with a regression test in
`tests/test_pipeline_manifest.py`.

**Worth internalising:** the text bug was cosmetic-looking and its damage was
silent and structural. It was found by *reading actual output*, not by any
test — parse rate, mypy and 300+ tests were all green throughout.

#### ✅ Resolved: there is now exactly one coordinate system

Previously `corpus.parquet` stored `edited_text` with the XML's indentation
intact while three consumers each re-collapsed whitespace independently, so
gold spans indexed a *different string* from `OffsetMap`, markup and numeral
spans. Fixed at the source: **the parser is the only component that decides
whitespace** (`build_corpus` v4).

`finalize()` canonicalises both views — a whitespace run collapses to one
character, leading/trailing padding goes — and **remaps every span through the
same index table**: markup, numerals, lines and the aligned segments. Because
canonicalisation only ever *deletes*, an old span `[i, j)` becomes
`[prefix[i], prefix[j])` where `prefix[i]` counts survivors before `i`.

Aligned segments are the subtle case and are split, not just shifted: a
character can survive in one view and not the other (the space after an
edited-only `<supplied>` may end a run in the edited view while the diplomatic
view still needs it). Such a character is left uncovered — exactly as
view-specific text already is — and the segment splits around it.

`gold/sample.py` now uses `edited_text` **verbatim**. Verified over the built
artifacts: all 150 batch documents are byte-identical to the stored text, and
all 1,127 suggested spans select exactly the text they claim.

#### Annotation is validated mechanically — `oik gold check`

The first hand-annotated documents exposed three defects that no other check
would have caught, and all three are mechanical:

1. **`end` treated as inclusive.** Every span came out one character short
   (`Ῥώμη` for `Ῥώμης`), and one-character spans — `QUANTITY` "β", the single
   commonest label in an account — collapsed to `start == end`, i.e. an empty
   span that trains on nothing and scores as nothing.
2. **Annotating a stale batch.** Offsets drifted further out the deeper into
   the document you read (+0, +1, +2 …) — the signature of annotating the
   pre-`break="no"` text, where each joined word later removed a character.
3. **Reversed relations.** `HAS_QUANTITY` written `QUANTITY → COMMODITY`.

`gold/validate.py` + `oik gold check` verify that every span selects the text
it claims, that relation endpoints match the signatures in the guidelines, and
that indices are in range. **`--fix` repairs offsets from the `text` field**,
which is exactly why every span carries its own text — the text is ground
truth, the offset is only a pointer to it. Spans whose text is absent from the
document are left failing for a human. Relation *direction* is never
auto-fixed: that is a judgment call against the guidelines.

**Open schema gap this surfaced.** `PARTY_OF`, `DATED_TO`, `PAID_BY`, `PAID_TO`
are defined as pointing at "the transaction" — which is not an entity, so there
is nothing to point at. Real annotation pointed them at the good or the amount
instead. Reported as `relation_unanchored`. Decide with real examples in hand:
either add a transaction/event entity, or redefine these as document-level
attributes. This blocks nothing today but must be settled before Phase 8.

#### Remaining choices

- **Sample from the train split only.** Annotating dev/test documents
  contaminates them. `splits.parquet` → `split_random == "train"`.
- **Stratify** by `stratum` (genre × date bucket) so the budget is not spent
  entirely on the 15,465 receipts.
- **Size:** 100–200 documents is the usable range in the literature for a first
  gold set; 10–30 double-annotated for agreement. Target κ ≥ 0.80 on entities.
- **Format:** JSONL, one document per line, character spans — matching
  `CharSpan` exactly so it loads without a converter:
  ```json
  {"doc_id": "134", "text": "...", 
   "entities": [{"start": 45, "end": 61, "label": "PLACE"}],
   "relations": [{"head": 0, "tail": 3, "type": "HAS_CURRENCY"}]}
  ```
- **Tools:** INCEpTION (standard in DH/classics), Label Studio, or doccano. All
  export character offsets.
- **On pre-annotation:** loading the weak baseline's output as a starting point
  roughly halves annotation time, but it **anchors the annotator to the
  baseline's decisions and inflates the baseline's apparent agreement with
  gold**. If used, do not report baseline-vs-gold numbers from pre-annotated
  documents — keep an un-pre-annotated subset for that comparison.
- **Store in `data/gold/`** — that tier is tracked in git, unlike the rest.

Guidelines: [`resources/schema/annotation_guidelines.md`](resources/schema/annotation_guidelines.md)
— now **v0.2**, led by a "§0 The ten rules" one-screen spine that resolves the
recurring decisions; §5 records every case settled against real text. Three
project-owner decisions are locked (2026-07-21): **full relation scope**
(every transaction carries `PARTY_OF`/`DATED_TO`/`HAS_PRICE`, not just the
measurable links), **one `PERSON` span including filiation**, and
**genitive-named parcels are `PLACE`** (`Εἰρηναίου κλήρου`). The gold
(`data/gold/annotated.jsonl`, now **115 docs, all `human_validated`**, `oik gold
check` clean) is calibrated to these decisions. **Do not regenerate the whole
file** — append only (§9/§10); `tools/build_gold_draft.py` builds only the
original 85. Expect §5 to keep growing as real documents are annotated — that
growth *is* the deliverable as much as the spans are.

### 🔶 Phase 6 — Weak/silver labeling (labeler built + validated; full train emission done)

#### ✅ Silver v2 — accuracy pass on the 115-doc all-human gold (2026-07-23)

A diagnose-then-fix pass, every change measured with `oik silver score`. **Entity
micro F1 (exact span): 0.585 → 0.667** (+0.082), no label regressed:

| label | before | after | fix |
|---|---|---|---|
| **AGE** | 0.000 | **0.970** | bug: `ἐτῶν N` was mislabeled DATE_REF (year-word); AGE rule only reclassified QUANTITY so it never fired. Now built from the `<num>` after ἐτῶν (gen. pl.), distinct from ἔτους/ἔτει regnal years. +133 AGE **and** −133 DATE_REF false positives. |
| **OCCUPATION** | 0.275 | **0.649** | +33 corpus-attested title entries (βοηθός, στρατηγός, νοτάριος, διάκονος, ἰατρός, ναύκληρος, ποιμήν …). Precision *rose* to 0.876. |
| **DATE_REF** | 0.386 | **0.518** | Καίσαρος/Αὐτοκράτορος/Σεβαστοῦ removed from the DATE_REF lexicon — gold's "ruler keeps titulature" rule tags them PERSON, so as DATE_REF they were 65 FPs. |
| **PERSON** | 0.683 | **0.715** | side-effect of the above — the titles now absorb into the ruler PERSON span. |
| **COMMODITY** | 0.444 | **0.554** | +property/land/animal entries (οἰκία, γῆ, ὄνος-not-ὄνομα, κάμηλος, πωμάριον, παράδεισος). |
| MONEY_AMOUNT | 0.650 | 0.652 | `_nearest` now reaches one line across for currency/unit (`νομισμάτιον\nἓν`), the EOL-currency/BOL-numeral split; also unblocks direction's amount. |

Also: payment-direction verbs widened (leases/orders — τελεσ, δωσ, δεδωκ, παρασχ,
μετρησ, διαστ, διαγραψ, εδεξ); direction still recall-bound (rule ceiling — it is
the Phase-8 model's job, not the silver's). `oik lexicon verify` 0 unattested;
ruff/mypy/408 tests green. **`silver.jsonl` must be re-emitted** (`oik silver
distmap` → `oik silver label`) and re-pushed for these gains to reach the model.

**Status: the silver labeler is built, scored against the gold, and run over the
whole train split.** `data/processed/silver.jsonl` (gitignored)
— **48,941 docs, 1,110,796 entities, 327,789 relations** (pre-v2; re-emit),
every span carrying a calibrated `confidence`. This is *training* material
(`provenance: silver`) — not gold, not the database.

**The scorer came first** (`labeling/score.py`, `oik silver score`): scores any
labeler against the gold per label, strict (exact span) and relaxed (overlap),
plus directed relations. It showed the Phase-2 baseline is *structurally blind*
to PERSON (30% of entities), PLACE, TRANSACTION, PERSON_ROLE, AGE — entity
recall 0.37, those five at 0.

**The labeler** (`labeling/silver.py`, `SilverLabeler`) is built *on top of*
the baseline — keeps the economic spans, adds LFs for the missing types, every
rule calibrated to a measured signal and stored in
`resources/silver/patterns.yaml`:
- **PERSON** — capitalisation (99.8% of gold persons are capital-initial),
  merged across filiation/alias particles (`Πτολεμαὶς Χαιρήμονος τοῦ Χαιρήμονος`
  is one span; bare `καί` splits co-parties; `ὃς καὶ` alias joins), minus
  standalone imperial titulature and calendar months.
- **PLACE** — admin-noun context (`κώμης X`, `X πόλεως/μερίδος/νομοῦ/κλήρου`) or
  a toponym gazetteer; the admin noun is part of the span.
- **TRANSACTION / PERSON_ROLE** — closed-class folded-stem prefixes, both
  lowercase-guarded (0/41 and 0/20 gold cases are capitalised); κύριος gated
  behind μετά/χωρίς; one TRANSACTION per document.
- **AGE** — a numeral next to ἐτῶν. **Relations** — the baseline's economic
  links plus PARTY_OF (roles + prep-marked names + the transaction's nearest
  name), DATED_TO, HAS_PRICE.

**Measured lift over the baseline** (65 gold docs, `model_draft` — agreement,
not truth):

| | baseline | silver |
|---|---|---|
| entity micro F1 exact | 0.412 | **0.598** |
| entity micro F1 relaxed | 0.470 | **0.723** |
| PERSON F1 (exact / relaxed) | 0 / 0 | **0.65 / 0.86** |
| PLACE F1 exact | 0 | **0.61** |
| relations micro F1 | 0.448 | ~0.45 |

**Three denoising moves, each validated against gold before the next:**
1. **Corpus type-consensus (majority override) — REJECTED by its own
   validation.** 96% of its changes flipped PLACE→PERSON (it *amplifies* the
   systematic bias), and corpus self-consistency was already **0.992** — the
   labeler's noise is ~99% systematic, not diffuse, so consensus has almost
   nothing to fix. **Lesson: aggregation cannot fix systematic noise, only
   independent signals can.**
2. **Directional place gazetteer + systematic-bug fixes — kept.** The corpus
   label distribution (`oik silver distmap` → `silver_label_dist.json`) yields a
   gazetteer of place-dominant, rarely-person forms that promotes PERSON→PLACE
   (only that direction is safe). Neutral on the 65 docs (they cannot see
   corpus-scale recall), but building it exposed real systematic bugs — the
   seed stem `αλεξανδρ` labelled the person Ἀλέξανδρος as PLACE, and months
   leaked to PERSON. Fixing those: **PLACE precision 0.69→0.74**.
3. **Confidence + abstention — kept, the real lever.** Every span carries a
   calibrated confidence: corpus-agreement for surface-decided labels (a
   validated predictor of correctness — the 0.7–0.9 band is a 0.33-precision
   sink), measured precision priors for the rest. `oik silver label
   --min-confidence 0.5` drops ~33% of entities and ~64% of relations —
   precisely the measured-noisy labels (DATE_REF, QUANTITY, TAX_TERM, PARTY_OF,
   DATED_TO). This keeps the systematic-noise tail out of training instead of
   feeding it as truth.

**The binding constraint this surfaced:** the 65-doc gold is at its resolution
limit — two corpus-scale denoisers both scored ~0.000 on it. Validating
corpus-scale denoising, or a label-model combiner (deliberately **not** built
for this reason), needs a larger / human-reviewed gold. And the gold is still
`model_draft`: these are agreement figures, not ground truth.

**Deliverables:** `labeling/score.py`, `labeling/silver.py`,
`resources/silver/patterns.yaml`, CLI `oik silver {score,distmap,label}`,
`confidence` on `WeakEntity`/`WeakRelation`, 25 tests. Ruff + mypy clean.

**Next:** finish Phase 5 gold to 150 + a human review pass, then train the
Phase 7 entity model confidence-weighted on `silver.jsonl` with the reviewed
gold as eval.

### 🔶 Phase 4b — DAPT run executed; full FT wins, prior FLIPPED

**The ledger's `LoRA wins or ties` prior was wrong for this stage and is now
retracted.** DAPT is *continued pretraining*, and for that regime the on-point
literature (Biderman 2405.09673) is that full FT beats low-rank adapters and the
gap does not close with rank; the `adapters ≈ full FT` results are all about the
downstream *fine-tune*, a different stage. Confirmed on GreBerta directly.

**Clean two-arm run** (`modal_app/dapt.py`, rewritten to two arms + per-arm LR):
`full` (full FT, lr 5e-5) vs `dora` (DoRA r=64, all-linear, rsLoRA, lr 1e-4) —
DoRA chosen as the *steelman* adapter (closest to full-FT geometry; beats LoRA
at all ranks). Both fresh from step 1, identical data, dev = the DAPT dev shard.
- **full: dev ppl 300 → 4.54, converged at the 16-epoch ceiling, NO
  overfitting** (dev loss never turned up; `hit_ceiling=1` but the curve is
  flat, i.e. converged not starved). Sharp phase transition ~step 1300→1700
  (ppl 70→6.7). Saved as `checkpoints/full/final` — **B1**, the papyri backbone.
- **dora: dev ppl ~415 → ~224, plateaued.** Learns, but ~50× behind full.

**Why the gap is that large (mechanistic, not just "adapters learn less"):**
full FT trains the **~40M token-embedding params (a third of the model)** plus
the LM head; the DoRA arm freezes them. Papyri's domain gap is heavily
*vocabulary/orthography* (onomastics, abbreviations, lacunae), so the embedding
remap is exactly the lever — and only full FT pulls it. At 125M params PEFT also
buys no memory (full FT fits the A10 trivially), so the adapter pays the compute
tax (DoRA materialises the merged weight per layer for its column-norm → ~2×
slower/step) without the benefit. **Verdict: full FT is the DAPT method.**

**Two bugs found and fixed mid-run, both worth remembering:** (a) the first
sweep's "LoRA wins ppl 92" was a *misread of interleaved untagged logs* — the
arms were swapped (`ClearLogger` now tags every line); (b) a fresh `compare`
silently **resumed stale checkpoints** from a prior run — the entrypoint now
clears the arm dirs (`reset_*`), while in-run resume for preemption is kept.
Also: shared LR starved the adapters; MLM logits (batch·seq·52k) OOM'd at bs=32
(now bs=16 × accum 4 + `expandable_segments`); train-loss display is `grad_accum×`
inflated by HF — **read eval ppl, not train loss**.

### ✅ Phase 7 — Entity NER: DAPT beats the control (+9.5 strict F1)

**The result the whole DAPT detour was for. B0 (no DAPT) vs B1 (papyri DAPT),
identical fine-tune on silver, scored on the 65-doc human-validated gold:**

| | b0 (control) | b1 (DAPT) | Δ |
|---|---|---|---|
| strict micro F1 | 0.495 | **0.589** | **+0.095** |
| relaxed micro F1 | 0.663 | 0.719 | +0.056 |
| PERSON | 0.458 | 0.648 | **+0.190** |
| PLACE | 0.503 | 0.617 | **+0.114** |
| MONEY_AMOUNT | 0.575 | 0.634 | +0.058 |

- **b1 ≥ b0 on every label**, strictly greater on most; nothing regressed.
  Squarely in the Gururangan "2–12 pts, largest at greatest domain distance".
- **The mechanism closed:** gains concentrate in PERSON/PLACE — the
  onomastic/toponymic labels the ~40M-param embedding remap (full-FT-only) was
  predicted to help. Lexicon-reachable labels barely move (CURRENCY .78→.79).
  The live `SAMPLE` proof: at eval 1, b0 tagged `Ῥώμης/PERSON` (wrong),
  b1 `Ῥώμης/PLACE` (right).
- **The ~0.59 ceiling is silver-bounded, not model-bounded:** b1's 0.589/0.719
  ≈ the silver labeler's own gold agreement (Phase 6). b0 can't even reach the
  silver ceiling — the weak backbone leaves ~9 pts on the table. Breaking past
  0.59 needs better *labels*, not a better backbone. b1 also converges far
  faster (~0.58 by epoch 0.3 vs b0 crawling to 0.49 over 2.6 epochs).
- **Weak spots:** OCCUPATION flat 0.239 (noisy silver), AGE 0.0 (5 gold / 149
  silver, too rare). Both models saved to the `oikonomia-ner` Volume
  (`models/{b0,b1}/final`). **Verdict: ship B1 as the entity backbone.**

**Next levers (raise the ceiling for both arms — label-side, not backbone):**
confidence-weighted silver loss (drop the 0.33-precision tail), sliding window
for the 512-truncated long docs, finish gold → 150 + human review.

**The harness that produced this:**
does the DAPT'd backbone give a better *NER* model? Measured on gold entity-F1.
- `oikonomia/ner/encode.py` — pure char-span ↔ BIO alignment (`align_bio` /
  `decode_spans`, inverses on token-aligned spans), + `ner/data.py` loaders. 7
  hand-computed tests. Metrics **reuse `labeling/score.py`** (`build_report`:
  strict + relaxed micro F1, per-label) — no duplication.
- `oik ner prepare` — freezes the BIO schema from silver to
  `processed/ner/labels.json`. **15 entity types**, every gold label learnable
  from silver (`gold_labels_not_in_silver: []`); 48,941 train docs / 1.11M
  silver entities, 65 gold eval docs / 1,654 entities.
- `modal_app/ner.py` — two arms, **b0 = bowphs/GreBerta (no DAPT, control)** vs
  **b1 = `/dapt/.../full/final` (DAPT)**, identical fine-tune on silver, scored
  on gold. Mounts the DAPT Volume read-only for b1. At each eval it decodes
  predictions → char spans → `build_report` and logs strict/relaxed F1 + per-
  label F1 + a **fixed-doc sample** (watch predictions improve across steps).
  Selection on `eval_strict_f1`; `compare` prints the **b1−b0 delta** — the
  actual finding. Runs with the venv's modal (container imports `oikonomia`).

**This is where "did DAPT help" is decided** — not perplexity. The strict-F1
Δ(b1−b0) is the number.

### ✅ Phase 7b — Two-stage silver→gold RUN: gold fine-tune is the recipe (strict 0.710 on 115-doc gold)

**Original result (b1 = DAPT backbone, 5-fold CV over the 85-doc gold; the
115-doc all-human re-run is the subsection below):**

| stage | strict F1 | relaxed F1 |
|---|---|---|
| silver-only | 0.584 | 0.709 |
| **silver→gold (CE)** | **0.672** | **0.785** |

- **Fine-tuning on the clean gold lifts strict F1 +8.8** and **breaks the ~0.59
  silver ceiling** — the diagnosis (label-bound, not model-bound) confirmed.
- **OCCUPATION 0.236 → 0.664 (+0.43)** is the clincher: Phase 7 had it frozen at
  0.24 for *both* backbones because the silver labels were systematically wrong;
  one pass on clean gold fixed it. Also DATE_REF +0.18, FRACTION +0.13, MONEY
  +0.11, QUANTITY +0.11, PERSON +0.08. Rare labels TAX_TERM/PERSON_ROLE regressed
  (14/20 gold ex — starved, high variance); AGE 0.0 (5 ex, unlearnable).

**GCE noise-robust loss — TESTED, REJECTED (−5.7 F1).** `--loss gce` gave
silver→gold strict **0.615** vs CE's 0.672. Mechanism backfired: GCE down-weights
low-confidence examples, but **rare classes are always low-confidence**, so it
*zeroed* OCCUPATION/FRACTION/TRANSACTION/TAX_TERM/PERSON_ROLE/PRICE_TERM at the
silver stage and gold couldn't fully rescue them. Also GCE targets *random* noise;
ours is ~99% *systematic* (Phase 6). Right tool, wrong regime.

**Lever ledger (all measured on gold F1, never guessed):**
`DAPT +0.094 ✓ · gold fine-tune +0.088 ✓ · GCE −0.057 ✗`. **Settled recipe:
DAPT backbone + silver (plain CE) + gold fine-tune → strict 0.672 / relaxed
0.785 on the 85-doc gold (→ 0.710 / 0.811 on the 115-doc all-human re-run below).**

**Caveat (now retired — see the re-run below):** 20 of the 85 gold docs were
un-reviewed `model_draft`s, giving the 0.672 mild circularity.

#### ✅ Re-run on the 115-doc, ALL-human-validated gold (2026-07-22)

Gold grown 85→115 (AGE un-starved 6→133; TAX_TERM/FRACTION/PERSON_ROLE ~2×) and
all 115 flipped to `human_validated`, then re-`push` + `xval --backbone b1
--loss ce`. **Result (5-fold CV, no draft-scoring-draft circularity):**

| stage | strict F1 | relaxed F1 |
|---|---|---|
| silver-only | 0.575 | 0.680 |
| **silver→gold (CE)** | **0.710** | **0.811** |

Gold-fine-tune Δ grew **+0.088 → +0.136**; the recipe is unchanged and now the
best measured (strict 0.710 / relaxed 0.811). Fold range 0.685–0.739.

- **AGE 0.0 → 0.947 — the batch's target, decisively hit.** Silver-only AGE is
  *still* 0.0 despite 149 silver AGE (the silver labels don't score on their
  own); the 133 clean gold examples both correct it and give it a real eval
  denominator. Same mechanism that fixed OCCUPATION, now proven for AGE.
- **Other gains:** FRACTION **0.82** (was +0.13 delta, now strong absolute),
  OCCUPATION 0.70, PERSON 0.75, MONEY 0.74, QUANTITY 0.71, DATE_REF 0.63.
- **The +0.038 vs 0.672 is partly reweighting** — the eval now includes AGE the
  model does well on, so it is not a clean apples-to-apples lift; the per-label
  numbers are the honest evidence.
- **Two classes did NOT respond to more data (correcting the prior prediction):**
  **TAX_TERM 0.440** (flat; silver-only 0.444 — doubling to 68 stopped the
  regression but bought no lift) and **PERSON_ROLE 0.396** (*still regresses*
  from silver-only 0.427 despite 44 ex). More-of-the-same won't move these —
  they need cleaner/more-consistent labels (PERSON_ROLE is heterogeneous:
  guardian formulas, statuses, unnamed roles) or a different lever, not just
  volume. This is the next real bottleneck.

**Built (`modal_app/ner.py`):** one `train` fn does **paired k-fold CV** — silver
trained **once**, then per fold: reset to the silver model, score the held-out
fold (**silver-only**), fine-tune on that fold's gold-train, score it again
(**silver→gold**); per-doc scores pooled across folds into one micro-F1 each.
`loss={ce,gce}`, `min_confidence>0` drops the low-confidence silver tail.
Entrypoint `xval --backbone b1 --loss ce|gce`.

**Done since (see the 115-doc re-run subsection above):** the 20 drafts were
reviewed → `human_validated`, AGE finished (0→**0.947**), and the rare classes
~doubled. **The lever that remains is TAX_TERM/PERSON_ROLE label *consistency*** —
volume is exhausted (doubling them moved nothing). Cheap untried test:
`xval --backbone b1 --loss ce --min-confidence 0.5` (hard-drop the noisy silver
tail). Self-training (BOND) / CRF head only if that falls short. Otherwise the
next build is **Phase 8 (relations)**.

### (superseded) original Phase 7b plan

**Why:** the Phase-7 ~0.59 is the *silver ceiling* (b1 hit it, b0 didn't) — both
arms only ever train on silver and never on the clean gold. The weak+clean
literature (NEEDLE 2106.08977; "Weaker Than You Think" 2305.17442) says the
small clean set should be the **final fine-tune stage**, correcting silver's
*systematic* errors (the noise Phase 6 measured).
Diagnosis: **label-bound, not model-bound** — so the levers are label-side; a
bigger backbone would hit the same wall.

**Built (`modal_app/ner.py`, rewritten):** one `train` fn does **paired k-fold
CV** — silver trained **once**, then per fold: reset to the silver model, score
the held-out fold (**silver-only**), fine-tune on that fold's gold-train, score
the same fold again (**silver→gold**); per-doc scores pooled across folds into
one honest micro-F1 each. `loss={ce,gce}` sets the silver-stage loss (`gce` =
generalized cross-entropy, the RoSTER noise-robust loss); `min_confidence>0`
drops the low-confidence silver tail. Entrypoint `xval --backbone b1 --loss ce`
(step 1) then `--loss gce` (step 2). Gold fine-tunes are cheap; silver runs once
per config. Ruff + compile clean.

**Plan (measured, one change at a time, all on the same gold via CV):**
1. `xval b1 ce` — silver-only vs silver→gold. **Predicted: the largest jump**
   (breaks the silver ceiling). 2. `xval b1 gce` — noise-robust silver, vs step 1.
3. Before running, **label ~20 more gold (65→~85)** and re-`push` — raises the
ceiling under everything and firms the CV. Later: soft confidence-weighting,
self-training on the 68k unlabeled corpus (BOND), CRF head — only if 1–2 fall short.

### 🔶 Phase 5c — Payment direction (PAID_BY / PAID_TO): silver engine built + tested; gold pass next

**Why (owner decision):** the gold captured *who was involved* (`PARTY_OF`) but
not *who paid whom* — direction was folded away. Direction is ~40% prevalent
(`παρά`/payment-verb markers, measured) and deliverable-core (price/wage series
need payer vs payee; "women as principals" needs active vs passive). `PAID_BY`/
`PAID_TO` were **already defined** in the schema (validate.py signatures:
PERSON/PERSON_ROLE → MONEY_AMOUNT/COMMODITY) but never used. Decision: **label
direction before the Phase 8 model** so the model is built once on the complete
schema. Rare *attested* relations (DATED_TO 32, HAS_PRICE 16, CHARGED_UNDER 13)
are NOT pre-labeled — the RE model decides which are volume-bound (the TAX_TERM
vs AGE lesson); the rule baseline scoring them ~0.10 is a *rule* failure, not a
data shortage.

**The signal is the VERB, not the case** (mined whole-corpus,
`scratchpad/mine_payment_verbs.py`): the same case flips role by verb —
*ἐσχηκέναι παρὰ σοῦ* (subject=payee, παρά=payer) vs *διέγραψεν X τῷ Y*
(subject=payer, dative=payee). Three classes: **receiver** (ἀπέχω, ἐσχηκέναι,
εἴληφα, κεκόμισμαι, ἔχειν — subject=payee, παρά=payer; co-occur with παρά
**40–65%**), **giver** (διαγράφω, μετρέω-grain, δίδωμι, καταβάλλω, τελέω —
subject=payer, dative/εἰς=payee), **impersonal** (τέτακται — payee=bank).

**Built (green):**
- `resources/silver/patterns.yaml` — `payment_{receiver,giver,impersonal}_stems`,
  `dative_endings`, `official_stems`. `SilverLabeler._direction_relations`
  (verb-anchored PAID_BY/PAID_TO, confidence-tiered in `PAID_CONFIDENCE`).
- **Precision filter: an amount (MONEY_AMOUNT/COMMODITY) must sit near the verb**
  — kills the παρά-of-a-petition trap and "received the *letter*".
- **Four systematic false-payer/direction bugs fixed** (each caught by smoke-
  testing on real gold docs, not reasoning): (a) `ὁ παρὰ X` / `τοῦ παρὰ X
  ἀγορανόμου` is X's *agent/official* (dating clause, scribal subscription),
  never the payer — excluded by the article-before-παρά rule; (b) παρά tightened
  to not match παρών ("being present"); (c) **a giver verb's following *dative*
  name is the PAYEE, not the payer** (*διέγραψε Σεκούνδῳ* "paid TO Secundus") —
  was flipping payer/payee on every *διέγραψε τοῖς πράκτορσι* tax receipt;
  (d) **`παρὰ τοῦ X`** (article between παρά and the name, "from THE X") now
  recognised as a payer — was silently missed.
- 10 hand-computed tests (`tests/test_silver_labeler.py`). **Gate green: ruff,
  mypy (61 files), 409 tests.** Guidelines **v0.4** (§5 payment-direction rule).
- **Coverage:** ~6,460 direction edges over the 48,941 train docs (8.6% of docs),
  confidence-tiered (precision-first; the ~40% marker rate includes excluded
  petitions). Confidences in `PAID_CONFIDENCE` are **PROVISIONAL** — replace with
  measured precisions once gold direction exists.

**Gold direction — VALIDATED + MERGED into the gold (2026-07-23).** The owner
gave the scope call (leases-with-future-rent, sales, in-kind distributions all
count as valid direction) and authorised merging every direction edge that is
correct. Done this session:

- **A Gemini review was checked and rejected.** An external model proposed
  swapping `PAID_BY`/`PAID_TO` on 8 of the 18 draft docs from a **case rule**
  ("nominative = payer, dative = payee"). That is exactly the heuristic §5 (v0.4)
  rejects — *the same case flips role by verb*. Every one of the 8 is a
  receiver-verb receipt/sale (ἔσχον/ἀπέσχον/ἔχειν) where the nominative subject is
  the **payee**; applying the swaps would have inverted the economics of each
  sale/loan. All 18 original docs re-verified correct against the verb rule.
  Gemini's one real catch — 4 `head_text`/`tail_text` cache strings truncated at
  a `\n` — was fixed (indices were always correct; only the denormalised text
  cache was stale).
- **The prior 64/11/17/18 triage was unrecoverable** (its builder
  `scratchpad/build_direction_draft.py` was deleted), so the payment-doc set was
  **re-derived from scratch over all 89 gold docs that carry a MONEY_AMOUNT or
  COMMODITY**. Each was read and classed: **~50 are genuine no-direction**
  (petitions, property/livestock registrations, admin letters, tax-assessment
  registers, fragmentary accounts, or docs whose only "party" is a
  matronymic/dating-consul — e.g. 15488 `Πτολέμας`); **20 new payment docs** got
  direction (loans, sales-tax/poll-tax receipts, fodder receipts, disbursement &
  ration orders, and 7 leases under the owner's scope call).
- **Result: `data/gold/annotated.jsonl` now carries payment direction —
  38 docs, 87 `PAID_BY`/`PAID_TO` edges** (18 original + 20 new). `oik gold check`
  **0 errors**, `numerals_checked`, relations **623 → 710**. All 87 pass the
  signature check (head∈{PERSON,PERSON_ROLE}, tail∈{MONEY_AMOUNT,COMMODITY}).
  `data/gold/direction_draft.jsonl` is kept as the complete auditable record of
  what was merged (38 docs, texts synced to gold).

The direction edges are Claude's linguistic calls, verified against §5 v0.4
(not individually eyeballed by the owner); the owner authorised the merge. The
20 new docs: `3141 5414 7797 15362 15454 15887 16396 16690 22840 36928 36941
38767 40966 41308 75749 76915 77107 78637 144620 702571`.

**Next:** (1) re-`push` gold to the `oikonomia-ner` Volume; (2) `oik silver
score` for per-direction precision → replace the **PROVISIONAL** `PAID_CONFIDENCE`
priors with measured values, tune recall (add verbs) if precision allows;
(3) re-emit `oik silver label`; (4) Phase 8 relation model on the
direction-augmented schema.

**Known residual (upstream, not direction):** the base capital-run PERSON merger
joins adjacent names with no bridge token (*Ψενθώτης Νεχούτου Πελαίαι Φίβιος* =
2 people as 1 span), which corrupts a giver-verb payer span and hides the dative
payee. Belongs to the PERSON LF, not `_direction_relations`.

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
- **`<lb break="no"/>` means the line break falls INSIDE a word — no separator
  belongs there.** The scribe ran out of room and continued on the next line.
  **23,982 of 67,980 documents (35.28%)** contain at least one; **96,323**
  occurrences corpus-wide. The parser emitted a separator at every `<lb>`
  regardless, so ναύκληρος came out as "ναύκλη ρος" — text no lexicon matches
  and no tokenizer handles well.
  **Two whitespace sources, and fixing only the first does nothing visible:**
  (a) the newline the parser itself emits, and (b) the XML file's own
  pretty-print indentation (`'\n\n    '`), which lands in the *preceding*
  element's tail and is what actually produced the visible space. Measured
  distribution of where (b) lives: `prev.tail` 82%, `parent.text` 9%, *inside*
  the previous element (e.g. `<supplied>ά\n  </supplied>`) 2%. On the far side,
  only `lb.tail` ever carries leading whitespace (0 of 705 cases where the tail
  is empty and an element follows). Handled by `_join_broken_words`, a pre-pass
  over the tree, so all offset accounting downstream sees correct text.
- **Near-duplication: 2.89%** (1,769 of 61,249 texted docs in 475 clusters,
  MinHash Jaccard >=0.8 over folded 5-grams). Enough to inflate a naive random
  split; not enough to distort corpus statistics. **This number moved from
  2.54% when the `break="no"` fix landed** — differently-broken words made two
  copies of the same text look different. A text-quality bug upstream is a
  leakage bug downstream.
- **Whitespace is canonical in `corpus.parquet`, and the parser is the only
  thing that decides it** (since `build_corpus` v4). Within a line, single
  spaces; one `\n` per real line break; nothing at a `break="no"` break; no
  leading or trailing padding. **Do not re-collapse it in a consumer** — that
  shifts every offset and silently decouples your spans from the stored text,
  which is exactly the bug v4 fixed. Verified over 1,500 random documents:
  0 occurrences of `'  '`, `' \n'`, `'\n '`, `'\n\n'`, or edge padding.
- **Gold `text` must be byte-identical to `corpus.parquet.edited_text`, and the
  numeral gate SILENTLY skips any doc where it is not.** `oik gold check` keys
  the `<num>` tags by exact `text` match (`_load_gold_numerals`); a mismatched
  text returns `numerals=None`, so `check_numeral_coverage` never runs for that
  doc and its coverage goes unchecked — no error, no warning. Found 2026-07-22:
  3 of the owner's hard docs (`7797`, `40966`, `41308`) carried a *normalized*
  text from `hard_data_batch.jsonl` (`γίνεται`→`γίνονται`, final `ς`→medial `σ`)
  that differed from corpus by 1–4 chars, so their gates had been silently off.
  **Any hand-curated batch file's `text` is suspect** — always source gold text
  from `corpus.parquet`, never from a batch/suggestion file, and cross-check
  byte-identity (a two-line diff) whenever gold rows are added by hand.
- **`<space>` is a *vacat*** — blank space deliberately left on the papyrus —
  and emits a space of its own. The source also puts literal spaces around it,
  so all three used to collide (`'Ποκῶτος   δραχμὰς'`). It is not a
  `MarkupKind`, so it produces no markup span.
- **Canonicalising text after spans exist requires remapping the spans**, and
  aligned segments must be *split*, not merely shifted: a character can survive
  in the edited view but not the diplomatic one (or vice versa), since each
  view's whitespace runs differ. Corpus-scale check: for every segment,
  `edited[e0:e1] == diplomatic[d0:d1]` — 0 mismatches over 1,500 documents.
- **1,706 documents share a TM id with another** — the same papyrus edited or
  republished separately. A real leakage group, and cheap to detect.
- Publication volume is far too coarse to group on: 1,025 volumes, largest
  holding 2,023 documents.
- Lexicon false friends share stems across categories: `χαλκεύς` (coppersmith)
  vs currency `χαλκοῦς`; `σιτολόγος` (grain officer) vs commodity `σῖτος`;
  `ἐλαιουργός` (oil-worker) vs `ἔλαιον`. These are OCCUPATION. Stem matching
  alone will mislabel them.

### Silver labeling (Phase 6, measured against the 65-doc gold draft)
- **PERSON is capitalisation.** 99.8% of gold PERSON spans are capital-initial;
  of all capitalised tokens, 71.6% are PERSON, 13.3% PLACE, ~6% titulature-in-
  dates, ~6% months — so capitalisation minus those exclusions is a strong
  PERSON detector. TRANSACTION and PERSON_ROLE are the opposite: **0/41 and
  0/20 gold instances are capitalised**, so those stems must be lowercase-gated.
- **The silver labeler's noise is ~99% systematic, not diffuse.** Corpus
  self-consistency (same form, same label across docs) is **0.992** before any
  denoising. Consequence, verified the hard way: a corpus-majority vote is
  *harmful* — 96% of its label changes flipped PLACE→PERSON, amplifying the
  systematic bias. **Aggregation cannot fix systematic noise; only independent
  signals or abstention can.**
- **Corpus-agreement confidence predicts correctness.** For surface-decided
  labels, confidence = the form's corpus-wide share of that label. Precision by
  bucket: ≥0.9 → 0.90, **0.7–0.9 → 0.33** (the danger zone), unseen novel form
  → 0.91. A `--min-confidence 0.5` filter drops the measured-noisy labels
  (DATE_REF 0.35, QUANTITY 0.46, TAX_TERM 0.26 and the PARTY_OF/DATED_TO tail).
- **The 65-doc gold cannot measure corpus-scale changes.** Both the place
  gazetteer and the consensus denoiser scored ~0.000 on it — their effects are
  on forms/docs outside the sample. Validating corpus-scale denoising (or a
  label-model combiner) requires a larger / human-reviewed gold. All Phase-6
  numbers are agreement-with-`model_draft`, not ground truth.
- **Seed-stem greediness is a real precision bug.** `αλεξανδρ` matched both
  Ἀλεξάνδρεια (place) and the person Ἀλέξανδρος; tightening to `αλεξανδρε`
  fixed it (PLACE precision 0.69→0.74). Month names (Θῶυτ, Ὑπερβερεταίου)
  missing from the date lexicon leak to PERSON unless stem-excluded.

### EpiDoc rendering (confirmed vs EpiDoc Guidelines)
- `<choice>`: edited uses `<reg>`/`<corr>`; diplomatic uses `<orig>`/`<sic>`.
- `<expan>`: `<ex>` (expansion) is edited-only; abbr letters are in both.
- `<supplied>` (lost/omitted): edited-only. `<surplus>`: diplomatic-only.
- `<app>`: render `<lem>` (chosen reading); ignore `<rdg>`.
- papyri.info blocks bots (Anubis) — rendered-text cross-checks are done with
  hand-crafted fixtures, not by scraping.

### Backbones (re-verified 2026-07-20, directly against HF model files)

**The bowphs family** (Heidelberg NLP, "Exploring LLMs for Classical Philology"):
- `bowphs/GreBerta` — **encoder-only RoBERTa-base, apache-2.0**, 12 layers,
  768d, 52k vocab, `max_position_embeddings` **514**. Reports UAS 88.20 /
  LAS 83.98 on UD 2.10.
- `bowphs/GreTa` — T5-base encoder-decoder, 0.2B, apache-2.0. Trained on
  Internet Archive OCR + Open Greek & Latin + CLARIN Medieval + Patrologia.
- `PhilBerta` / `PhilTa` are the multilingual (Greek+Latin+English) variants.

**Own models** (`ainouche-abderahmane/*`, all LoRA adapters over GreTa):
- `koineformer` r=16 α=32, 3.7M trainable / 220M, 14 MB, **CC-BY-SA-4.0**
  (the SA is inherited from MorphGNT, not chosen).
- `koine-t5`, `koine-t5-omni` — **CC-BY-NC-SA-4.0**. GreTa is apache-2.0, so
  the NC is *not* inherited from the backbone. Audit where it came from before
  assuming the firewall is immovable.
- All three are adapted on ~1.5M tokens of SBLGNT + Apostolic Fathers, i.e.
  **biblical literary Koine — a different register from documentary papyri.**

**Case handling differs by model — and an earlier version of this ledger got
it wrong.** It claimed case was destroyed family-wide, inferred from reading
vocabulary files. Tokenising actual text shows otherwise:

| | `Ἡλιοδώρου` vs `ἡλιοδώρου` | round-trip |
|---|---|---|
| **GreTa** | identical ids `[11655, 17067]` | lowercased — **case lost** |
| **GreBerta** | `[2213, 513, 50508]` vs `[1342, 513, 50508]` | `Ἡλιοδώρου` — **case kept** |

GreTa's tokenizer normalizer contains `{"type": "Lowercase"}`, so case is gone
before the model sees it. **GreBerta has no such normalizer and preserves case
fine** — ByteLevel BPE composes capitals from byte pieces, and an absent
uppercase *merge* is not an absent uppercase *representation*. `Γεώργιος` and
`γεωργός` tokenise to entirely different ids.

**Keeping case costs −0.59% tokens** over the corpus, i.e. it is *cheaper* as
well as more informative. 16.16% of corpus tokens are capitalised and in papyri
capitals mark proper names, so lowercasing throws away the strongest available
PERSON/PLACE cue for nothing. `pranaydeeps/Ancient-Greek-BERT` does state
"de-accentuating and lower-casing" outright (and declares no licence — unusable
for a released artifact), but that is a property of that model, not of the
field.

**Consequence:** the planned B2 arm ("does an explicit capitalisation feature
help?") is largely moot for GreBerta — the backbone already sees case. Reuse
that slot for something that is actually in question.

**Architecture evidence for the task (token classification, not generation):**
- Encoder-only beats encoder-decoder on NER by a wide margin: 84.7 vs 68.1 F1
  in-domain, 76.6 vs 58.9 out-of-domain (~15–17.7 points). Cause is
  architectural — MLM pretraining aligns with sequence labelling, and
  autoregressive decoding accumulates errors across tokens.
- The bowphs paper itself credits T5's decoder specifically for
  **lemmatization** — a generative task, which ours is not.

### DAPT method (verified)
- Gururangan et al., "Don't Stop Pretraining": DAPT gains **2–12 points**,
  largest when the target domain is *furthest* from the pretraining domain.
  Documentary papyri vs literary Classical/Medieval Greek is a large distance,
  so expect the upper half of that range. ~12,500 steps was their setting.
- **TAPT (task-adaptive pretraining) helps on top of DAPT** — cheap, do both.
- **Full fine-tuning, not LoRA, for DAPT.** "LoRA learns less and forgets
  less": LoRA's value is preserving source-domain ability, which is exactly
  what we do *not* need — literary Greek performance is not a deliverable.
  GreBerta is 0.1B, so full FT fits an A10 (24 GB) comfortably.
- Weak/silver supervision (Phase 6) carries **20–60% label noise** in the
  literature. Budget for noise-robust loss + filtering, not naive training.
- Joint span-based entity+relation extraction outperforms pipelines when well
  designed (pipelines suffer error propagation) — but a badly designed joint
  model underperforms a pipeline.

### Ablation plan (restructured 2026-07-20 on the evidence above)

| Arm | Backbone | DAPT | Licence | Role |
|---|---|---|---|---|
| **B0** | GreBerta | none | apache-2.0 | **Control.** Isolates what DAPT buys. |
| **B1** | GreBerta | papyri | apache-2.0 | **Primary. The released model.** |
| **B2** | GreBerta | papyri, seq_len 256 | apache-2.0 | Median papyrus is ~74 tokens; a 512-block packs ~7 unrelated documents. |
| **A1** | GreTa | papyri | apache-2.0 | Architecture control: encoder vs encoder-decoder. |
| **A3** | koine-t5-omni | — | **CC-BY-NC-SA** | Comparison only. **Never released.** |

B0 is a real arm, not a formality: if DAPT does not clear it, that is the
finding and there is no reason to ship a DAPT'd model. B1 vs A1 tests the
architecture claim on our own data rather than on the literature's.

### Context length (measured against this corpus)
- GreBerta's 512 tokens covers **~93%** of documents whole (median 267 chars,
  p90 1,228, p95 1,830; ~6.8% exceed ~512 tokens, 2.0% exceed ~1024).
  Sliding window with overlap handles the tail.
- koine-t5/omni's 256-token limit would truncate ~25% — another reason not to
  build on them.

### Modal API (verified at modal.com/docs — re-check before Phase 4)
- `modal.App` (`modal.Stub` is an error in ≥1.0). GPU string **`gpu="A10"`**,
  24 GB, `"A10:2"` for multi. **`"A10G"` is no longer in the documented GPU
  list** (T4, L4, A10, L40S, A100, H100, H200, B200, B300, RTX-PRO-6000) —
  use `"A10"`. `gpu=["H100", "A100-40GB:2"]` expresses ordered fallbacks.
- `modal.gpu.*` objects, `modal.Mount`/`mount=`, automounting of local modules:
  **all deprecated/removed** — add local source explicitly
  (`add_local_python_source`, `add_local_dir`).
- Volumes `from_name(create_if_missing=True)`, `volumes={...}`, `.commit()`;
  **background commits every few seconds plus a final snapshot on shutdown**
  are confirmed current. Pass `version=2` for v2 Volumes. Set the HF Trainer's
  `output_dir` inside the Volume and checkpointing is automatic.
- `@app.function(gpu=, volumes=, secrets=, timeout=, retries=, max_containers=,
  single_use_containers=)`; timeout max 86400; `concurrency_limit`→`max_containers`.
- Preemption-resilient pattern: Volume checkpoints + `retries=` +
  `single_use_containers=True` + resume-from-last-checkpoint.

---

## 8. Progress

**~60% of the full project.** Phases 0–3 complete; **Phase 4 DAPT RUN — full FT
wins, `full/final` (B1) saved**; **Phase 5 — 115 gold docs, ALL human_validated,
2,995 entities, 0 errors, all byte-identical to corpus; AGE un-starved 6→133**;
**Phase 6 silver emitted over the train split** (1.11M entities
/ 328k relations); **Phase 7 entity NER RUN — DAPT beats the no-DAPT control
+9.5 strict F1** (b1 0.589 vs b0 0.495; PERSON +19, PLACE +11); **Phase 7b
two-stage RUN — settled recipe DAPT + silver(CE) + gold-FT; on the 115-doc
all-human gold strict 0.710 / relaxed 0.811, AGE 0.0→0.947** (GCE rejected −5.7).
Foundation:
a validated corpus-ingestion pipeline built over all
67,980 documents at parse rate 1.000, whole-corpus characterization, mined
lexicons with measured recall, the annotation schema (guidelines v0.3, ten
rules), a mechanical span + **numeral-coverage** validator (`oik gold check`),
a proximity baseline at a 74.50% numeral link rate, leak-free stratified +
chronological splits, and a scored, confidence-aware silver labeler.

**Phase 5c IN PROGRESS — payment direction (`PAID_BY`/`PAID_TO`)**, a
deliverable-driven prelude to Phase 8: the silver direction engine is built +
tested (green), and the gold direction draft is 46/64 reviewed (47 edges) in
`data/gold/direction_draft.jsonl`, awaiting owner validation (§6, §9).

Remaining: **finish Phase 5c** (validate draft + 18 unread/17 flagged docs →
merge → re-score) · **Phase 8 relation model** (the big build, on the
direction-augmented schema) · Phase 9 corpus inference → DB · Phase 10 historical
analysis · Phase 11 release. Entity-side gold is in strong shape (115
human-validated docs, 0 errors).

**The entity model is validated: strict 0.710 / relaxed 0.811 on the 115-doc
all-human gold, with gold fine-tune the proven lever (+0.136).** AGE is solved
(0.947) and every gold doc is human_validated. The remaining *entity-side*
ceiling is **TAX_TERM (0.44, flat) and PERSON_ROLE (0.40, still regresses under
gold fine-tune)** — these do NOT respond to more volume (proven: doubling them
did nothing); they need cleaner/more-consistent labels or a different lever.
**Phase 8 (relations) is the next scientific risk** (silver PARTY_OF precision
≈ 0.28).

---

## 9. Current machine state (read this first in a new session)

_Last updated: 2026-07-23 (**Phase 5c — payment direction VALIDATED + MERGED
into the gold**). Owner gave the scope call (leases/sales/in-kind all count) and
authorised the merge. This session rejected an external (Gemini) case-rule review
of the draft, re-derived the payment-doc set over all 89 money/commodity gold
docs (prior triage lost with its deleted builder), annotated 20 new payment docs,
and **merged 87 `PAID_BY`/`PAID_TO` edges across 38 docs into
`annotated.jsonl`** (relations 623→710, `oik gold check` 0 errors). Did NOT train
anything. Gold entities are unchanged; only relations were added.

**Gold direction — DONE (this session):**
- `annotated.jsonl` now carries **38 direction docs / 87 `PAID_BY`/`PAID_TO`
  edges** (18 original draft + 20 new). All pass the signature check;
  `oik gold check` 0 errors, `numerals_checked`, relations **710**.
- `data/gold/direction_draft.jsonl` = the auditable record of what was merged
  (38 docs, `head_text`/`tail_text` synced to gold; the 4 Gemini-flagged
  truncations fixed — indices were always correct).
- 20 new docs: `3141 5414 7797 15362 15454 15887 16396 16690 22840 36928 36941
  38767 40966 41308 75749 76915 77107 78637 144620 702571`. ~50 other
  money/commodity gold docs were read and judged genuine no-direction.
- The `PAID_CONFIDENCE` priors in `patterns.yaml` are still **PROVISIONAL** —
  measure them with `oik silver score` now that gold direction exists.

**Silver direction engine (built the prior session, unchanged, green):**
- Verb-anchored `PAID_BY`/`PAID_TO` in `SilverLabeler._direction_relations`
  (verb map mined whole-corpus: receiver verbs → subject=payee, παρά=payer;
  giver verbs → subject=payer, dative=payee; τέτακται impersonal). Patterns in
  `resources/silver/patterns.yaml` (`payment_*_stems`, `dative_endings`,
  `official_stems`). Precision filter: an amount must sit near the verb.
- **4 systematic bugs fixed** (see §6 Phase 5c): `ὁ/τοῦ παρὰ X` agent-of,
  παρών≠παρά, giver-dative-is-payee, `παρὰ τοῦ X` payer.
- Guidelines **v0.4** (§5 payment-direction rule). 10 hand-computed tests.
- Coverage: ~6,460 silver direction edges over the 49k train docs.

**Prior state (still current, unchanged this session):** Phase 4 DAPT full FT
wins → `checkpoints/full/final` = B1; Phase 7 entity NER DAPT beats control +9.5
strict F1, `models/{b0,b1}/final` on `oikonomia-ner` Volume; Phase 7b two-stage
silver→gold strict 0.710 / relaxed 0.811, AGE 0.947. `annotated.jsonl` = 115
docs, all human_validated, 0 errors, byte-identical; now +87 direction relations._

**Built (green — ruff, mypy 61 files, 409 tests, caches cleared):**
- Verb-anchored `PAID_BY`/`PAID_TO` in `SilverLabeler._direction_relations`
  (verb map mined whole-corpus: receiver verbs → subject=payee, παρά=payer;
  giver verbs → subject=payer, dative=payee; τέτακται impersonal). Patterns in
  `resources/silver/patterns.yaml` (`payment_*_stems`, `dative_endings`,
  `official_stems`). Precision filter: an amount must sit near the verb.
- **4 systematic bugs fixed** (see §6 Phase 5c): `ὁ/τοῦ παρὰ X` agent-of,
  παρών≠παρά, giver-dative-is-payee, `παρὰ τοῦ X` payer.
- Guidelines **v0.4** (§5 payment-direction rule). 10 hand-computed tests.
- Coverage: ~6,460 direction edges over the 49k train docs (`PAID_CONFIDENCE`
  values are PROVISIONAL until measured on gold).

**Gold direction DRAFT (owner-validation pending):**
`data/gold/direction_draft.jsonl` (git-tracked, **separate** from the untouched
human-validated `annotated.jsonl`). **46 of 64 payment docs reviewed** — 18 docs
/ **47 signature-checked edges** (0 errors), 11 confident-none, 17 flagged for
review. The hand pass corrected real auto-labeler errors (matronymics read as
subject, pronoun payers, direction flips) — it is load-bearing.

**Prior state (still current, unchanged this session):** Phase 4 DAPT full FT
wins → `checkpoints/full/final` = B1; Phase 7 entity NER DAPT beats control +9.5
strict F1, `models/{b0,b1}/final` on `oikonomia-ner` Volume; Phase 7b two-stage
silver→gold strict 0.710 / relaxed 0.811, AGE 0.947. `annotated.jsonl` = 115
docs, all human_validated, 0 errors, byte-identical.)._

### Modal Volumes (state that lives off-repo)
- `oikonomia-dapt`: `shards/{train,dev}.bin`, `checkpoints/full/final` (**B1
  backbone**, load this for Phase 7 b1), plus stale `checkpoints/b1-*` from the
  first (misconfigured) sweep — safe to `modal volume rm -r` to reclaim space.
- `oikonomia-ner`: `data/{silver,gold,labels}.json*`. **The Volume now holds the
  115-doc all-human gold** — pushed this session before the successful `xval`
  run (strict 0.710 / relaxed 0.811, AGE 0.947). Re-`push` only if
  `annotated.jsonl` / `silver.jsonl` / `labels.json` change again.
  `xval` trains in `/tmp` per fold and saves no persistent model (it measures,
  it doesn't ship a model) — the shippable NER model is a later `launch`-style
  full train once the recipe/gold are frozen.
- Run `modal_app/ner.py` with the **venv's** modal (imports `oikonomia`); the
  DAPT one runs with global modal (ships nothing local).

### Quality gate at last save
**Green: ruff (src tests modal_app) · mypy (61 files) · 406 tests · caches
cleared.** `oik gold check` **0 errors** after the direction merge
(`numerals_checked`, relations 710). Committed this session on a branch (the
prior session's engine work + this session's validation/merge together).
`git status` before commit:
- `M data/gold/annotated.jsonl` (**merged 87 `PAID_*` direction relations**)
- `?? → tracked data/gold/direction_draft.jsonl` (38-doc auditable record)
- `M src/oikonomia/labeling/silver.py` (the direction labeler + 4 fixes)
- `M resources/silver/patterns.yaml` (payment verb map)
- `M resources/schema/annotation_guidelines.md` (v0.4)
- `M tests/test_silver_labeler.py` (10 direction tests)
- `M CLAUDE.md`

Prior committed state (HEAD `0e06588`): 115-doc gold, all human_validated, no
direction relations.

### Gold annotation (115 docs — ALL human_validated)
- **Now 115 docs, `oik gold check` 0 errors, numerals_checked, byte-identical,
  all `human_validated` / `reviewed_by: abderahmane-ai`.** This session's 20
  drafts were owner-reviewed and flipped from `model_draft`:
  - 13 hard-batch docs: `77576 78637 77107 75749 79378 702571 793 5344 7560 5414
    703351 76201 43027`
  - 7 AGE-targeted docs: `25173 26167 27453 11440 29529 12351 12906`
- **The `oikonomia-ner` Volume now has this 115-doc gold** (pushed + `xval` run
  this session → strict 0.710 / relaxed 0.811, AGE 0.0→0.947). Re-`push` only
  after further gold edits.
- **The owner's 10 hard docs** (now `human_validated`): `35281 36847 40966 41308
  47246 7797 78653 79380 38767 76915`. Three (`7797 40966 41308`) needed a
  text-corruption fix this session (§7) — do not re-import their text from
  `hard_data_batch.jsonl`, it is normalized-away-from-corpus.
- **Do NOT run `tools/build_gold_draft.py`** — it `write_text`-overwrites the
  whole file from its 85-doc SPEC and would drop the owner's 10 + this session's
  20 (none is in the SPEC). Append new rows instead (compute offsets by
  forward-scanning surface strings against `corpus.parquet` text).
- **AGE un-starved: 9 → 133** (now `human_validated`). Seven train-split
  census/signalement docs annotated this session (`25173 26167 27453 11440 29529
  12351 12906`). `scratchpad/find_age_docs2.py` regenerates the ranked
  candidate list (~900 more age-docs + huge 100–220-age poll-tax registers) if
  further AGE is ever wanted; `scratchpad/age_build.py` auto-generates AGE spans
  from the corpus `<num>` offsets for clean "every-numeral-is-an-age" lists.
- **8 docs still HELD** (too dense/fragmentary to auto-draft; `35281` was one but
  the owner has since annotated it): `23914` (marriage, double-annotate),
  `25467` `27734` `28329` `31975` `33510` (obol/grain/harbour registers,
  40–80 numerals each), `37263` (shattered λόγος). Careful/human annotation.
- **Resume for more:** next undone tractable ids after 36941: `37277, 37409,
  37678, 382560, 38625, 38767, …`. Regenerate the list with the §10 one-liner.
- **Workflow that worked well:** dump 5 docs at a time with the scratchpad
  helper (text + tagged `<num>` offsets + baseline suggestions), write each
  `SPEC["<id>"]` block in `tools/build_gold_draft.py`, rebuild, `oik gold check`.
  Recurring builder gotchas: (a) list entities in **reading order** (surface
  is found by forward scan from the previous span's end — CURRENCY before its
  MONEY_AMOUNT, `βοηθὸς` before `Ἀλεξάνδρου`); (b) single-char numeral surfaces
  (`δ`,`η`,`ι`,`ρ`) match inside words like `δηναρίων` — anchor them with a
  two-token context (`"ρλγ δ"`, `"δ η ιϛ"`); (c) contexts are literal, no regex.
- **Advisory residue is expected and justified:** theonyms (`Ἰησοῦ Χριστοῦ`),
  fused obol-words (`διώβολον`, `τετρώβολον`), elided-denomination sums, bare
  counts, and damaged name-fragments. Drive the *real* misses to zero; leave
  those, per guidelines §5.

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
- `data/processed/corpus.parquet` — **293 MB**, 67,980 rows, built at
  `build_corpus` stage version **4** (honours `<lb break="no"/>`; canonical
  whitespace with all spans remapped).
- `data/processed/ingest_failures.json` — now an empty failure list.
- `data/.manifests/build_corpus.json`.
- `data/interim/numeral_context*.csv` — mined candidate vocabulary
  (17,540 tokens at `--min-docs 2`). Regenerate with `oik lexicon mine`.
- `data/processed/splits.parquet` + `splits_report.json` — `build_splits`
  stage version **3**. 61,249 rows, both regimes in one table
  (`split_random`, `split_chronological`). Rebuilt post-parser-fix: 475
  duplicate clusters, 59,581 groups.
- `data/processed/dapt/{train,dev}.bin` + `.json` — packed uint16 token
  shards, stage version **3**: case preserved, blocks framed `<s>…</s>`.
  16,109 train blocks (8.25M tokens) + 2,146 dev (1.10M). **No test shard, by
  design.**
- `data/processed/silver.jsonl` — **146 MB**, Phase 6 silver over the train
  split (48,941 docs, 1.11M entities, 328k relations, `confidence` per span,
  `provenance: silver`). Regenerate with `oik silver label` (~5 min); needs
  `silver_label_dist.json`. Gold docs excluded (they get reviewed labels).
- `data/processed/silver_label_dist.json` — corpus surface-form → label
  distribution (9,517 forms) from `oik silver distmap --sample 20000`; drives
  the place gazetteer and the confidence signal.

**All three were rebuilt this session** after the parser fixes. Splits and DAPT
shards came out **byte-identical** to their pre-canonicalisation versions —
expected, and a useful confirmation, since both already collapsed whitespace
themselves. Only the stored text, its spans, and the gold batch changed.
Downstream stages now invalidate correctly on their own via `upstream_key`.

**`transformers` 5.14 was installed into the venv** (tokenizers only, no
torch) to verify the packing pipeline against the real GreBerta tokenizer
rather than a mock. Tests do not depend on it — they use a fake tokenizer — so
the suite still runs on a clean checkout.

Disk: watch headroom — corpus 6.1 GB + processed 280 MB.

### Gold annotation state (git-TRACKED, not derived)
- `data/gold/annotated.jsonl` — **115 documents, ALL `human_validated`**,
  **2,995 entities / 623 relations**, `oik gold check` 0 errors,
  `numerals_checked`, every text byte-identical to `corpus.parquet`. Built from
  three sources: the original 85 (`tools/build_gold_draft.py` SPEC), the owner's
  10 hard docs, and this session's 20 (13 hard + 7 AGE). **Do NOT regenerate the
  whole file** (§9 "Gold annotation" note) — append only.
- `data/gold/{to_annotate,hard_data_batch,batch_2}.jsonl` — the source batches
  gold docs were drawn from. **Their `text` is suspect** — some carries
  normalized-away-from-corpus text (§7); always source gold text from
  `corpus.parquet`, never these files.
- `tools/build_gold_draft.py` — the spec for the ORIGINAL 85 only; entities are
  surface strings in reading order (offsets computed, off-by-one impossible).
  The appenders for the +30 docs lived in the scratchpad and are gone; the
  artifacts are the JSONL rows themselves.
- `resources/schema/annotation_guidelines.md` — **v0.3**, the single authority
  (§0 ten rules, §5 all decisions incl. the "completeness pass" block, §6 batch
  format with `skipped_numerals`). `ANNOTATION.md` was deleted; do not recreate.
- `src/oikonomia/gold/validate.py` + `oik gold check [--fix]` — the mechanical
  validator. It now cross-references corpus `<num>` tags (numeral-coverage gate,
  a hard failure) and prints name/relation advisories. Run after any edit to
  `annotated.jsonl`. Needs `data/processed/corpus.parquet` for the numeral gate;
  without it, that gate is skipped (offset/relation checks still run).

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

# 1. Green before changing anything
.venv/bin/ruff check src tests modal_app && .venv/bin/python -m mypy src && .venv/bin/python -m pytest

# 2. Artifacts intact? Rebuild if missing:
#    oik ingest build (~85s) -> oik splits build (~25s) -> oik dapt prepare (~20s)
.venv/bin/oik splits check
.venv/bin/oik dapt inspect | tail -15

# 3. Gold intact? (115 docs, ALL human_validated, 0 errors + numerals_checked)
.venv/bin/oik gold check

# 3b. Phase 6 silver intact? (re-emit if silver.jsonl missing)
.venv/bin/oik silver score                  # entity micro F1 ~0.60 exact / ~0.72 relaxed
#   oik silver distmap --sample 20000  ->  oik silver label   (rebuilds silver.jsonl, ~5 min)

# 3c. Re-run the entity xval any time (Volume already has the 115-doc gold):
#   .venv/bin/modal run --detach modal_app/ner.py::xval --backbone b1 --loss ce
#   (re-`push` first only if annotated.jsonl/silver.jsonl/labels.json changed)

# 3d. Phase 5c (IN PROGRESS) — payment direction PAID_BY/PAID_TO.
#   The silver engine is built+green; the gold draft awaits owner validation:
head -5 data/gold/direction_draft.jsonl        # 18 docs / 47 hand-verified edges
#   Smoke-test the labeler on real docs (scratchpad helper is gone; regenerate):
#     builds candidates over gold's own entities via SilverLabeler._direction_relations
#   Remaining: validate the 47 edges + finish 18 unread + 17 flagged docs (§6/§9),
#   then MERGE validated edges into annotated.jsonl (append to each doc's
#   "relations" — do NOT regenerate the file), re-push, oik silver score.

# 4. (Optional) more gold candidates: AGE-dense train docs, or undone to_annotate
.venv/bin/python /path/to/scratchpad/find_age_docs2.py   # ranked AGE candidates (regen if lost)
```

**Where the project stands.** Phases 0–7b are done and *measured*: the entity
model is validated at **strict 0.710 / relaxed 0.811** (DAPT + silver-CE +
gold-FT, 5-fold CV on the 115-doc all-human gold), AGE solved (0.947). Gold is
115 docs, all `human_validated`, 0 errors. **Nothing here is blocked on more
gold volume.**

**The immediate next move: FINISH PHASE 5c (payment direction).** This session
built the silver direction engine (green) and drafted 46/64 gold payment docs
into `data/gold/direction_draft.jsonl` (47 signature-checked `PAID_BY`/`PAID_TO`
edges + 11 confident-none + 17 flagged). To finish:
1. **Owner validates** the 47 draft edges and the 11 "none" calls.
2. **Scope call** (owner's, blocks the 17 flagged): does direction cover leases
   (future rent), sales (buyer→seller money), and in-kind distribution lists —
   or only completed money/goods receipts? Decide, then annotate the flagged +
   the 18 unread docs.
3. **Merge** validated edges into `annotated.jsonl` (append per-doc, never
   regenerate), re-`push`, `oik silver score` → real per-direction precision →
   update the PROVISIONAL `PAID_CONFIDENCE`, tune recall.
Then Phase 8 trains on the direction-augmented schema. `git status` this session
is uncommitted on `main` — branch + commit the engine+draft when ready (§9).

**After Phase 5c, the two moves for Phase 8 / entity polish:**

1. **Phase 8 — relation model.** The next big build and the scientific risk:
   silver PARTY_OF precision ≈ 0.28. The gold already carries 623 relations
   (PARTY_OF, HAS_*, DATED_TO, CHARGED_UNDER) — now plus direction — as the
   eval/fine-tune anchor. This is the largest remaining piece of the pipeline.

2. **Entity-model polish — the stubborn classes.** TAX_TERM (0.44, flat) and
   PERSON_ROLE (0.40, *regresses* under gold-FT) are the entity ceiling and do
   **not** respond to more volume (proven: doubling them moved nothing). The
   lever is label *consistency*, not count — audit the PERSON_ROLE spans across
   the gold for inconsistency (guardian formulas vs statuses vs unnamed roles
   all share one label), consider splitting the label, then re-run `xval`.
   Optional cheap test first: `xval --backbone b1 --loss ce --min-confidence 0.5`
   (hard-drop the noisy silver tail).

**If more gold is ever wanted** (not required): `scratchpad/find_age_docs2.py`
lists ~900 more train AGE-docs; the appender pattern is `scratchpad/age_build.py`
(auto-AGE from `<num>` offsets for pure age-lists) + `append_gold.py`-style
surface specs for mixed docs. **Always** source text from `corpus.parquet`, run
`oik gold check` (0 errors + honest advisories), and check byte-identity.
8 dense docs remain held (§9): `23914 25467 27734 28329 31975 33510 37263`.

**Before touching Modal:** re-verify its API against `modal.com/docs` (§7). Run
`modal_app/ner.py` with the **venv's** modal (it imports `oikonomia`).

**Reminder:** commit after each green unit of work (this session's work is
uncommitted — see §9 "Quality gate"), and update §6/§8/§9 before ending a session.
