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

### The owner run-sequence (needs an HF write token — Claude cannot authenticate)

An HF **organization** is created from an existing account (huggingface.co → New
Organization) — it is not a second login, and a personal write token covers org
repos you administer.

```bash
# 0. Give Modal your HF write token, once (covers both pushes):
modal secret create huggingface HF_TOKEN=hf_xxx

# --- Grammateus (entities) ---
.venv/bin/modal run --detach modal_app/ner.py::launch          # all-gold train → models/release/final
.venv/bin/modal run modal_app/ner.py::push_to_hub              # → oikonomia/grammateus-grc (PRIVATE)

# --- Homologia (relations) --- (already trained + saved: models/relation/final)
.venv/bin/modal run modal_app/relations.py::push_to_hub        # → oikonomia/homologia-grc (PRIVATE)
```

Both pushes default to the repo ids above (`--repo-id` overrides) and **start
private** — review on HF, then flip to public. Each refuses to run if the licence
firewall does not pass. Note the asymmetry: Homologia's shippable weights **already
exist** on the volume (saved by `relations.py::launch` during step 7 of the women
work), while Grammateus still needs its all-gold `launch` run — `models/b1/final`
is the Phase-7 checkpoint used for corpus inference, not the release train.

If you publish under a personal account instead of an org, pass
`--repo-id <username>/grammateus-grc` and update the two cross-links + the usage
snippet in the cards (`tests/test_release_cards.py` guards against placeholders
being left behind).

### Remaining / next

- **Owner-run:** the three commands above. Everything up to the authentication line
  is done, tested and verified.
- After both are live: the findings write-up (#3). The DB package (#2) is shipped.
