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
| Entity NER | **OIKONOMIA-Grammateus** | γραμματεύς, "the scribe" — the village clerk who wrote down who, where, how much | `oikonomia/grammateus-grc` | `resources/release/GRAMMATEUS_CARD.md` |
| Relation RE | **OIKONOMIA-Homologia** | ὁμολογία, "the acknowledgment" — the contract formula binding parties to a deal; ὁμολογῶ is the corpus's most frequent transaction word (~3,000 attestations) | `oikonomia/homologia-grc` | `resources/release/HOMOLOGIA_CARD.md` |

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
.venv/bin/oik release push  grammateus                         # → oikonomia/grammateus-grc (private)
.venv/bin/oik release push  homologia                          # → oikonomia/homologia-grc (private)
```

Both start **private** — review on HF, then flip to public. Note the asymmetry:
Homologia's shippable weights already exist (saved by `relations.py::launch` during
step 7 of the women work) and its local copy is verified, so it can go out today.
Grammateus's local copy is `models/b1/final`, the Phase-7 checkpoint used for corpus
inference — publishable, but the intended release model is the all-gold `launch`
above.

To publish under a personal account instead of an org, pass
`--repo-id <username>/grammateus-grc` and update the two cross-links in the cards
(`tests/test_release_cards.py` guards against placeholders being left behind).

### Remaining / next

- **Owner-run:** the three commands above. Everything up to the authentication line
  is done, tested and verified.
- After both are live: the findings write-up (#3). The DB package (#2) is shipped.
