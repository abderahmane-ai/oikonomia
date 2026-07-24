# CLAUDE.md — OIKONOMIA

Agent instructions and live project state. This file is the only thing loaded
into a new session's context, so keep it **lean and current**. Detail that is
not needed to continue work lives elsewhere:

- **Phase history** → [`docs/phases/*.md`](docs/phases) (one file per phase).
- **Load-bearing facts** ("never re-derive") → [`docs/fact-ledger.md`](docs/fact-ledger.md).
- **Architecture detail** → [`docs/architecture.md`](docs/architecture.md).
- **Database schema / data dictionary** (deliverable #2) → [`docs/database.md`](docs/database.md).
- **Phase-8 plan of record (lean/descoped)** →
  [`docs/phases/phase_8_relation_model.md`](docs/phases/phase_8_relation_model.md).
  The original maximal OIKONOMIA-RE plan (now descoped) is archived at
  `~/.claude/plans/fizzy-wondering-eich.md`.

**Update §5–§7 of this file at the end of every phase or coherent unit of work.**
Do not let ancient logs accumulate here — archive them into `docs/phases/`.

---

## 1. What this project is

**OIKONOMIA** turns the ~68,000 ancient Greek documentary papyri of Greco-Roman
Egypt (tax receipts, leases, loans, wages, census returns, private letters) into
a structured, auditable database of everyday economic life, and trains open Greek
models to read them. It is the first attempt to automate the information
extraction economic historians now do by hand. Three deliverables:

1. **Open models** — a papyri-adapted Greek model family (entity + relation
   extraction), released on Hugging Face.
2. **A derived database** — every extracted transaction traceable to a character
   span in a specific document at a specific corpus revision.
3. **Historical findings** — price/wage series across a millennium, women as
   contract principals, ancient credit.

**Corpus:** Duke Databank of Documentary Papyri (DDbDP) + HGV metadata, via
[`papyri/idp.data`](https://github.com/papyri/idp.data), **CC BY 3.0**.
**Venue:** ML4AL / LT4HALA or DSH journal. No fixed deadline — build it properly.

---

## 2. Working rules (non-negotiable)

- **Aim for the best, never for green.** Do not build something just to make a test
  pass, hit a number, or mark a task done. Always use the best approach available —
  and here that means: if a trained model beats rules on the task (people, places,
  who-is-a-party), **use the model**, don't reach for a cheap rule-based stand-in
  because it finishes on the laptop. **Rough approximations may be used to *validate*
  an idea, but never *delivered* as the result.** Validate with slop, ship the best.
- **Never guess. Validate before implementing.** Every load-bearing fact (path
  conventions, XML structure, API syntax, licences) is checked against the live
  source, not recalled, and recorded in [`docs/fact-ledger.md`](docs/fact-ledger.md).
  **Modal syntax is always re-checked against `modal.com/docs`** — never from memory.
- **Tests are progressive and extensive**, shipped in the same change as the code.
  Prefer hand-crafted fixtures with hand-computed expected output over smoke tests
  for anything with subtle semantics (the EpiDoc parser especially).
- **Quality gate, in this order, after ANY unit of work:** ruff → mypy → pytest →
  `make clean`. Never leave or commit caches (`__pycache__`, `.pytest_cache`,
  `.mypy_cache`, `.ruff_cache`, `*.pyc`). See §4.
- **Phase discipline.** Before starting the next phase, write a clean summary of
  the finished one into `docs/phases/` and update §5–§7 here. Do not roll forward
  silently.
- **"Save state" means update THIS FILE** (§5–§7) plus the relevant `docs/phases/`
  file. Every pause starts a *new session*; `CLAUDE.md` + `docs/` are all that
  carry over. Never park a handoff in a scratchpad or plan file only.
- **Commit whenever a unit of work is green** (ruff + mypy + pytest), so nothing
  is lost to an interrupted session. Branch first if being on `main` was not intended.
- **Hardware:** training runs on **Modal, single A10 (24 GB)**. Do heavy
  preprocessing offline into the processed corpus; feed the GPU tokenised,
  memory-mapped, packed data; prefer bf16 and sensible batch sizes. **The library
  must stay importable and testable on a laptop with no GPU/Modal dependency.**
- **Data separation is structural** (§3). Raw data is immutable and gitignored;
  only `data/gold/` and `data/.manifests/` are tracked.
- **Licence firewall.** Never build a *releasable* artifact on a NonCommercial
  ancestor (`koine-t5`, `koine-t5-omni` are CC-BY-NC-SA). See `MODEL_LICENSES.md`.

---

## 3. Architecture (boundaries that must hold)

Four hard boundaries, enforced by directory layout and import direction:

1. `src/oikonomia/` — pure-Python library. **No Modal imports, no GPU deps.**
2. `modal_app/` — thin Modal orchestration. Imports the library, never the
   reverse. Deleting it must not break the library.
3. `data/` — tiered by mutability: `raw/` (immutable, gitignored) → `interim/`,
   `processed/` (gitignored, re-derivable) → `gold/`, `.manifests/` (tracked).
4. `resources/` — curated knowledge (lexicons, genre map, prompts), reviewed as
   source code because model behaviour depends on it.

Config is layered YAML (`configs/base.yaml` → `paths.<env>.yaml` → dotted
overrides → `OIK_*` env). No module constructs a data-path literal; all paths
come from `settings.paths.*`, so the same code runs locally and on Modal.

The pipeline is a set of **deterministic, resumable stages** (`pipeline/`). Each
stage writes a manifest (`data/.manifests/<stage>.json`) with its input
fingerprint, a params hash, and output sha256s. Freshness =
`version + inputs_key + params`. **`inputs_key` must name what the stage actually
reads**: stages reading the raw corpus fingerprint it with the pinned git rev;
stages reading another stage's output use `pipeline.manifest.upstream_key(...)`
(hashes the upstream manifest's output sha256s). Keying a downstream stage on the
corpus rev is a silent staleness bug. **Bump a stage's `version` when you change
its logic** (or run `--force` while iterating). Full detail:
[`docs/architecture.md`](docs/architecture.md).

---

## 4. Commands

```bash
# --- Setup ---
uv venv --python 3.12
uv pip install -e ".[dev]"        # library + dev tools (no GPU stack)
# Modal extras (.[modal], .[train]) only when a Modal phase begins.

# --- Quality gate — run after ANY unit of work, in this order ---
.venv/bin/ruff check src tests modal_app     # must be: All checks passed!
.venv/bin/python -m mypy src                 # must be: Success: no issues found
.venv/bin/python -m pytest                   # all green (-m "not corpus" while iterating)
make clean                                    # always clear caches afterwards

# --- Core pipeline (each stage is deterministic + resumable) ---
uv run oik ingest sync   --set ingest.idp_git_rev=<sha>  # pinned-rev checkout
uv run oik ingest build                       # → processed/corpus.parquet (~85s)
uv run oik corpus stats                       # recompute the fact-ledger numbers (~7s)
uv run oik splits build                       # dedup + assign (~25s); splits check / report
uv run oik dapt prepare                       # pack train/dev shards (needs .[train] tokenizer)

# --- Gold (data/gold/, tracked) ---
uv run oik gold check                         # span/relation/numeral-coverage validator (--fix repairs offsets)

# --- Silver (Phase 6) ---
uv run oik silver score                       # score the labeler vs gold, per label
uv run oik silver distmap --sample 20000      # corpus label distribution → gazetteer/confidence
uv run oik silver label                       # emit silver over train (~5 min); needs the distmap

# --- Entity NER (Phase 7) — run with the VENV's modal (container imports oikonomia) ---
.venv/bin/oik ner prepare                                          # freeze BIO schema from silver
.venv/bin/modal run --detach modal_app/ner.py::push               # upload silver/gold/labels (prints a fingerprint)
.venv/bin/modal run --detach modal_app/ner.py::xval --backbone b1 --loss ce   # paired 5-fold CV

# --- Model release (Phase 11) — deliverable #1; OWNER-RUN (needs HF write token) ---
.venv/bin/modal run --detach modal_app/ner.py::launch          # all-gold train + save → models/release/final
modal secret create huggingface HF_TOKEN=hf_xxx                # once
.venv/bin/modal run modal_app/ner.py::push_to_hub --repo-id <org>/oikonomia-ner  # push (starts private)

# --- Relations (Phase 8) — FROZEN; GPU runs owner-triggered, not the default path ---
.venv/bin/oik relation prepare                # freeze relation_labels.json; recall guard MUST be 0 uncovered
.venv/bin/oik relation score                  # nearest-pair baseline (the bar): rel micro F1 0.443

# --- Database (Phase 9) — the ACTIVE deliverable; deterministic, laptop, no GPU ---
.venv/bin/oik db build --sample 0             # whole corpus (~minutes) → data/processed/db/monetary.parquet
.venv/bin/oik db prices                       # clean price series (median [IQR] n) → db/prices.parquet
.venv/bin/oik db taxes                        # fiscal-regime map + poll tax by century/region → db/taxes.parquet
.venv/bin/oik db persons                      # gender+guardian over the MODEL's 350k PERSON spans → db/persons.parquet
.venv/bin/oik db autonomy                     # χωρὶς-vs-μετὰ-κύριου curve by century/region → db/autonomy.parquet
.venv/bin/oik db principals                   # women as principals by DEAL TYPE (reads re_corpus.jsonl + persons.parquet) → db/principals.parquet
.venv/bin/oik db export                        # package the queryable DB: documents spine + distinct persons + manifest → db/export/
.venv/bin/oik db validate-women               # validate the women pipeline (steps 3-5) vs the 115-doc gold
.venv/bin/oik db women --source gold          # OLD rule-based principals (superseded by `oik db principals`)
```

Database schema + data dictionary: [`docs/database.md`](docs/database.md).

Explicit cache-clear (if `make clean` is unavailable). **Never use `find -delete`
here** — it implies `-depth`, which disables `-prune` and walks into `.venv`:

```bash
find . -path ./.venv -prune -o -type d \
  \( -name "__pycache__" -o -name ".pytest_cache" \
     -o -name ".ruff_cache" -o -name ".mypy_cache" \) -exec rm -rf {} + 2>/dev/null || true
find . -path ./.venv -prune -o -name "*.pyc" -exec rm -f {} + 2>/dev/null || true
```

---

## 5. Where the project stands

**PIVOTED (2026-07-23): models frozen at a publishable bar; now building the
database (Phase 9) — deliverable #2/#3 — driven by a concrete finding.** The
objective (§1) is a queryable, auditable database of economic life + the historical
findings it enables. After 8 phases the *reading* was solid but **zero database
rows existed and zero historical questions were answered**; the relation-F1 grind
(esp. 8a direction) was polishing scaffolding. So: freeze the models, build the DB.
Full rationale + first result: [`docs/phases/phase_9_database.md`](docs/phases/phase_9_database.md).

**LATEST (2026-07-24) — the WOMEN FRONT IS COMPLETE (all 8 steps).** Two findings
on the trained models. **(A) Autonomy** (steps 1–6): trained-model NER over all
61,249 docs (1.37M entities), person-blob split (129k father links), gender +
typed guardian → **women's χωρὶς-κυρίου (autonomous) share rises 0% (≤1c AD) → 39%
(3c) → 80% (4c AD)** — *ius liberorum* / decline of tutela mulierum, unsupervised,
gold-validated. **(B) Principals by deal type** (steps 7–8): saved the RE model
(end-to-end PARTY_OF 0.623), ran it over the corpus (16,315 PARTY_OF), joined to
the gendered persons → **21,895 principals, women's share 18.0%, deal-type gradient
sale 30% / loan 28% (property) vs receipt/delivery 5–10% (fiscal paperwork)**;
guardian split 92/8 matches step 4; 65% carry a patronymic. **Five findings now
exist** (prices, taxes, autonomy, principals-by-deal-type, + the monetization
transition). **Next: Phase 10 write-up** (details in §7).

**The models are DONE, not abandoned (deliverable #1, publishable):**
- Entity NER: DAPT **B1** (GreBerta full-FT) → silver-pretrain → gold-FT →
  **strict F1 0.737 / relaxed 0.837** (5-fold CV, 115-doc gold). Ceiling is
  TAX_TERM/PERSON_ROLE *label consistency*, not data.
- Relation RE: span-pair (SpERT) + B1 + silver→gold → **0.713 oracle**. Strong on
  adjacency (HAS_UNIT/CURRENCY 0.87–0.88) + PARTY_OF (0.65); direction is
  data-bound and parked (PAID_BY 0.15). **Freeze; revisit only if a finding needs
  more.** Diagnosis of the direction ceiling: [`docs/phases/phase_8_relation_model.md`].

**Phase 9 — the full-corpus database exists and the numbers are real.** `oik db
build --sample 0` over all 61,249 text docs → **195,906 monetary facts, 99%
normalized, 100% provenance** (every row → tm_id + char span), silver 140k / gold
54.8k kept separate. Two validation views recover known history: **2c AD wheat ≈
12 dr/artaba** (lit. ~7–8) and the **silver→gold monetization transition**
(textbook Egyptian coinage history, unsupervised). The profile surfaced **two
ready findings in the same table**: **7,725 commodity prices** (wheat/wine/oil/
barley span 8–9 centuries) and **6,623 tax payments** (named: demosia 9 centuries,
laographia poll tax 574, phoros, prosdiagraphomena) — taxes are *cleaner* (no
per-unit division). Bottleneck is extraction precision + the per-unit math, **not**
entity F1.

**The decisive enabler (audited, don't re-derive):** `corpus.parquet` already
carries `tm_id` (100%), `date_lo/hi` (95–98%, HGV), `place_pleiades/tm` (74–76%,
authority-linked), `canonical_genres` (100%), and EpiDoc-**decoded `<num>` values**.
So dates/places/numerals are *given* — the DB layer normalizes + assembles, it does
not re-extract them, and the weak `DATED_TO`/PLACE relations are bypassed.

**8b (relation coverage) — HAS_OCCUPATION + HAS_AGE apposition rules landed**
(gold coverage 35.7%→49.6%); the attribute draft (`data/gold/attribute_draft.jsonl`)
awaits owner review. This is *relation* work, now secondary to the DB; merge it
opportunistically, not as the critical path.

**Assets in hand:** validated ingestion over all 67,980 docs (parse rate 1.000)
with HGV date/place/genre + decoded numerals as parquet columns; mined lexicons
with canonical ids (currency/commodity/unit) that make DB normalization free;
DAPT B1 backbone; frozen entity + relation models; 115-doc all-human gold; the
deterministic silver labeler (doubles as the DB's extraction engine).

---

## 6. Phase status

Full write-ups: [`docs/phases/`](docs/phases). Headline result per phase:

| Phase | Status | Headline | Doc |
|---|---|---|---|
| 0 Foundation | ✅ | src-layout, layered config, deterministic pipeline, tooling | [phase_0](docs/phases/phase_0_foundation.md) |
| 1 Ingestion | ✅ | dual-view EpiDoc parser; 67,980 docs, parse rate **1.000** | [phase_1](docs/phases/phase_1_ingestion.md) |
| 2 Characterization & schema | ✅ | mined lexicons (88 entries/336 forms, 0 unattested); baseline 74.5% numeral link | [phase_2](docs/phases/phase_2_characterization_schema.md) |
| 3 Splits | ✅ | leak-free stratified + chronological; 475 dup clusters (2.89%) removed | [phase_3](docs/phases/phase_3_splits.md) |
| 4 DAPT | ✅ | **full-FT wins** (dev ppl 4.54); `checkpoints/full/final` = **B1** | [phase_4](docs/phases/phase_4_dapt.md) |
| 5 Gold annotation | ✅ | **115 docs, all human_validated**, 2,995 ent / 710 rel, 0 errors | [phase_5](docs/phases/phase_5_gold_annotation.md) |
| 5c Payment direction | ✅ | 87 PAID_BY/PAID_TO edges merged (verb-class rule, not case) | [phase_5](docs/phases/phase_5_gold_annotation.md) |
| 6 Silver labeling | ✅ | Silver-v2 labeler micro F1 0.585→**0.667**; emitted over 48.9k train docs | [phase_6](docs/phases/phase_6_silver_labeling.md) |
| 7 Entity NER | ✅ | **DAPT beats no-DAPT control +9.5 strict F1** (PERSON +19, PLACE +11) | [phase_7](docs/phases/phase_7_entity_ner.md) |
| 7b Two-stage silver→gold | ✅ | gold-FT recipe → **strict 0.737 / relaxed 0.837**; GCE rejected (−5.7) | [phase_7](docs/phases/phase_7_entity_ner.md) |
| 8 Relation model | ✅ FROZEN | span-pair RE **0.713** (oracle); saved + **end-to-end measured** (PARTY_OF oracle 0.705 → e2e 0.623); 8a data-bound; 8b apposition rules (+14 pts coverage) | [phase_8](docs/phases/phase_8_relation_model.md) |
| 9 Corpus→DB | ✅ (opt. hardening left) | **195,906 facts**; 5 findings — **prices**, **taxes**, **AUTONOMY** χωρὶς curve **0%→39%→80% (3c→4c AD)**, **PRINCIPALS by deal type** (21,895; women 18.0% mentions / 20.1% distinct; **sale 30%/loan 28% vs receipt 10%**), monetization; **DB packaged + queryable** (`oik db export`, `docs/database.md`) | [phase_9](docs/phases/phase_9_database.md) |
| 10 Analysis | ⬜ | findings write-up (price series, women-as-principals) | — |
| 11 Release | 🔶 PACKAGED | NER model **packaged for HF** (licence firewall + model card + `launch`/`push_to_hub`); 2 owner-run commands from live | [phase_11](docs/phases/phase_11_release.md) |

---

## 7. Current machine state — READ THIS FIRST in a new session

_Last updated: 2026-07-24. Branch **`main`**; working tree clean._

> ## ✅✅ COMPLETED DIRECTIVE — WOMEN ANALYSIS, done PROPERLY with the models (owner, 2026-07-24)
>
> **DONE — all 8 steps complete + validated (2026-07-24).** Two findings on the
> trained models: the **autonomy curve** (steps 1–6) and **principals by deal type**
> (steps 7–8). Numbers in §5 LATEST + the phase-9 doc. The step record below is kept
> as the build log. **The front is closed; next is Phase 10 (findings write-up).**
> Original binding directive (every point delivered):
>
> - **FOCUS: the "autonomy" finding FIRST** — of women who transact, how many act
>   **with** a guardian (`μετὰ κυρίου`) vs **without** (`χωρὶς κυρίου`) — the curve
>   over time and region. Then the fuller "women as principals across deal types."
> - **USE THE TRAINED MODELS, not rules.** **Download the model(s) from the Modal
>   volumes at run time — do NOT rely on any locally-saved copy.**
> - **CORPUS-SCALE INFERENCE, ON MODAL GPU** — run the NER model over ALL 61,249
>   text docs on an **A10** (`modal_app/ner.py`, `gpu="A10"`). The model already
>   lives on the volume; batched encoder forward passes = **minutes on GPU vs an
>   hour+ on laptop CPU**. Push corpus text (`tm_id`+`edited_text`) to the
>   `oikonomia-ner` volume first, write spans back to the volume, then pull down for
>   the deterministic laptop steps. Keep chunk/stride + assembly in the pure library
>   (laptop-testable); the Modal function is a thin GPU entrypoint.
> - **LONG DOCUMENTS MUST BE HANDLED** — no 512-token truncation loss; chunk/stride
>   so NO people are dropped. We need the long docs.
> - **FIX EVERY RELATION-MODEL ISSUE, all of them:** (a) extract `RelationHead` out
>   of the `train()` closure into a reusable module; (b) add all-gold train + save
>   (custom `state_dict` + config — it is not a standard HF model); (c) add
>   standalone RE inference that runs on the **NER-predicted** entities (reuse
>   `label_candidates` / `admissible_mask` / `constrain` / direction features);
>   (d) measure the end-to-end drop vs the 0.65 oracle PARTY_OF.
> - **FIX ALL MISSING STUFF, ALL OF IT:** batched corpus NER inference; read the
>   exact `corpus.parquet edited_text` and carry `tm_id`; **person-blob splitting**
>   (43% of PERSON spans are name+patronymic collapsed) for gender + kinship; feed
>   model spans into the gender rules (guardian formula + nomen + kin); a model-fed
>   assembler + metadata join (date/place/genre); **end-to-end validation of the
>   women pipeline vs the 115-doc gold.**
> - **AIM FOR THE BEST, NEVER FOR GREEN (§2).** Validate with rough versions;
>   deliver only the best. No synthetic slop.
>
> **Order (chronological; steps 1–2 on Modal GPU, 3–8 deterministic on laptop):**
> 1. ✅ **DONE** — `oik ner corpus-text` emits `{stem, tm_id, text}` for the 61,249
>    non-empty docs; batched **Modal A10** entrypoint `modal_app/ner.py::infer_corpus`
>    (chunk/stride in the pure `oikonomia.ner.inference`; loads the model from the
>    volume at run time via `_resolve_ckpt`).
> 2. ✅ **DONE** — ran NER over all 61,249 docs on the A10 → **1,368,079 entities**
>    (PERSON 350k, PLACE 48k, …), 3,304 long docs windowed, **provenance validated
>    0/1.37M mismatch** against `corpus.parquet.edited_text`. Output
>    `data/processed/ner/ner_corpus.jsonl`, keyed by **`stem`** (NOT tm_id — see §8).
> 3. ✅ **DONE** — person-blob split (`oikonomia.db.names.parse_person_name`):
>    head + patronymic chain + metronymic/alias/status, each with offsets.
>    **128,896 father links recovered** (99% of the 130k blobs), 100% heads, 0
>    offset errors. Fixed a `μητρ`-stem bug (was eating names like Δημητρίου).
> 4. ✅ **DONE** — gender+guardian over model spans (`oikonomia.db.personscan`,
>    `oik db persons` → `db/persons.parquet`, 350k rows). `guardian_status` types
>    the formula **with** (μετὰ) vs **without** (χωρὶς κυρίου). Result: 30%
>    gender-attributable, women's share 21.7%; **autonomy signal — 1,770 women
>    with a guardian formula: 92% μετὰ / 8% χωρὶς** (94% clean of competing male
>    signal; the 6% mis-scoped window is what step 6 measures).
> 5. ✅ **DONE** — the autonomy **curve** (`oikonomia.db.autonomy`, `oik db
>    autonomy` → `db/autonomy.parquet`). **χωρὶς-κυρίου (autonomous) share by
>    century: 0% (≤1c AD) → 1% (2c) → 39% (3c) → 80% (4c) → 77% (6c)** — reproduces
>    the *ius liberorum* spread / decline of tutela mulierum, unsupervised. Region
>    cut is confounded by each nome's era-composition (secondary).
> 6. ✅ **DONE** — gold validation (`oik db validate-women`): gender rules **100%
>    deterministic** (613/613 matched spans agree); PERSON relaxed recall 0.91;
>    guardian-women over-counted on the μετὰ (with) side, but **χωρὶς matches gold
>    exactly** — so the autonomy rise is **conservative**, not inflated. Trend robust.
> 7. ✅ **DONE + GPU-verified (2026-07-24).** RE model revived, saved, and
>    end-to-end measured. **(a)** `RelationHead` → module-level `build_relation_head`
>    factory; re-verified via `xval` (F1 0.729, PARTY_OF 0.678). **(b)** `launch`
>    trained silver→all-gold and **saved** the custom `state_dict`+`config.json` to
>    `/vol/models/relation/final` (5-fold CV F1 0.721, PARTY_OF 0.705 — matches the
>    frozen profile). **(c)+(d)** `eval_e2e` ran the saved model on the 115 gold docs
>    twice, **`docs_missing_pred=0`** (stem↔doc_id join clean):
>    **PARTY_OF held-out-oracle 0.705 → end-to-end 0.623** (NER-predicted entities);
>    the entity cascade costs **≈0.08** on PARTY_OF, which survives at ~0.6 — usable
>    (noisy) for step 8. (The same-model oracle on these docs reads 0.993 but that is
>    train-on-test, not a generalization number.) Detail in the phase-8 doc.
> 8. ✅ **DONE (2026-07-24) — women as principals ACROSS DEAL TYPES.** Ran the saved
>    RE model over all 61,249 docs' NER entities on the A10 (`relations.py::infer`
>    → `infer_corpus`) → **228,945 relations, 16,315 PARTY_OF** (`re_corpus.jsonl`).
>    `oik db principals` keeps PARTY_OF/PAID_* heads, joins gender+guardian+father
>    from `persons.parquet`, tags by deal type → **21,895 principals, women's share
>    18.0%** (9,130 gender-attributable). **Headline — the deal-type gradient: sale
>    30% / loan 28% (property transactions) vs receipt/delivery/account 5-10%
>    (fiscal paperwork).** Guardian split 92% μετὰ / 8% χωρὶς (= step-4 number, RE
>    didn't distort it); 65% of women principals carry a patronymic (`CHILD_OF`).
>    Pure windowing/candidate logic in `oikonomia/relations/infer.py` (laptop-tested);
>    assembler `oikonomia/db/principals.py`. 35 giant registers RE-skipped by design
>    (quadratic cost, no party structure). Detail: phase-9 doc.
>
> **What is on Modal (checked 2026-07-24, do not re-guess):** NER model SAVED at
> `oikonomia-ner:/models/b1/final` (`RobertaForTokenClassification`, 15 labels / 31
> BIO). DAPT backbone `oikonomia-dapt:/checkpoints/full/final`. Volume data:
> `silver/gold/labels/relation_labels` (relation_labels **re-pushed 2026-07-24**,
> now 8b-current with AGE/OCCUPATION). `predictions/ner_corpus.jsonl` (1.37M ents).
> **RE MODEL: SAVED 2026-07-24** at `oikonomia-ner:/models/relation/final` (custom
> `relation_head.pt` state_dict + `config.json`; written by `launch`, load-verified
> by `eval_e2e`). **Corpus RE run DONE 2026-07-24:** `predictions/re_corpus.jsonl`
> (61,249 docs, 228,945 relations, 16,315 PARTY_OF; 35 dense registers skipped).
>
> **Progress:** steps **1–8 ALL DONE + validated — THE WOMEN FRONT IS COMPLETE.**
> Steps 1–6: autonomy finding (χωρὶς-κυρίου curve 0%→39%→80% over 3c→4c AD,
> gold-validated). Step 7: RE model saved + end-to-end **PARTY_OF 0.623**. **Step 8
> (2026-07-24):** corpus RE → `oik db principals` → **women as principals 18.0%,
> deal-type gradient sale 30%/loan 28% vs receipt/delivery 5-10%** (guardian split
> 92/8 = step-4 number; 65% carry a patronymic). ⇒ **Next session: Phase 10 write-up**
> of the findings (prices, taxes, autonomy curve, principals-by-deal-type), and/or
> Phase 11 model release (deliverable #1, already packaged).

**PARKED — model release (deliverable #1).** Superseded by the directive above.
NER release is PACKAGED (licence firewall `oikonomia.models.licensing`; model card
`resources/release/MODEL_CARD.md`; owner-run `launch`+`push_to_hub` in
`modal_app/ner.py`; GreBerta apache-2.0 verified; `MODEL_LICENSES.md` corrected).
Resume only after the women work. Detail:
[`docs/phases/phase_11_release.md`](docs/phases/phase_11_release.md).

**THE PIVOT — read before doing anything.** The deliverable is a **queryable,
auditable economic database + findings** (§1). The models are frozen at a
publishable bar (entity 0.737, relation 0.713 oracle). **Do NOT resume relation-F1
tuning** — it is measured out (8a: every model-side knob neutral; direction is
data-bound at PAID_BY 0.15 and parked). The active work is **Phase 9: the
database** — deterministic, laptop, no GPU. Every hour goes to fact assembly,
normalization, and the first finding, not to moving 0.71 → 0.75.

**Phase 9 state — the full-corpus database exists.** `oik db build --sample 0` →
`data/processed/db/monetary.parquet` (gitignored, re-derivable, ~2.6 MB / 195,906
rows): **99% normalized, 100% provenance, silver 140k / gold 54.8k.** Validation:
2c AD wheat ≈ 12 dr/artaba (lit. ~7–8) and the silver→gold monetization transition.
**Two findings are ready in the table: 7,725 prices (wheat/wine/oil/barley, 8–9
centuries) and 6,623 tax payments (demosia/laographia/phoros — cleaner, no
per-unit math).** Code: `src/oikonomia/db/{money,dates,facts}.py` + `cli/db_cmd.py`.
Detail: [`docs/phases/phase_9_database.md`](docs/phases/phase_9_database.md).

**Wheat price finding — DONE + validated (`oik db prices`).** `src/oikonomia/db/
prices.py` cleans the fact table (drops the 48% `value_num==quantity` double-link
artifact, bronze `chalkous`, wrong units, implausible qty/price). 70 clean wheat
obs reproduce the literature: 3c BC **2.53** (lit ~1–2), **2c AD 13.33 [IQR 6–27.5]
n=37** (lit ~7–12 — IQR brackets it), 3c AD 3.76. Writes `db/prices.parquet` (98
obs, full provenance). Small n is the honest cost of precision filtering.

**MODELS vs RULES — read this so it never confuses again.** The economic findings
(prices/taxes) run on the **lexicon + rules**, NOT the trained neural models —
correctly: prices need closed-class vocab (drachma/artaba/wheat) a gazetteer
matches at ceiling, so the model adds nothing. The trained models earn their keep
elsewhere: (1) as **deliverable #1** (a released papyri Greek NER+RE model — a
contribution in itself), and (2) for the **person/place-heavy findings** (women-as-
principals, kinship) where PERSON/PLACE are open-class and rules fail (model beats
rules +19 PERSON / +11 PLACE). The entity model is now **wired into the DB** — its
corpus-scale run (`ner_corpus.jsonl`) drives the autonomy finding (steps 1–6). The
relation model is now **saved too** (step 7, 2026-07-24: `/vol/models/relation/final`,
end-to-end PARTY_OF 0.623) and drives **step 8** (women as principals), next.

**Tax finding — DONE + validated (`oik db taxes`).** `src/oikonomia/db/taxes.py`
+ `places.py`. (1) **Fiscal-regime map** (tax × era) reproduces textbook history:
laographia (poll tax) Roman-only, prosdiagraphomena Roman surcharge, demosia the
Byzantine land tax, phylakitikon Ptolemaic-fading. (2) **Poll-tax payments** by
century (installments: median ~4 dr, p90 20 dr → the known annual ~16–40 dr tail)
and **by region** (place names resolved from HGV: Arsinoites 25 dr vs
Herakleopolites 2 dr — real nome variation). Writes `db/taxes.parquet` (592 obs).

**AUTONOMY FINDING — DONE end-to-end on the trained model (steps 1–6, 2026-07-24).**
The full pipeline runs the **model's** corpus-scale NER (not rules), as directed:
`db/names.py` (`parse_person_name`: head/patronymic split — 129k father links) →
`db/personscan.py` (`oik db persons`: gender + typed guardian over the 350k model
PERSON spans) → `db/autonomy.py` (`oik db autonomy`: the curve). **Result — the
χωρὶς-κυρίου (autonomous) share by century: 0% (≤1c AD) → 39% (3c) → 80% (4c)**,
reproducing the *ius liberorum* spread / decline of tutela mulierum unsupervised.
Gold-validated (`oik db validate-women`): gender rules **100% deterministic**;
over-count is on the μετὰ side so the rise is **conservative**. Gender logic
(`db/persons.py`, precision-ordered: guardian→female, nomen `Αὐρήλιος`m/`Αὐρηλία`f,
θυγάτηρ/υἱός, Egyptian `Τα-`f/`Πα-`m, gazetteer; guards for metronymic `μητρὸς X`,
the `καὶ ὁ υἱὸς` handoff, masc-inflection veto) is unchanged and each attribution
labels its `basis`. **A bootstrapped name gazetteer was built then REMOVED as slop
(2026-07-24)** (synthetic shortcut, §2). The relation-based `oik db women`/`parties.py`
path (needs PARTY_OF) is the **step-8** fuller finding, still to come; `--source
corpus` there is a rule-labeler lower bound only.

**Triage (what is shelved/frozen — do not reopen without a finding that demands it):**

| Verdict | Items |
|---|---|
| **DELETED from plan** | direction features (null), `constrain-decode`/`--no-relation-weight` as F1 levers, PL-Marker, BOND self-training, model EVENT node, the maximal OIKONOMIA-RE program. Code left dormant (ripping out forces a re-verify retrain); do not build on it. |
| **FROZEN (publishable, deliverable #1)** | entity NER 0.737, relation RE 0.713. A `launch`-style full train happens only when the DB needs the shippable model. |
| **SHELVED (revisit only if a finding needs it)** | relation-model tuning, silver re-emission cycles, splits, ORIGIN_OF/LOCATED_IN/HAS_STATUS as model targets, more direction gold (→ only for a credit-flow finding). |
| **PARKED review artifact** | `data/gold/attribute_draft.jsonl` (8b HAS_OCCUPATION/HAS_AGE, 242 edges) — owner reviews when convenient; merging is opportunistic, not critical path. |

### Resume checklist (in order)

```bash
cd /Users/abdoumagico/Development/ACHATES

# 1. Green before changing anything (604 tests, mypy 86 files, ruff clean at last save)
.venv/bin/ruff check src tests modal_app && .venv/bin/python -m mypy src && .venv/bin/python -m pytest

# 2. ⇒ The WOMEN FRONT IS COMPLETE (steps 1-8). Next is PHASE 10 — write up the five
#    findings (prices, taxes, autonomy curve, principals-by-deal-type, monetization).
#    All finding tables regenerate on the laptop (all gitignored, re-derivable):
.venv/bin/oik db persons && .venv/bin/oik db autonomy      # autonomy curve (reads ner_corpus.jsonl)
.venv/bin/oik db principals                                # principals-by-deal-type (reads re_corpus.jsonl + persons.parquet)
#    (needs data/processed/ner/ner_corpus.jsonl AND data/processed/re/re_corpus.jsonl —
#     pull from the oikonomia-ner volume if missing: /predictions/{ner,re}_corpus.jsonl)

# 3. Laptop artifacts intact? (only if rebuilding; all gitignored)
.venv/bin/oik gold check            # 115 docs, all human_validated, 0 errors
```

**Then, in priority order (the women front is DONE — findings now exist):**
**(1) Phase 10 — write up the five findings** (prices, taxes, autonomy curve,
principals-by-deal-type, monetization transition): the venue paper. This is the
natural next front now that the women analysis is complete. **(2) harden the wheat
price slice** — outlier filter, fix per-unit semantics (`unit_price =
value/quantity` over-divides when the amount is already per-unit), → a defensible
series with error bars vs Rathbone/Bagnall. **(3) entity identity / coreference**
for cross-document prosopography (the principals table now has 65% patronymic
coverage — a real hook). **(4) release the frozen models** (deliverable #1, already
packaged). **Do NOT** reopen relation-F1 work, silver re-emission, or Modal xval
unless a *specific finding* proves the frozen model is the binding constraint — the
audits say it is not.

### Operational gotchas (do not relearn these the hard way)

- **Gold is append-only.** Add rows; compute offsets by forward-scanning surface
  strings against `corpus.parquet` text — never regenerate the whole file. (The old
  `tools/build_gold_draft.py`, which `write_text`-overwrote gold from a stale SPEC,
  was removed 2026-07-23; recover from git if its annotation record is ever needed.)
- **`tools/build_attribute_draft.py` is the SAFE draft tool**: it only *reads*
  `annotated.jsonl` and writes the separate `attribute_draft.jsonl`; refuses
  `--out == --gold`. Merging approved edges into gold is a manual append-by-index step.
- **Gold `text` must be byte-identical to `corpus.parquet.edited_text`.** The
  numeral-coverage gate keys on an exact `text` match and **silently disables
  itself** on any doc where it differs. Always source gold text from
  `corpus.parquet`, never from a batch/suggestion file (some carry
  normalized-away-from-corpus text). Run `oik gold check` after every edit.
- **Run `modal_app/ner.py` and `relations.py` with the VENV's modal**
  (`.venv/bin/modal`) — the container imports `oikonomia`. `dapt.py` uses global
  modal (ships nothing local).
- **Warm-container stale-data trap.** `push` and `train` each print a silver
  fingerprint (`sha docs age`); they **must match**, or the run trained on
  pre-push data. Current silver: **`sha=96428892f944 docs=48891 age=4888`**.
- **Relation schema on the volume goes stale.** `relation_labels.json` embeds
  `entity_labels`/`relation_labels` from `RELATION_SIGNATURES`. When 8b added
  `HAS_AGE`/`HAS_OCCUPATION` (→ AGE/OCCUPATION endpoints), the volume copy was NOT
  re-pushed, so `relations.py::train` hit `KeyError: 'AGE'` at `ent2id`. **Always
  `oik relation prepare` → `relations.py::push` before a relation run** if the
  signatures changed. Current schema: 12 rel labels / 13 entity labels, recall
  guard 0 uncovered.
- **8 dense gold docs are held** (too fragmentary to auto-draft; need careful
  human work): `23914 25467 27734 28329 31975 33510 37263`.

### Artifacts on disk (all gitignored, re-derivable) & Modal state

- `data/raw/idp.data` — **6.1 GB**, HEAD at pinned rev `d7a34f30…`, count-verified
  (`DDbDP` 67,980 · `HGV_meta_EpiDoc` 66,872 · `Translations` 8,001).
- `data/processed/corpus.parquet` — 293 MB, 67,980 rows, `build_corpus` v4.
- `data/processed/splits.parquet` (+ report) — `build_splits` v3, 61,249 rows.
- `data/processed/dapt/{train,dev}.bin` (+ `.json`) — v3, 8.25M + 1.10M tokens.
  **No test shard, by design.**
- `data/processed/silver.jsonl` — 146 MB, Silver-v2 over train
  (`sha=96428892f944 docs=48891 age=4888`). Regen: `oik silver distmap` →
  `oik silver label`. Needs `silver_label_dist.json`.
- `data/gold/annotated.jsonl` — **git-tracked**, 115 docs all `human_validated`,
  2,995 entities / 710 relations (incl. 87 PAID_*), 0 errors. `direction_draft.jsonl`
  is the auditable record of the merged direction edges.
- `data/processed/relations/relation_labels.json` — gitignored; `oik relation prepare`.
- `data/processed/ner/corpus_text.jsonl` — `{stem, tm_id, text}` for the 61,249
  non-empty docs (the GPU-inference payload, ~upload with `modal volume put`).
  Regen: `oik ner corpus-text`. Gitignored, re-derivable.
- `data/processed/ner/ner_corpus.jsonl` — **corpus-scale NER: 61,249 docs /
  1,368,079 entities**, one record per doc `{stem, tm_id, entities[{start,end,label,text}]}`,
  offsets into `corpus.parquet.edited_text` (validated 0/1.37M mismatch). Keyed by
  **`stem`** (unique) — the women pipeline's extraction input. Regen: `oik ner
  corpus-text` → `modal volume put` → `modal run modal_app/ner.py::infer` → `modal
  volume get`. Gitignored, re-derivable.
- `data/processed/db/monetary.parquet` — **2.6 MB, 195,906 rows** (Phase 9 fact
  table). Regen: `oik db build --sample 0` (~minutes). Gitignored, re-derivable.
- `data/processed/db/prices.parquet` — **98 clean price obs** (wheat/barley/wine,
  with provenance). Regen: `oik db prices`. Gitignored, re-derivable.
- `data/processed/db/taxes.parquet` — **592 clean tax payments** (poll + land tax,
  with provenance). Regen: `oik db taxes`. Gitignored, re-derivable.
- `data/processed/db/parties.parquet` — party (principal) table w/ gender+guardian
  +role+span. Regen: `oik db women --source gold` (178 rows) or `--source corpus`
  (noisy lower bound). Gitignored, re-derivable.
- `data/processed/db/persons.parquet` — **350,206 rows**, gender+guardian for every
  model PERSON span (step 4): head/father split, gender_basis, guardian with/without
  /none, provenance. Regen: `oik db persons` (reads `ner_corpus.jsonl`). Gitignored.
- `data/processed/db/autonomy.parquet` — the **autonomy curve** (step 5): 32 buckets
  (century + region), n_with/n_without/autonomous_share. Regen: `oik db autonomy`
  (reads `persons.parquet`). Gitignored, re-derivable.
- `data/processed/re/re_corpus.jsonl` — **corpus-scale RE (step 8): 61,249 docs,
  228,945 relations / 16,315 PARTY_OF**, one record per doc `{stem, tm_id,
  entities, relations[{head,tail,type,confidence}]}`. 35 dense registers RE-skipped.
  Regen: `modal run modal_app/relations.py::infer` (A10) → `modal volume get
  /predictions/re_corpus.jsonl data/processed/re/`. Gitignored, re-derivable.
- `data/processed/db/principals.parquet` — **21,895 principals** (step 8): PARTY_OF/
  PAID_* heads with gender+guardian+father+deal_type+span. Women 18.0%; deal-type
  gradient sale 30%/loan 28% vs receipt 10%. Regen: `oik db principals` (reads
  `re_corpus.jsonl` + `persons.parquet`). Gitignored, re-derivable.
- `data/processed/db/export/` — **the packaged database** (deliverable #2):
  `documents.parquet` (61,249-doc spine w/ per-doc counts + price/tax flags),
  `persons_distinct.parquet` (**17,362 distinct people**, coref-lite — **1,414
  distinct women principals / 7,022 = 20.1%**, the honest headcount vs the 18%
  mention share), `manifest.json` (inventory + `corpus_rev` + CC BY 3.0). Regen:
  `oik db export`. Schema doc: [`docs/database.md`](docs/database.md). Gitignored.
- **Modal Volume `oikonomia-dapt`:** `shards/{train,dev}.bin`,
  `checkpoints/full/final` (**B1** — load this for b1). Stale `checkpoints/b1-*`
  from the first sweep are safe to `modal volume rm -r`.
- **Modal Volume `oikonomia-ner`:** `data/{silver,gold,labels}.json*` +
  `relation_labels.json` (re-pushed 2026-07-24 — now 8b-current w/ AGE/OCCUPATION)
  + `data/corpus_text.jsonl` (the inference
  payload). `models/{b0,b1}/final` from Phase 7 — **`models/b1/final` is what the
  corpus NER run loaded** (`_resolve_ckpt`). `predictions/ner_corpus.jsonl` = the
  61,249-doc / 1.37M-entity NER output; `predictions/re_corpus.jsonl` = the
  61,249-doc / 16,315-PARTY_OF corpus RE output (step 8). `models/relation/final`
  = the saved RE model (`launch`). `xval` measures and saves no persistent NER
  model — the shippable NER model is produced by **`launch`**
  (`train(save_final=True)` → `models/release/final`, all gold), then **`push_to_hub`**.

**Quality gate at last save:** ruff (src tests modal_app) · mypy (88 files) ·
619 tests · caches cleared — all green. `oik gold check` 0 errors. Corpus NER run
provenance-validated 0/1.37M mismatch. Women pipeline gold-validated (gender rules
100% deterministic, autonomy trend robust). Step 8: corpus RE 61,249 docs /
16,315 PARTY_OF; principals finding deal-type ordering stable at n≥40. DB packaged
(`oik db export`): 61,249-doc spine + 17,362 distinct people; schema `docs/database.md`.

---

## 8. Key facts (the load-bearing few — full ledger → [`docs/fact-ledger.md`](docs/fact-ledger.md))

Consult these constantly; the full ledger has the rest and the evidence.

- **Pinned corpus rev:** `d7a34f302d1e44e271256092c2b780733187b478` (papyri/idp.data
  HEAD 2026-07-20), in `configs/base.yaml`. Repin deliberately, never incidentally.
  Licence **CC BY 3.0**.
- **idp.data path conventions are asymmetric:** DDbDP `DDbDP/{id//1000}/{stem}.xml`;
  HGV `HGV_meta_EpiDoc/HGV{id//1000+1}/{stem}.xml` (**+1 and "HGV" prefix**);
  Translations `Translations/{id//1000}/{id}-{seq}.xml`. Parse with
  **`collect_ids=False`** — duplicate `xml:id` is endemic (0.75% of files) and
  otherwise fatal. With it, parse rate is **1.000**.
- **Denominators for supervision:** 67,980 DDbDP docs total, but only **61,249**
  have real text and **44,064** also carry a numeral. Filter empties on
  `parse_flags`/`.strip()`, **never** on `n_chars_edited` (it counts whitespace).
- **Whitespace is canonical in `corpus.parquet` and the parser is the only thing
  that decides it** (`build_corpus` v4: single spaces, one `\n` per line break,
  nothing at a `break="no"` break, no edge padding). **Do not re-collapse it in a
  consumer** — that silently decouples your spans from the stored text.
- **`<lb break="no"/>` = line break *inside* a word** (35.28% of docs) — no
  separator belongs there. Handled by the parser's `_join_broken_words` pre-pass.
- **Backbone B1 = `bowphs/GreBerta`** (apache-2.0, encoder-only RoBERTa-base, 512
  ctx, 52k vocab) **+ papyri full-FT DAPT**. **GreBerta preserves case** (unlike
  GreTa) — keeping case is the strongest PERSON/PLACE cue and is −0.59% tokens.
  `koine-t5*` are **CC-BY-NC-SA — never release on them.**
- **Word order: units PRECEDE their numeral** (`πυροῦ ἀρτάβαι ιβ`; δραχμαι left of
  the numeral 81.5% of the time). Any proximity rule breaks ties **leftward**.
- **Leakage signals:** near-duplication **2.89%** (475 clusters); **1,706 docs
  share a TM id**. Both are grouped before splitting.
- **Modal (re-verify at `modal.com/docs` before use):** `modal.App` (not `Stub`);
  **`gpu="A10"`** (NOT `"A10G"`); `Volume.from_name(create_if_missing=True)`;
  `evaluation_strategy`→`eval_strategy` (transformers ≥5); **`.map()`/`.starmap()`
  are positional-only — use `.spawn()` + `FunctionCall.get()`** to vary kwargs.
- **Zero entity markup upstream** (0% over 200 docs) — all entity/relation
  supervision is built by hand. This is why gold is the critical path and
  relations the scientific risk.
