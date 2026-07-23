# CLAUDE.md — OIKONOMIA

Agent instructions and live project state. This file is the only thing loaded
into a new session's context, so keep it **lean and current**. Detail that is
not needed to continue work lives elsewhere:

- **Phase history** → [`docs/phases/*.md`](docs/phases) (one file per phase).
- **Load-bearing facts** ("never re-derive") → [`docs/fact-ledger.md`](docs/fact-ledger.md).
- **Architecture detail** → [`docs/architecture.md`](docs/architecture.md).
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

# --- Relations (Phase 8) — also the venv's modal ---
.venv/bin/oik relation prepare                # freeze relation_labels.json; recall guard MUST be 0 uncovered
.venv/bin/oik relation score                  # nearest-pair baseline (the bar): rel micro F1 0.443
.venv/bin/modal run --detach modal_app/relations.py::xval --backbone b1 --loss ce
```

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

**~68% of the 12-phase project. Phases 0–7b + 5c done and *measured*; Phase 8
(relations) reframed as the OIKONOMIA-RE program, in progress.**

**Settled entity recipe (frozen):** DAPT **B1** (GreBerta + papyri **full-FT**
DAPT) → silver-pretrain (Silver-v2, plain **CE**) → **gold fine-tune**. On the
115-doc all-human gold (5-fold CV): **strict F1 0.737 / relaxed 0.837**. AGE
solved (0.974). The remaining entity ceiling is **label consistency of TAX_TERM
(0.39) and PERSON_ROLE (0.36)** — proven immune to *both* more volume and better
silver; the lever is cleaner/split labels, not data.

**First relation model measured:** span-pair (SpERT-style, single encode) + B1 +
silver→gold → **rel micro F1 0.713** (oracle entities, 5-fold CV), vs the
nearest-pair baseline 0.443. Payment **direction learned** (PAID_TO 0.0→0.30) but
**it is the bottleneck** (PAID_BY 0.15). The owner then reframed Phase 8 into a
**maximal program** — full prosopographical DB + max architecture — because the
data audit showed 0.713 is strong on the economic core but **coverage is
schema-bound** (PLACE/AGE/OCCUPATION and 79% of every PERSON are in no relation
at all) and silver is useless for the deliverable-critical relations (direction,
price). **8a's direction-feature experiment then came back flat (0.710 vs 0.713);
direction is data-bound, not feature-bound** — so the maximal program was
**descoped to a lean, auditable core** (rules-first coverage + more gold, not more
model machinery; direction features, BOND self-training and the virtual EVENT node
are cut/shelved). Plan of record:
[`docs/phases/phase_8_relation_model.md`](docs/phases/phase_8_relation_model.md).

**8b (coverage) started — first rules-first win landed.** Deterministic apposition
rules for **HAS_OCCUPATION + HAS_AGE** (the two unambiguous attribute relations):
linked entity coverage on gold **35.7% → 49.6% (+14.0 pts)** from these two alone,
recall guard clean, every edge auditable to two spans. Not yet trained/measured —
awaits gold-draft review + silver re-emit (see §7). Fuzzier PLACE/status relations
(ORIGIN_OF/LOCATED_IN/HAS_STATUS) deferred pending a corpus-evidence pass.

**Assets in hand:** validated ingestion over all 67,980 docs (parse rate 1.000);
whole-corpus characterization; mined lexicons with measured recall; leak-free
stratified + chronological splits; DAPT B1 backbone; 115-doc all-human gold
(2,995 entities / 710 relations incl. 87 PAID_BY/PAID_TO); a scored,
confidence-aware silver labeler over the 48.9k-doc train split.

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
| 8 Relation model | ✅→🔶 | span-pair RE **0.713** (oracle); 8a closed (data-bound); 8b coverage started (+14 pts) | [phase_8](docs/phases/phase_8_relation_model.md) |
| 9 Corpus→DB · 10 Analysis · 11 Release | ⬜ | not started | — |

---

## 7. Current machine state — READ THIS FIRST in a new session

_Last updated: 2026-07-23. Branch **`main`**; working tree clean._

**Phase 8b — first coverage win landed (HAS_OCCUPATION + HAS_AGE).** Deterministic
apposition rule (`src/oikonomia/labeling/apposition.py`): each OCCUPATION/AGE →
nearest PERSON/PERSON_ROLE that *ends before* it, ≤40 chars; a headcount guard
skips counted occupations (`ἱερεῖς β` is a HAS_QUANTITY, not a title). Wired
through the single authority — `RELATION_SIGNATURES` (+2), `LOCAL_FAMILY` (both
gap-capped), silver labeler (`_attribute_relations`), tests, and an **auditable
gold draft** (`tools/build_attribute_draft.py` → `data/gold/attribute_draft.jsonl`,
242 edges / 70 docs, NEVER touches `annotated.jsonl`). On gold: coverage **35.7% →
49.6% (+14.0 pts)**, recall guard **0 uncovered**, all 242 edges candidate-covered.
**Not yet trained.** Measurable only when BOTH sides carry the types — so the next
steps are, together: (a) owner reviews `attribute_draft.jsonl`; (b) merge approved
edges into gold (append-only, by index); (c) re-emit silver (fresh sha) so training
carries them; then (d) owner push + xval. Doing (c) alone would train relations the
gold can't score → misleading F1. **NEXT rule work:** the fuzzier ORIGIN_OF /
LOCATED_IN / HAS_STATUS — deferred pending their own corpus-evidence pass (PLACE
apposition is looser and needs prepositional cues; HAS_STATUS overlaps PERSON_ROLE).

**Phase 8a — CLOSED; every model-side accuracy knob measured neutral.** Three clean
`xval` runs (fingerprint `sha=96428892f944 docs=48891`, gold_docs=98) land in one
noise band: baseline **0.713**, + direction-features/wide-context **0.710**, +
`--constrain-decode` **0.7145** — the silver-only F1 alone wobbles 0.643→0.655
run-to-run, so this spread is pure seed noise. Direction features did **not**
deliver the payer/payee win they were built for (PAID_TO/PAID_BY nominally down;
~17 direction edges/fold = noise), and constraints did **not** raise precision
(0.757→0.752). **Finding: direction is data-bound, not feature-bound** (87 gold
direction edges is too thin regardless of features); no head/decode tweak moves the
~0.71 core. Direction features **dropped**; constraints **kept ON as a DB
well-formedness invariant** (one currency per amount, one tax per payment — not for
F1); `--no-relation-weight 0.3` left untested, low priority. **The lever is data +
coverage → pivot to 8b now.** Full detail: the phase-8 doc.

### Resume checklist (in order)

```bash
cd /Users/abdoumagico/Development/ACHATES

# 1. Green before changing anything
.venv/bin/ruff check src tests modal_app && .venv/bin/python -m mypy src && .venv/bin/python -m pytest

# 2. Artifacts intact? Rebuild if missing (all gitignored, re-derivable):
#    oik ingest build (~85s) → oik splits build (~25s) → oik dapt prepare (~20s)
.venv/bin/oik splits check
.venv/bin/oik gold check            # 115 docs, all human_validated, 0 errors + numerals_checked

# 3. Silver-v2 intact? Re-emit if silver.jsonl missing/stale:
.venv/bin/oik silver score          # entity micro F1 ~0.667 exact / ~0.752 relaxed
#    After ANY labeler/lexicon/patterns edit: oik silver distmap → oik silver label (~5 min; sha changes)

# 4. PHASE 8a — CLOSED (all model-side knobs neutral). PHASE 8b IN PROGRESS:
#    HAS_OCCUPATION + HAS_AGE apposition rule DONE (coverage +14 pts on gold, guard
#    clean). Review the auditable draft, then merge + re-emit silver together:
.venv/bin/python tools/build_attribute_draft.py --preview 20   # regenerate + eyeball
#    Plan of record: docs/phases/phase_8_relation_model.md
```

**Then, in leverage order (LEAN plan — full detail in the phase-8 doc):**
**(1) land the two attribute relations end-to-end** — owner reviews
`data/gold/attribute_draft.jsonl`; a session then merges approved edges into gold
(append-only, by index) **and** re-emits silver (`oik silver label`, fresh sha) so
both sides carry them; owner push + xval measures HAS_OCCUPATION/HAS_AGE F1. **(2)
extend 8b coverage** with the fuzzier ORIGIN_OF/LOCATED_IN/HAS_STATUS (each needs a
corpus-evidence pass first — PLACE apposition is looser, needs prepositional cues;
HAS_STATUS overlaps PERSON_ROLE — do NOT guess them). **(3) more direction gold**
(the only lever for PAID_BY/PAID_TO). **(4) 8d deterministic** kinship/gender parse
+ event assembly in the DB layer. **Owed:** end-to-end eval (predicted entities →
RE, the real number vs the 0.713 oracle ceiling). **Cut/shelved:** direction
features (null), BOND self-training (un-auditable), virtual EVENT node as a model
construct. **GPU runs are owner-triggered** (the owner controls Modal spend).

### Operational gotchas (do not relearn these the hard way)

- **Gold is append-only.** Do **NOT** run `tools/build_gold_draft.py` — it
  `write_text`-overwrites the whole file from a stale 85-doc SPEC and would drop
  the owner's 10 hard docs + the 20 added since. Append rows; compute offsets by
  forward-scanning surface strings against `corpus.parquet` text.
- **`tools/build_attribute_draft.py` is the SAFE 8b tool** (do not confuse with the
  above): it only *reads* `annotated.jsonl` and writes the separate
  `attribute_draft.jsonl`; it refuses `--out == --gold`. Merging its approved edges
  into gold is still a manual append-by-index step, done with the silver re-emit.
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
- **Modal Volume `oikonomia-dapt`:** `shards/{train,dev}.bin`,
  `checkpoints/full/final` (**B1** — load this for b1). Stale `checkpoints/b1-*`
  from the first sweep are safe to `modal volume rm -r`.
- **Modal Volume `oikonomia-ner`:** `data/{silver,gold,labels}.json*` +
  `relation_labels.json` (all current). `models/{b0,b1}/final` from Phase 7.
  `xval` measures and saves no persistent model — the shippable NER model is a
  later `launch`-style full train once the recipe is frozen (it now is).

**Quality gate at last save:** ruff (src tests modal_app) · mypy (67 files) ·
tests · caches cleared — all green. `oik gold check` 0 errors.

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
