# Phase 11 — Model release (deliverable #1)

### Why now — the pivot from build to ship (2026-07-24)

After the women-as-principals work, an honest audit put
the project at **0/3 shipped deliverables** despite a large validated substance
base (models at bar, ~196k-row fact table, three findings). Decision: stop
accumulating substance, take **one** deliverable all the way out. Chosen first
ship: **deliverable #1 — the papyri Greek NER model on Hugging Face** — because it
is closest to done (at a publishable bar), a standalone contribution, and unblocks
nothing else.

### What was packaged (laptop, no publishing, no auth)

The release is **prepared up to the authentication line**; the two steps that
require credentials/publishing are the owner's.

- **Licence firewall — `src/oikonomia/models/licensing.py`** (the safety code
  `MODEL_LICENSES.md` *claimed* existed but never did). `assert_releasable(lineage)`
  is **fail-closed**: any ancestor that is NonCommercial *or* absent from the vetted
  allowlist blocks the push. Called by the Hub-push step before a byte leaves.
  Tests: `tests/test_models_licensing.py` (GreBerta clean, koine-t5 refused,
  unknown refused, empty refused).
- **Licence verified against the live source.** `bowphs/GreBerta` is **apache-2.0**
  (checked on its HF model card, Riemenschneider & Frank ACL'23). `MODEL_LICENSES.md`
  was **stale** — it described a superseded GreTa/T5 ablation; corrected to the real
  GreBerta chain. Model weights: apache-2.0 (backbone-inherited); training corpus
  DDbDP is CC BY 3.0 and is attributed in the card.
- **Model card — `resources/release/GRAMMATEUS_CARD.md`** (the HF README): frontmatter
  (apache-2.0, `grc`, base_model, metrics), the 15 labels, eval (strict **0.737** /
  relaxed **0.837**, 5-fold CV on 115-doc gold; per-label; DAPT +9.5 vs control),
  intended use + usage snippet, limitations, DDbDP provenance/attribution,
  citations (project + GreBerta + DDbDP).
- **Release code — `modal_app/ner.py`** (owner-run): `train(..., save_final=True)`
  retrains on **all** gold (not a CV fold) and saves one checkpoint; `launch`
  drives it; `push_to_hub` uploads the checkpoint + card + labels to the Hub behind
  the firewall, **starting private**. Modal secret syntax re-checked against
  modal.com/docs.

### The two models, named (2026-07-24)

Both are downloaded from the Modal volumes, verified to load locally, and carded.
The family is **OIKONOMIA**; the models carry papyrological names that say what
they do:

| Model | Name | Why | Repo id | Card |
|---|---|---|---|---|
| Entity NER | **OIKONOMIA-Grammateus** | γραμματεύς, "the scribe" — the village clerk who wrote down who, where, how much | [`ainouche-abderahmane/grammateus`](https://huggingface.co/ainouche-abderahmane/grammateus) | `resources/release/GRAMMATEUS_CARD.md` |
| Relation RE | **OIKONOMIA-Homologia** | ὁμολογία, "the acknowledgment" — the contract formula binding parties to a deal; ὁμολογῶ is the corpus's most frequent transaction word (~3,000 attestations) | [`ainouche-abderahmane/homologia`](https://huggingface.co/ainouche-abderahmane/homologia) | `resources/release/HOMOLOGIA_CARD.md` |

**Local copies** (gitignored, `artifacts/` tier): `artifacts/models/grammateus/`
(125.4M params, `RobertaForTokenClassification`, 31 BIO tags) and
`artifacts/models/homologia/` (129.1M params, custom span-pair head, 12 relation
classes / 13 entity endpoints). Pulled with
`modal volume get oikonomia-ner models/<b1|relation>/final <dest>` — **the
destination directory must already exist**, or `volume get` writes the folder as a
single opaque file.

**Both verified to load and run locally**, not merely downloaded: Grammateus tags
`πυροῦ ἀρτάβας δύο δραχμῶν ἑκατόν` as COMMODITY / UNIT / MONEY_AMOUNT / CURRENCY
correctly; Homologia's `state_dict` loads `strict=True` against a freshly built
head, confirming the config.json rebuild recipe printed in its card is exact.

**Homologia's card carries what a standard card would hide:** it is *not* an
`AutoModel` (custom head → `relation_head.pt` + a rebuild config), its oracle
scores are flattering, so the card leads the practitioner to the **end-to-end**
number (PARTY_OF 0.623), and payment *direction* is documented as weak
(PAID_BY 0.145) with the reason (87 gold direction edges, every model-side remedy
measured neutral).

### Where the push runs — a correction (2026-07-24)

The first wiring ran the Hub push *inside* a Modal function, following the pattern
already in `ner.py`. That pattern was right when the weights existed only on the
volume: uploading from a container avoided a 500 MB down-then-up round trip, and
the HF token lived as a Modal secret.

It stopped being right the moment both models were pulled to local disk. Pushing
local files through a container means shipping an auth token to a remote machine to
upload files that are already here. **So the Modal `push_to_hub` functions were
deleted and publishing moved to the laptop:**

- `src/oikonomia/models/release.py` — what a release *is* (`ReleaseSpec`: weights
  dir, card, repo id, required files) and `check_ready`, the pre-flight. It runs the
  **licence firewall first**, then refuses on a missing card or an incomplete
  checkpoint. A half-uploaded Hub repo — weights without a config, or the reverse —
  looks published and loads for nobody; that is the failure this prevents.
- `src/oikonomia/cli/release_cmd.py` — `oik release check|push`, with `--dry-run`,
  private by default, `--public` only when meant.
- **The token is never a CLI argument.** `huggingface_hub` reads it from the stored
  login (`hf auth login`) or `HF_TOKEN`; argv lands in shell history and is visible
  to every process on the box.
- Tests: `tests/test_models_release.py` (7) + `tests/test_release_cards.py` (8).

Modal keeps exactly the job it is good at: the **GPU train** (`ner.py::launch`,
`relations.py::launch`).

### The owner run-sequence (needs an HF write token — Claude cannot authenticate)

An HF **organization** is created from an existing account (huggingface.co → New
Organization) — it is not a second login, and a personal write token covers org
repos you administer.

```bash
# --- Grammateus (entities): still needs its all-gold train on the GPU ---
.venv/bin/modal run --detach modal_app/ner.py::launch          # → models/release/final
mkdir -p artifacts/models/grammateus && .venv/bin/modal volume get \
  oikonomia-ner models/release/final artifacts/models/grammateus

# --- publish both from the laptop ---
hf auth login                                                  # once (or export HF_TOKEN)
.venv/bin/oik release check grammateus                         # pre-flight, uploads nothing
.venv/bin/oik release push  grammateus                         # → ainouche-abderahmane/grammateus
.venv/bin/oik release push  homologia                          # → ainouche-abderahmane/homologia
```

Both start **private** — review on HF, then flip to public. Note the asymmetry:
Homologia's shippable weights already exist (saved by `relations.py::launch` during
step 7 of the women work) and its local copy is verified, so it can go out today.
Grammateus's local copy is `models/b1/final`, the Phase-7 checkpoint used for corpus
inference — publishable, but the intended release model is the all-gold `launch`
above.

### ✅ PUBLISHED (2026-07-24) — all three artifacts are live

| Artifact | Hub |
|---|---|
| OIKONOMIA-Grammateus (entities) | <https://huggingface.co/ainouche-abderahmane/grammateus> |
| OIKONOMIA-Homologia (relations) | <https://huggingface.co/ainouche-abderahmane/homologia> |
| OIKONOMIA-DB (dataset, deliverable #2) | <https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db> |

All three cards verified live: apache-2.0 on the models, CC BY 3.0 on the dataset,
`grc` language tag, base-model lineage, metrics, limitations and citation present.

### Post-publication audit (2026-07-24)

An external review of the three live repos, plus a sweep of our own, found seven
defects. All are fixed locally; **the live pages still carry them until a re-push.**

| # | Defect | Fix |
|---|---|---|
| 1 | Cards referenced the never-created `oikonomia/*-grc` org repos in three places, including the Grammateus usage snippet — copy-paste gave a 404 | Both cards, the three `repo_id` defaults in `models/release.py`, and the cross-reference test now use the real `ainouche-abderahmane/*` ids |
| 2 | **Homologia's architecture lived in `modal_app/relations.py`** — a §3 violation: the published model was unloadable without the orchestration layer the boundary says must be deletable | `build_relation_head` moved to `oikonomia/relations/model.py`; added `load_homologia()`, one call from a repo id or a local dir. `modal_app` now delegates. Guarded by `test_published_architectures_are_defined_in_the_library` |
| 3 | Dataset card documented a `person_id` join key that **did not exist** | `persons_distinct` now ships a real `person_id` — a stable 16-hex hash of the coref-lite key, unique across all 17,362 rows and identical across rebuilds |
| 4 | Dataset viewer was dead: the frontmatter used a malformed `dataset_info.features` block listing tables as features | Replaced with a `configs:` block, one config per table. Enables the viewer and `load_dataset(..., "prices")`. A test ties the declared configs to the release spec's required files so they cannot drift |
| 5 | **`check_ready` listed only top-level files** while `upload_folder` uploads recursively — the pre-flight under-reported what went public, and could ship a dataset missing two of its eight tables | Listing recurses; `export/documents.parquet` and `export/persons_distinct.parquet` added to `required`; two tests cover it |
| 6 | `docs/project_summary.md` claimed a *"Late Roman Hyperinflation (4th c. AD): prices soaring to 300.00 dr/artaba"* — **there is no 4th-century wheat data at all** (wheat spans 3c BC–3c AD), and the two 4c rows are *wine in keramia*. A known unit artifact was written up as a finding | Section rewritten against the shipped tables: the five findings with their real numbers, mechanisms and limits |
| 7 | No CI; the gate was manual | `.github/workflows/ci.yml` runs ruff → mypy → pytest on push and PR, installing only `.[dev]` so it also enforces the no-ML-stack boundary. `pre-commit` now covers `modal_app` like the documented gate |

Card content also hardened where the review pushed on statistics rather than
defects: Grammateus now states that 115 documents over 5 folds is ~23 per fold,
that per-label figures on rare labels are indicative of rank rather than precise,
and that per-fold variance was never recorded (a known gap needing a GPU re-run).
Homologia now states that payment direction is *deliberately absent* from the
published database rather than present and wrong. The dataset card gained a
Limitations section covering the thin price sample, the two error regimes, the
missing direction columns, mentions-vs-people and survival bias.

Verified end to end, not assumed:

- `load_homologia("ainouche-abderahmane/homologia")` downloads and loads the live
  weights `strict=True` → 129.1M params, 12 relation labels, eval mode.
- The Grammateus card's usage snippet, run verbatim, tags
  *πυροῦ ἀρτάβας δύο δραχμῶν ἑκατόν* as COMMODITY / UNIT / MONEY_AMOUNT / CURRENCY.
- Every SQL block in `docs/database.md` (11) and in the dataset card (2) executes.
- The gate passes in **both** environments — with the ML stack (646 tests) and in a
  clean venv without torch (644 + 2 skipped) — after adding mypy overrides so the
  answer no longer depends on whether torch happens to be installed.

### Decided against: `trust_remote_code` standalone loading (2026-07-24)

Homologia does not load with a bare `AutoModel.from_pretrained` the way Grammateus
does, because its span-pair head is not a registered `transformers` architecture.
The fix would be to ship a generated `modeling_homologia.py` inside the Hub repo
with an `auto_map`. **It was built far enough to prove it works, then reverted.**
The reasoning, so this is not rediscovered:

- The win is one `pip install` traded for one `trust_remote_code=True` flag. Both
  paths are two lines for the user.
- The cost is ~800 lines of library logic duplicated into a public artifact, two
  build tools whose textual assumptions break on any refactor, and a **third**
  loading path beside `load_homologia()` and the Modal training code.
- Decisive: `trust_remote_code` couples the published model to `transformers`
  *internals* (the prototype hit `all_tied_weights_keys`, a 5.x private
  attribute). When those shift, the model breaks on users' machines and nothing
  of ours runs there to catch it.
- It does not remove the real barrier anyway. Homologia only does anything useful
  on Grammateus's spans in our 11-relation schema; anyone getting that far wants
  the pipeline and is installing the package regardless.

The supported path is `oikonomia.relations.model.load_homologia()`, and the card
says so plainly. Revisit only if a concrete user is blocked by the install.

### Remaining / next

**✅ Re-pushed 2026-07-24, and verified against the Hub rather than assumed:**

- Both model cards fetched back: **0** remaining `oikonomia/*-grc` dead links;
  Grammateus carries the per-fold sample-size caveat; Homologia documents
  `load_homologia`.
- Dataset card: `configs:` block and Limitations section live.
- `export/persons_distinct.parquet` **downloaded back and read**: 17,362 rows ×
  9 columns, `person_id` present and unique.
- All 10 dataset files present including `export/`; **no junk** (`__pycache__`,
  `.pyc`, `.DS_Store`) — the new shared `IGNORE_PATTERNS` covers listing and upload.

Nothing is outstanding. What remains is optional:

- Optional: `training_args.bin` ships inside Grammateus. It is standard HF output,
  but it is a pickle, so the Hub flags it. Drop it if the warning matters more than
  the record of the training configuration.
- Optional: the all-gold `ner.py::launch` Grammateus retrain, if the released
  Phase-7 checkpoint is to be swapped for the all-gold one.
- Deliverable #3 is recorded: [`phase_10_findings.md`](phase_10_findings.md).

---

## Card rewrite — 2026-07-25 (all three cards rebuilt to HF template structure)

Triggered by an audit of what the three live cards actually contained. The model
cards were strong on metrics; the **dataset card documented tables but not a single
column** — the whole 579-line reference in [`docs/database.md`](../database.md)
(column dictionary, controlled vocabularies, 8 pitfalls) had never reached the Hub.

All three now follow the official HF card templates (`modelcard_template.md` /
`datasetcard_template.md`) adapted to the artifact.

### What was wrong, and what it is now

| # | Defect (live cards, pre-2026-07-25) | Fix |
|---|---|---|
| 1 | Dataset card defined **no columns** for any of the 8 tables | Full per-table column reference: type, measured non-null coverage, meaning |
| 2 | No controlled vocabularies — `gender`, `guardian`, `deal_type`, `roles`, `gender_basis`, currency/commodity/unit/tax ids all undocumented | All 9 vocabularies with counts. (The cost of this gap is concrete: a `gender in ('F','M')` guess returns zero rows — the values are `male`/`female`/`unknown`.) |
| 3 | Pitfalls section never shipped; **`tm_id` is not unique** (231 ids span >1 doc) was nowhere on the Hub | All 8 pitfalls carried over |
| 4 | Provenance claim named columns that do not exist (`stem`, `start_char`, `end_char` in the money tables) | Corrected: `amount_start`/`amount_end` keyed on `tm_id`, `person_start`/`person_end` keyed on `stem`; 0-based end-exclusive stated |
| 5 | No findings section — the evidence base for five results described none of them | "What has been found with it", five findings, every number recomputed from the shipped tables |
| 6 | Grammateus published **12 of 15** per-label F1s, omitting exactly the three the Limitations call weakest | All 15 listed; `COMMODITY`/`PERSON_ROLE`/`TAX_TERM` marked ***not recorded*** with the reason (never logged; re-deriving needs a fresh 5-fold CV, since the shipped all-gold checkpoint scored on gold is train-on-test) |
| 7 | Neither model card had a **single training hyperparameter** | Both carry the two-stage table (LR, schedule, steps/epochs, batch, seq len, loss, optimizer, precision, seed) from `modal_app/{ner,relations}.py` defaults — which is what `launch` runs |
| 8 | Homologia gave end-to-end for `PARTY_OF` only, the rest in prose | Full e2e table (overall 0.609 P 0.771 / R 0.503; PAID_TO 0.507, PAID_BY 0.231, HAS_PRICE/CHARGED_UNDER 0.000), with the 4 unrecorded per-relation e2e figures named as a gap |
| 9 | **`HAS_AGE`/`HAS_OCCUPATION` listed as supported relations with zero gold edges** — silver-only, scored nowhere | Disclosed, with a gold-edge count column (they read 0) beside all 11 relations |
| 10 | `datasets: papyri/DDbDP` in both model frontmatters — **dead link** (HF 401; DDbDP is a git repo, not a Hub dataset) | Removed from frontmatter, cited in prose |
| 11 | Grammateus reported F1 only, no P/R | Stated as not recorded (only micro F1 at both strictness levels was logged); Homologia's P/R added to its `model-index` |
| 12 | No cross-links: dataset ↔ models | All three link the other two; guarded by a test |
| 13 | Homologia had no `library_name` → Hub rendered a broken inference widget for a custom-head model | `inference: false`; both models get `base_model_relation: finetune`; dataset gets `pretty_name` + `tabular` modality tag |

### Guards added (`tests/test_release_cards.py`, 22 → 32 tests)

The card is the public face of the work and ships verbatim, so each fix above is
now locked:

- frontmatter names no Hub repo that does not exist (defect 10);
- both model cards publish hyperparameters (7);
- all three cards link the other two artifacts (12);
- Grammateus discloses the unrecorded per-label scores (6);
- Homologia leads with end-to-end and labels the 0.993 as train-on-test (8);
- Homologia flags the two unsupervised relations (9);
- the dataset card has a column-reference section per shipped table (1),
  the vocabularies and the pitfalls (2, 3);
- **`@pytest.mark.corpus`: every column of every shipped parquet file appears in
  the dataset card** — schema drift between the files and the card now fails the
  suite instead of surfacing as a query that returns nothing.

Both quickstart queries in the dataset card were executed verbatim against the
shipped parquet files; output matches the card.

### Still not measured (honest gaps, each needs a GPU run)

These are stated as gaps *on the cards* rather than quietly omitted:

- per-label F1 for `COMMODITY` / `PERSON_ROLE` / `TAX_TERM` → `ner.py::xval`
- entity-model precision/recall (only micro F1 was logged) → same run
- per-fold variance for every entity figure → same run
- per-relation end-to-end F1 for `HAS_CURRENCY`/`HAS_UNIT`/`HAS_QUANTITY`/`DATED_TO`
  → `relations.py::eval_e2e`
- any score at all for `HAS_AGE`/`HAS_OCCUPATION` → needs gold edges first
  (`data/gold/attribute_draft.jsonl`, still parked for owner review)
