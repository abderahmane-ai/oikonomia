<div align="center">

# OIKONOMIA

**Turning 68,000 ancient Greek papyri into a queryable database of the everyday economy of Greco-Roman Egypt.**

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)
[![Code License: MIT](https://img.shields.io/badge/code-MIT-green.svg)](#data-models--licensing)
[![Corpus: CC BY 3.0](https://img.shields.io/badge/corpus-CC%20BY%203.0-lightgrey.svg)](DATA_ATTRIBUTION.md)
[![Status: Phase 9 · database](https://img.shields.io/badge/status-Phase%209%20·%20database-orange.svg)](CLAUDE.md)

</div>

---

OIKONOMIA reads the ~68,000 documentary papyri of Greco-Roman Egypt — tax
receipts, leases, loans, wage lists, census returns, private letters — and turns
them into a **structured, auditable database of everyday economic life**. Every
extracted fact traces back to a character span in a specific document at a pinned
corpus revision, so a historian can always open the papyrus and check it.

It is the first attempt to automate, at corpus scale, the information extraction
that economic historians have done by hand, one document at a time — spanning a
millennium from the Ptolemies through Roman, Byzantine, and early-Islamic Egypt.

## Results so far

| | |
|---|---|
| 📜 **Corpus parsed** | **67,980** documents, EpiDoc parse rate **1.000** |
| 🏷️ **Entity extraction** | strict F1 **0.737** / relaxed **0.837** (papyri-adapted GreBerta, 5-fold CV) |
| 🔗 **Relation extraction** | micro F1 **0.713** on the economic core |
| 🗂️ **Economic database** | **195,906** monetary facts, **99%** normalized, **100%** traceable to a source span |
| ✅ **Historically validated** | 2ᶜ AD wheat ≈ 12 dr/artaba (published: ~7–8) · the silver→gold monetization shift recovered *unsupervised* |

The database already spans **227 distinct places** (linked to the [Pleiades](https://pleiades.stoa.org/)
gazetteer) across nine centuries, with viable long-run price series for wheat,
wine, oil, and barley, and named taxes (the *laographia* poll tax, the *demosia*
land taxes) tracked over time and region.

## How it works

```mermaid
flowchart LR
    A[papyri/idp.data<br/>EpiDoc XML · CC BY 3.0] --> B[Ingest<br/>dual-view parser]
    B --> C[(corpus.parquet<br/>+ HGV dates · Pleiades places<br/>· decoded numerals)]
    C --> D[Extract<br/>lexicon + DAPT'd GreBerta<br/>entities & relations]
    D --> E[Assemble<br/>normalize money · walk the<br/>relation graph · join metadata]
    E --> F[(monetary.parquet<br/>queryable economic facts<br/>with span-level provenance)]
    F --> G[Findings<br/>prices · taxes · monetization]
```

Two principles hold the design together:

- **The model is a means, not the goal.** Entity recall and the genuinely
  ambiguous economic relations are learned; everything deterministic — monetary
  normalization, dates, place-linking, adjacency — is done by *auditable rules*,
  because a queryable historical record must be checkable, not black-box.
- **Provenance is structural.** Raw data is immutable and pinned to a git
  revision; every derived fact carries `(document, character span)` so nothing is
  un-sourceable.

## What's in the box

Three deliverables:

1. **Open models** — a papyri-adapted Greek entity + relation extraction family,
   built on [GreBerta](https://huggingface.co/bowphs/GreBerta) with domain-adaptive
   pretraining on the corpus.
2. **A derived database** — every transaction traceable to a span in a specific
   document at a specific corpus revision.
3. **Historical findings** — price and wage series across a millennium, the
   structure of taxation, monetization, women as economic principals.

## Quickstart

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"

# Pin a corpus revision, then sync + build the processed table (~85s).
uv run oik ingest sync  --set ingest.idp_git_rev=<commit-sha>
uv run oik ingest build

# Assemble the economic database and print a validation view.
uv run oik db build            # → data/processed/db/monetary.parquet
```

## Example: query the economic database

```python
import pandas as pd

df = pd.read_parquet("data/processed/db/monetary.parquet")

# Median wheat price (drachmas per artaba) by century — silver system only,
# never mixing the non-convertible Byzantine gold coinage.
wheat = df[(df.commodity_id == "wheat") & (df.system == "silver")
           & df.unit_price_base.notna() & (df.unit_id == "artaba")]
print(wheat.groupby("century").unit_price_base.median())

# Every row is auditable: open the papyrus and check the span.
print(wheat[["tm_id", "amount_start", "amount_end", "date_lo", "place_pleiades"]].head())
```

## Project layout

```
src/oikonomia/     pure-Python library — no Modal, no GPU deps; testable on a laptop
  ├─ ingest/       EpiDoc XML → corpus.parquet (dual text views, HGV metadata, numerals)
  ├─ labeling/     lexicon matcher + weak/silver labelers + apposition rules
  ├─ ner/ relations/  entity & relation encoders (model-side lives in modal_app/)
  └─ db/           Phase 9 — monetary/date normalization → queryable fact table
modal_app/         thin Modal orchestration (training); imports the library, never vice versa
resources/         curated knowledge (lexicons, genre map, schema) — reviewed as code
configs/           layered YAML configuration (local | modal)
data/              tiered by mutability; only data/gold and data/.manifests are tracked
docs/              architecture, per-phase write-ups, decision records, fact ledger
tests/             progressive tests — hand-computed fixtures over real EpiDoc
```

`CLAUDE.md` is the living project log: current state, phase history, and the
load-bearing facts never to re-derive.

## Status

| Phase | | |
|---|---|---|
| 0–4 | Foundation · Ingestion · Schema · Splits · **DAPT** | ✅ |
| 5–6 | Gold annotation (115 docs) · Silver labeling | ✅ |
| 7–8 | Entity NER (0.737) · Relation extraction (0.713) | ✅ frozen |
| **9** | **Corpus → queryable database** | 🔶 active |
| 10–11 | Historical findings · model release | ⬜ next |

## Data, models & licensing

- **Code** — MIT (this repository).
- **Corpus & derived data** — [Duke Databank of Documentary Papyri](https://papyri.info)
  + [HGV](https://aquila.zaw.uni-heidelberg.de/) metadata, via
  [`papyri/idp.data`](https://github.com/papyri/idp.data), **CC BY 3.0**. See
  [`DATA_ATTRIBUTION.md`](DATA_ATTRIBUTION.md).
- **Models** — backbone and release licence lineage tracked in
  [`MODEL_LICENSES.md`](MODEL_LICENSES.md).

## Citation

If you use OIKONOMIA, please cite it — see [`CITATION.cff`](CITATION.cff).
