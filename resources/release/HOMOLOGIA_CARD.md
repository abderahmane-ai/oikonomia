---
license: apache-2.0
language:
- grc
base_model: bowphs/GreBerta
base_model_relation: finetune
inference: false
tags:
- relation-extraction
- re
- information-extraction
- ancient-greek
- greek-re
- papyrology
- epigraphy
- classics
- classical-studies
- digital-humanities
- economic-history
- pytorch
- greberta
metrics:
- f1
- precision
- recall
model-index:
- name: OIKONOMIA-Homologia
  results:
  - task:
      type: relation-extraction
      name: Relation Extraction
    metrics:
    - type: f1
      name: relation micro F1 (5-fold CV, gold entities)
      value: 0.713
    - type: precision
      name: relation micro precision (5-fold CV, gold entities)
      value: 0.758
    - type: recall
      name: relation micro recall (5-fold CV, gold entities)
      value: 0.673
    - type: f1
      name: PARTY_OF F1, end-to-end (model-predicted entities)
      value: 0.623
---

# OIKONOMIA-Homologia — Relation Extraction for Greek Documentary Papyri

> **ὁμολογία** *homología*, "the acknowledgment" — the contract formula that binds
> parties to a deal. It is the most common transaction word in the corpus this
> model was trained on (ὁμολογῶ and its forms, ~3,000 attestations).

A span-pair relation-extraction model that turns tagged entities in a documentary
papyrus into the **structure of a transaction**: who is a party to the deal, who
paid whom, which amount prices which commodity, which measure attaches to which
quantity, which tax a payment discharges.

It is the relation arm of **OIKONOMIA**, a project turning the ~68,000 Duke
Databank (DDbDP) papyri into a structured, auditable database of ancient economic
life. It runs **on top of**
[**OIKONOMIA-Grammateus**](https://huggingface.co/ainouche-abderahmane/grammateus) —
Grammateus finds the spans, Homologia links them. At corpus scale the pair
produced **228,945 relations over 61,249 documents**, including 16,315 `PARTY_OF`
edges, which became the published
[OIKONOMIA-DB](https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db).

> ⚠️ **This is not a `transformers` `AutoModel`.** The head is custom, so the
> checkpoint is a PyTorch `state_dict` (`relation_head.pt`) plus a `config.json`
> describing how to rebuild it. See [How to Get Started](#how-to-get-started) —
> you need the OIKONOMIA package, not just `from_pretrained`.

---

## Model Details

### Model Description

- **Developed by:** Abderahmane Ainouche (OIKONOMIA project)
- **Model type:** SpERT-style span-pair relation classifier over a RoBERTa encoder
- **Language:** Ancient Greek (`grc`) — documentary, not literary
- **Licence:** apache-2.0, inherited from the encoder
- **Encoder:** [`bowphs/GreBerta`](https://huggingface.co/bowphs/GreBerta) + domain-adaptive pretraining on the papyri corpus
- **Parameters:** 129.1M · **Context:** 512 tokens
- **Output space:** 12 classes (11 relations + `NO_RELATION`) over 13 entity endpoint types

### Architecture

Per candidate entity pair the head sees:

- max-pooled **head** and **tail** span representations,
- the text **between** the two spans,
- a **wide left context** reaching back before the payer, where the direction verb
  lives in Greek contract formulae,
- the **CLS** state of the window,
- learned **entity-type embeddings** (`type_dim` 64) and pair features
  (`feat_dim` 16),

with dropout 0.2, and decoding masked by a **schema constraint** (which entity-type
pairs may hold which relation).

### Model Sources

- **Repository:** https://github.com/abderahmane-ai/oikonomia
- **Sibling model:** [OIKONOMIA-Grammateus](https://huggingface.co/ainouche-abderahmane/grammateus) (entities)
- **Dataset produced with it:** [OIKONOMIA-DB](https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db)

---

## Uses

### Direct Use

Structured information extraction over **documentary** Ancient Greek — contracts,
receipts, leases, loans, sales, tax payments — to populate an economic database.
Built for research in papyrology, digital humanities and ancient economic history.

### Out-of-Scope Use

- **Standalone use.** It classifies pairs of *given* spans. Without an entity
  model it does nothing.
- **Payment direction as fact.** `PAID_BY` scores F1 0.145. Treat a predicted
  direction as a hypothesis; we exclude it from the published database entirely.
- **Literary Greek, epigraphy, or Modern Greek.**
- **Dense registers.** Candidate generation is quadratic in entity count; giant
  lists (hundreds of entities) need a cap. The corpus run skips 35 such documents
  by design.

---

## How to Get Started

```bash
pip install git+https://github.com/abderahmane-ai/oikonomia
```

```python
from oikonomia.relations.model import load_homologia

model, cfg = load_homologia("ainouche-abderahmane/homologia")
# 129.1M params, eval mode, 12 relation labels over 13 entity types
```

Point it at a directory to load files you already have:

```python
model, cfg = load_homologia("./homologia", device="cuda")
```

The loader rebuilds the architecture by pulling `bowphs/GreBerta` from the Hub,
then loads this checkpoint over it with `strict=True` — **every** weight, encoder
included, is replaced by the papyri-adapted one. First load therefore needs network
access to the base repo. The `transformers` "newly initialized pooler" notice
during that step is expected and harmless: the pooler is overwritten from the
checkpoint a moment later, and `strict=True` would fail if anything were left
uninitialised.

Candidate construction — which entity pairs to score, how to window a document
longer than 512 tokens, how to fold per-window scores into one edge per pair —
lives in `oikonomia.relations.infer` and `oikonomia.relations.encode` in the same
package. **Scoring raw pairs without that logic will not reproduce these numbers:**
the schema mask and the window merge are part of the model's decode.

### Relation labels

| Relation | Links | Reads as | Gold edges |
|---|---|---|---:|
| `HAS_CURRENCY` | MONEY_AMOUNT → CURRENCY | the denomination of the sum | 173 |
| `HAS_UNIT` | QUANTITY → UNIT | the measure the quantity is counted in | 154 |
| `PARTY_OF` | PERSON / PERSON_ROLE → TRANSACTION | X is a party to this deal | 147 |
| `HAS_QUANTITY` | COMMODITY → QUANTITY | how much of the good | 88 |
| `PAID_BY` | MONEY_AMOUNT → PERSON | this sum was paid *by* X | 44 |
| `PAID_TO` | MONEY_AMOUNT → PERSON | this sum was paid *to* X | 43 |
| `DATED_TO` | TRANSACTION → DATE_REF | when the act is dated | 32 |
| `HAS_PRICE` | COMMODITY → MONEY_AMOUNT | this sum is the price of that good | 16 |
| `CHARGED_UNDER` | MONEY_AMOUNT → TAX_TERM | the named tax this payment discharges | 13 |
| `HAS_AGE` | PERSON → AGE | a stated age | **0** |
| `HAS_OCCUPATION` | PERSON → OCCUPATION | a stated trade | **0** |

> **`HAS_AGE` and `HAS_OCCUPATION` have no gold supervision.** They were added to
> the label space from apposition rules after the evaluation below was run, so they
> are trained on silver only and **are not scored anywhere on this card**. They are
> predictable but unmeasured — treat them accordingly. The "gold edges" column is
> the count in the 115-document gold set (710 relations total) and is the single
> best predictor of which relations work.

Entity endpoints (13): `AGE`, `COMMODITY`, `CURRENCY`, `DATE_REF`, `FRACTION`,
`MONEY_AMOUNT`, `OCCUPATION`, `PERSON`, `PERSON_ROLE`, `QUANTITY`, `TAX_TERM`,
`TRANSACTION`, `UNIT`.

---

## Training Details

### Training Data

- **Corpus:** the Duke Databank of Documentary Papyri via
  [`papyri/idp.data`](https://github.com/papyri/idp.data), **CC BY 3.0**, pinned to
  revision `d7a34f302d1e44e271256092c2b780733187b478`. Not available as a Hub
  dataset; it is EpiDoc XML in a git repository.
- **The papyri carry no relation markup upstream.** All supervision was built for
  this project:
  - **Silver:** a deterministic lexicon + rules labeler over **48,891** documents.
  - **Gold:** **115 documents, fully human-annotated** — 710 relations, including
    **87 hand-adjudicated payment-direction edges** (adjudicated by verb class, not
    by grammatical case).

### Training Procedure

Silver pretraining of the span-pair head, then gold fine-tuning, over the
DAPT-adapted encoder.

#### Training Hyperparameters

| | Stage 1 (silver) | Stage 2 (gold) |
|---|---|---|
| Learning rate | 3e-5 | 3e-5 |
| Schedule | linear, warmup ratio 0.06 | linear, warmup ratio 0.06 |
| Steps / epochs | 2,000 steps | 20 epochs |
| Batch size | 8 documents | 8 documents |
| Max sequence length | 512 | 512 |
| Loss | cross-entropy | cross-entropy |
| Optimizer | AdamW | AdamW |
| Seed | 17 | 17 |

Head configuration: `type_dim` 64, `feat_dim` 16, dropout 0.2, schema-constrained
decoding on, `NO_RELATION` class weight 1.0 (reweighting it was tested and made no
difference).

#### Compute

Single NVIDIA A10 (24 GB) on [Modal](https://modal.com). Emissions were not
tracked; a run of this size is on the order of GPU-hours, not GPU-days.

---

## Evaluation

### Testing Data, Factors & Metrics

5-fold cross-validation on the 115-document gold set. Two regimes, and the
difference between them is the most important thing on this card:

- **Oracle** — scored with **gold entity spans**, isolating the relation model
  from entity errors. Every relation-extraction paper reports this; it flatters.
- **End-to-end** — scored on spans predicted by
  [Grammateus](https://huggingface.co/ainouche-abderahmane/grammateus), which is
  how you will actually use it.

Metric is micro-averaged F1 over typed, directed entity pairs.

### Results — oracle entities

| Stage | Micro F1 | Precision | Recall |
|---|---|---|---|
| Nearest-pair heuristic baseline | 0.443 | 0.299 | 0.852 |
| Silver only | 0.655 | 0.699 | 0.617 |
| **Silver → gold fine-tune (this model)** | **0.713** | **0.757** | **0.673** |

**Per-relation F1 (oracle):**

| Relation | F1 | | Relation | F1 |
|---|---|---|---|---|
| `HAS_CURRENCY` | 0.883 | | `CHARGED_UNDER` | 0.375 |
| `HAS_UNIT` | 0.874 | | `DATED_TO` | 0.369 |
| `HAS_QUANTITY` | 0.744 | | `PAID_TO` | 0.300 |
| `PARTY_OF` | 0.652 | | `PAID_BY` | 0.145 |
| `HAS_PRICE` | 0.444 | | | |

### Results — end-to-end (quote these)

Run on Grammateus-predicted entities. The join between the two models is clean
(0 documents unmatched).

| | Micro F1 | Precision | Recall |
|---|---|---|---|
| **Overall, end-to-end** | **0.609** | 0.771 | 0.503 |

| Relation | Oracle | End-to-end | |
|---|---|---|---|
| `PARTY_OF` | 0.705 † | **0.623** | the edge the database rides on |
| `PAID_TO` | 0.300 | 0.507 | |
| `PAID_BY` | 0.145 | 0.231 | still too weak to use |
| `HAS_PRICE` | 0.444 | **0.000** | entity model rarely supplies `COMMODITY` |
| `CHARGED_UNDER` | 0.375 | **0.000** | entity model rarely supplies `TAX_TERM` |
| `HAS_CURRENCY`, `HAS_UNIT`, `HAS_QUANTITY`, `DATED_TO` | see above | *not recorded per-relation* | |

† `PARTY_OF` oracle from the all-gold `launch` run's held-out CV — the honest
generalization number for the shipped checkpoint — rather than the 0.652 in the
table above, which is from the earlier paired-CV run.

**The entity cascade costs ≈ 8 points on `PARTY_OF`** (0.705 → 0.623). Note that
recall, not precision, is what collapses end-to-end (P 0.771 / R 0.503): the model
is still right about what it asserts, but the entity stage never hands it some of
the pairs.

Four relations were not broken out individually in the end-to-end run and are
reported only inside the 0.609 overall. That is a gap in the record.

#### One number deliberately not quoted

Scoring the shipped all-gold checkpoint on the gold documents gives `PARTY_OF`
0.993. **That is train-on-test** — those documents are in its training set — and it
is reported here only because it confirms the save/load and constrained-decode
inference path works end to end. It is not a generalization estimate. The 0.623 is
itself mildly optimistic for the same reason, so true corpus-wide `PARTY_OF` is
likely a shade under 0.62.

---

## Bias, Risks, and Limitations

- **Payment direction is weak, and this is data scarcity, not a bug.** `PAID_BY`
  (0.145) and `PAID_TO` (0.300) sit far below the adjacency relations. The gold set
  holds only 87 direction edges — about 17 per held-out fold — and *every*
  model-side remedy tried (direction features, wide context, constrained decoding)
  measured neutral or slightly negative. We act on this: **direction is
  deliberately absent from the published OIKONOMIA-DB.** There are no
  `paid_by`/`paid_to` columns, because shipping them at F1 0.145 would be shipping
  noise as data.
- **Rare relations collapse end-to-end.** `HAS_PRICE` and `CHARGED_UNDER` fall to
  0.0 with predicted entities, because the entity model rarely supplies their
  `COMMODITY`/`TAX_TERM` endpoints. The adjacency relations (`HAS_UNIT`,
  `HAS_CURRENCY`) are the robust ones. Performance is stratified by relation, not
  uniform — read the per-relation table before relying on any single edge type.
- **Two relations are unmeasured.** `HAS_AGE` and `HAS_OCCUPATION` have no gold
  supervision and no score.
- **Errors are not uniform across documents.** Formulaic contracts, which follow a
  fixed Greek template, are much easier than free-form letters and accounts. A
  corpus-wide average understates the first and overstates the second.
- **Downstream social inference is not this model's claim.** OIKONOMIA-DB combines
  `PARTY_OF` edges with rule-based gender attribution to study women as economic
  principals. Those are aggregate, error-bounded historical claims layered on top
  of this model, not assertions it makes about individuals.
- **Corpus bias is inherited** — *surviving, published, digitized* papyri, skewed
  toward the Arsinoite nome and dry sites.

### Recommendations

Report end-to-end numbers, not oracle ones, if you build on this. Use the
`PARTY_OF`/adjacency edges; treat direction as a hypothesis to verify. Prefer
relative contrasts across periods, regions or document types to absolute counts,
since extraction error is roughly common-mode across buckets.

---

## Licence & lineage

Released under **apache-2.0**, inherited from the `bowphs/GreBerta` encoder
(apache-2.0). The training corpus (DDbDP) is **CC BY 3.0** and must be attributed.
No ancestor carries a NonCommercial term — deliberately: the release is gated in
code by a licence firewall that refuses any artifact of NonCommercial or unverified
lineage (`oikonomia.models.licensing`; audit trail in `MODEL_LICENSES.md`).

## Citation

```bibtex
@misc{oikonomia_homologia_2026,
  title  = {{OIKONOMIA-Homologia}: Relation Extraction for Greek Documentary Papyri},
  author = {Ainouche, Abderahmane},
  year   = {2026},
  url    = {https://huggingface.co/ainouche-abderahmane/homologia},
  note   = {Encoder bowphs/GreBerta; trained on the Duke Databank (DDbDP, CC BY 3.0)}
}

@inproceedings{riemenschneider-frank-2023-exploring,
  title     = {Exploring Large Language Models for Classical Philology},
  author    = {Riemenschneider, Frederick and Frank, Anette},
  booktitle = {Proceedings of ACL 2023},
  year      = {2023},
  url       = {https://arxiv.org/abs/2305.13698}
}
```

Duke Databank of Documentary Papyri (DDbDP), Duke Collaboratory for Classics
Computing (DC3) and papyri.info, CC BY 3.0.

## Model Card Contact

Issues and corrections: https://github.com/abderahmane-ai/oikonomia/issues
