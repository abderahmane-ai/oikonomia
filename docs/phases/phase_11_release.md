# Phase 11 — Model release (deliverable #1)

### Why now — the pivot from build to ship (2026-07-24)

After the women-as-principals finding and the coverage lever, an honest audit put
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
- **Model card — `resources/release/MODEL_CARD.md`** (the HF README): frontmatter
  (apache-2.0, `grc`, base_model, metrics), the 15 labels, eval (strict **0.737** /
  relaxed **0.837**, 5-fold CV on 115-doc gold; per-label; DAPT +9.5 vs control),
  intended use + usage snippet, limitations, DDbDP provenance/attribution,
  citations (project + GreBerta + DDbDP).
- **Release code — `modal_app/ner.py`** (owner-run): `train(..., save_final=True)`
  retrains on **all** gold (not a CV fold) and saves one checkpoint; `launch`
  drives it; `push_to_hub` uploads the checkpoint + card + labels to the Hub behind
  the firewall, **starting private**. Modal secret syntax re-checked against
  modal.com/docs.

### The owner run-sequence (needs an HF write token — Claude cannot authenticate)

```bash
# 1. Train the single shippable model on all gold (Modal A10, GPU spend) → models/release/final
.venv/bin/modal run --detach modal_app/ner.py::launch

# 2. Give Modal your HF write token, once:
modal secret create huggingface HF_TOKEN=hf_xxx

# 3. Push (starts PRIVATE — review on HF, then flip to public):
.venv/bin/modal run modal_app/ner.py::push_to_hub --repo-id <your-org>/oikonomia-ner
```

Set the repo id (`<your-org>/…`) in the model card usage snippet after the id is
final. The push refuses to run if the licence firewall does not pass.

### Remaining / next

- **RE model (deliverable #1b)** is *not* shippable yet — it was only xval-measured,
  never saved. A `launch`-style all-data train + save is needed before it can be
  pushed (same pattern as the NER `save_final`).
- After NER is live: the findings write-up (#3) and the DB package (#2).
