---
license: apache-2.0
language:
- grc
library_name: transformers
pipeline_tag: token-classification
base_model: bowphs/GreBerta
base_model_relation: finetune
tags:
- token-classification
- named-entity-recognition
- ner
- information-extraction
- ancient-greek
- greek-ner
- papyrology
- epigraphy
- classics
- classical-studies
- digital-humanities
- economic-history
- greberta
metrics:
- f1
widget:
- text: "Αὐρηλία Θεοδώρα θυγάτηρ τοῦ μακαρίου Ἀλεξάνδρου χωρὶς κυρίου χρηματιζούσης τέκνων δικαίῳ ἐν Ἑρμουπόλει. σίτου ἀρτάβας ἑκατόν γίνονται (ἀρτάβαι) ρ, καὶ ἀργυρίου δραχμὰς πεντακισχιλίας."
model-index:
- name: OIKONOMIA-Grammateus
  results:
  - task:
      type: token-classification
      name: Named Entity Recognition
    metrics:
    - type: f1
      name: strict micro F1 (5-fold CV, 115-doc gold)
      value: 0.737
    - type: f1
      name: relaxed micro F1 (5-fold CV, 115-doc gold)
      value: 0.837
---

# OIKONOMIA-Grammateus — Entity Recognition for Greek Documentary Papyri

> **γραμματεύς** *grammateús*, "the scribe" — the village clerk of Greco-Roman
> Egypt, whose job was to write down who, where, and how much.

A token-classification model that reads the everyday economic language of the
documentary papyri of Greco-Roman Egypt — tax receipts, leases, loans, wages,
sales, census returns — and tags the entities an economic historian extracts by
hand: people, places, money, commodities, units, taxes, dates, ages, occupations.

It is the entity arm of **OIKONOMIA**, a project turning the ~68,000 Duke Databank
(DDbDP) papyri into a structured, auditable database of ancient economic life. Run
over the whole corpus it produced **1,368,079 entities across 61,249 documents**,
which became the published [OIKONOMIA-DB](https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db).

---

## Model Details

### Model Description

- **Developed by:** Abderahmane Ainouche (OIKONOMIA project)
- **Model type:** RoBERTa-base encoder + token-classification head (BIO tagging)
- **Language:** Ancient Greek (`grc`) — documentary, not literary
- **Licence:** apache-2.0, inherited from the backbone
- **Base model:** [`bowphs/GreBerta`](https://huggingface.co/bowphs/GreBerta) + domain-adaptive pretraining (DAPT) on the papyri corpus
- **Parameters:** 125.4M · **Context:** 512 tokens · **Vocabulary:** 52k, case-preserving
- **Labels:** 15 entity types → 31 BIO tags

Case preservation matters here and drove the backbone choice: capitalisation is the
strongest single cue for `PERSON` and `PLACE` in this corpus, and keeping it costs
only ~0.6% more tokens.

### Model Sources

- **Repository:** https://github.com/abderahmane-ai/oikonomia
- **Sibling model:** [OIKONOMIA-Homologia](https://huggingface.co/ainouche-abderahmane/homologia) (relations)
- **Dataset produced with it:** [OIKONOMIA-DB](https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db)

---

## Uses

### Direct Use

Information extraction over **documentary** Ancient Greek: tagging the entities in
a papyrus so they can be normalized, linked and counted. Suited to papyrology,
digital humanities, and ancient economic history.

### Downstream Use

Designed to feed [OIKONOMIA-Homologia](https://huggingface.co/ainouche-abderahmane/homologia),
which links the tagged spans into transactions. Run Grammateus first, pass its
spans to Homologia. Also a reasonable starting point for fine-tuning on other
documentary Greek annotation schemes.

### Out-of-Scope Use

- **Literary Greek, epigraphy, or Modern Greek.** The domain adaptation is
  specifically to documentary papyri; performance elsewhere is unmeasured.
- **As a normalizer.** It finds spans. Mapping surface forms to canonical
  currency/commodity/unit ids is a separate lexicon step.
- **As a person disambiguator.** A `PERSON` span is the name as written, often
  name + patronymic together; it does not resolve who that individual is.

---

## How to Get Started

```python
from transformers import AutoTokenizer, AutoModelForTokenClassification
import torch

repo = "ainouche-abderahmane/grammateus"
tok = AutoTokenizer.from_pretrained(repo)
model = AutoModelForTokenClassification.from_pretrained(repo).eval()

text = "πυροῦ ἀρτάβας δύο δραχμῶν ἑκατόν"  # "two artabas of wheat, a hundred drachmas"
enc = tok(text, return_tensors="pt", return_offsets_mapping=True)
offsets = enc.pop("offset_mapping")[0]
with torch.no_grad():
    pred = model(**enc).logits[0].argmax(-1)

for (s, e), p in zip(offsets.tolist(), pred.tolist()):
    if e > s:
        print(text[s:e], model.config.id2label[p])
```

Documents longer than 512 tokens must be windowed; the corpus run used a strided
window with span-offset remapping (`oikonomia.ner.inference`).

### Entity labels (15)

| Label | What it marks |
|---|---|
| `PERSON` | personal names (name + patronymic as written) |
| `PLACE` | toponyms (villages, nomes, cities) |
| `MONEY_AMOUNT` | a monetary quantity |
| `CURRENCY` | denomination (drachma, obol, talent, nomisma, …) |
| `COMMODITY` | traded goods (wheat, wine, oil, barley, …) |
| `QUANTITY` | a counted / measured amount |
| `UNIT` | measure (artaba, aroura, metretes, …) |
| `FRACTION` | fractional numerals |
| `PRICE_TERM` | pricing vocabulary (τιμή, …) |
| `TAX_TERM` | named taxes (laographia, demosia, …) |
| `TRANSACTION` | the act (sale, lease, loan, receipt) |
| `OCCUPATION` | professions / trades |
| `PERSON_ROLE` | a party named by role (lessor, creditor, …) |
| `DATE_REF` | dating expressions (regnal year, month) |
| `AGE` | stated ages |

---

## Training Details

### Training Data

- **Corpus:** the Duke Databank of Documentary Papyri via
  [`papyri/idp.data`](https://github.com/papyri/idp.data), **CC BY 3.0**, pinned to
  revision `d7a34f302d1e44e271256092c2b780733187b478`. Not available as a Hub
  dataset; it is EpiDoc XML in a git repository.
- **The papyri carry no entity markup upstream** (0% over a 200-document audit).
  All supervision was built for this project:
  - **Silver:** a deterministic lexicon + rules labeler over **48,891 training
    documents** (measured against gold at micro F1 0.667).
  - **Reference set:** **115 documents** — 2,995 entities. Model-drafted and
    model-re-checked, not expert-validated; see the provenance note below.
- Splits are leak-free: near-duplicate clusters (2.89% of the corpus) and
  TM-sibling documents are grouped before assignment, so no document's near-twin
  sits across the split boundary.

### Training Procedure

Three stages: DAPT, then silver pretraining, then gold fine-tuning.

**Stage 0 — domain-adaptive pretraining.** Full fine-tune of GreBerta on the
papyri corpus (8.25M train / 1.10M dev tokens), masked-LM objective. Full-FT beat
head-only and adapter variants (dev perplexity 4.54). This checkpoint is the
backbone for everything below.

**Stage 1 — silver pretraining.** Token classification over the 48,891
silver-labelled documents.

**Stage 2 — gold fine-tuning.** The same model fine-tuned on the 115 gold
documents.

#### Training Hyperparameters

| | Stage 1 (silver) | Stage 2 (gold) |
|---|---|---|
| Learning rate | 5e-5 | 3e-5 |
| Schedule | linear, warmup ratio 0.06 | linear, warmup ratio 0.06 |
| Steps / epochs | 2,000 steps | 15 epochs |
| Batch size | 32 | 8 |
| Max sequence length | 512 | 512 |
| Loss | cross-entropy | cross-entropy |
| Optimizer | AdamW | AdamW |
| Precision | bf16 | bf16 |
| Seed | 17 | 17 |

A generalized-cross-entropy loss (GCE, q=0.7) was tried on the silver stage to
absorb label noise and **rejected — it cost 5.7 strict F1.**

#### Compute

Single NVIDIA A10 (24 GB) on [Modal](https://modal.com). Emissions were not
tracked; a run of this size is on the order of GPU-hours, not GPU-days.

---

## Evaluation

### Testing Data, Factors & Metrics

**Testing data.** 5-fold cross-validation over the **115-document reference set**
(2,995 entities). No separate held-out test set exists — the set is small enough
that spending part of it on a test split would make every number noisier than
cross-validation does.

**Note on provenance.** This reference set was drafted by one language model and re-checked span by span by a second, different one. It is mechanically constrained (offsets computed not typed, text byte-identical to the corpus, every numeral either labelled or explicitly skipped with a reason, every relation schema-legal) but **no papyrologist or other domain expert has adjudicated it, and the maintainers do not read Ancient Greek**. Scores below are therefore *agreement with this reference*, not accuracy against expert ground truth. Independent expert annotation is the top outstanding item.

**Metrics.** Micro-averaged span F1, in two regimes: **strict** requires an exact
span *and* label match; **relaxed** credits an overlapping span of the right label.
Relaxed is the fairer read for a downstream normalizer that only needs to find the
right token region.

### Results

| | Strict micro F1 | Relaxed micro F1 |
|---|---|---|
| Silver only (no gold fine-tune) | 0.654 | 0.753 |
| **Silver → gold fine-tune (this model)** | **0.737** | **0.837** |

**Per-label strict F1:**

| Label | F1 | | Label | F1 |
|---|---|---|---|---|
| `AGE` | 0.974 | | `OCCUPATION` | 0.746 |
| `PRICE_TERM` | 0.929 | | `QUANTITY` | 0.744 |
| `FRACTION` | 0.863 | | `DATE_REF` | 0.690 |
| `UNIT` | 0.841 | | `PLACE` | 0.650 |
| `CURRENCY` | 0.822 | | `TRANSACTION` | 0.602 |
| `PERSON` | 0.775 | | `COMMODITY` | *not recorded* |
| `MONEY_AMOUNT` | 0.758 | | `PERSON_ROLE`, `TAX_TERM` | *not recorded* |

> **Three labels are missing, and that is a gap in the record, not a suppression.**
> The cross-validation run logged per-label F1 for 12 of the 15 labels;
> `COMMODITY`, `PERSON_ROLE` and `TAX_TERM` were not captured, and re-deriving them
> honestly requires re-running the 5-fold CV rather than scoring the shipped
> checkpoint (which was trained on all 115 gold documents, so scoring it on them
> would be train-on-test). Expect them to sit at the low end: `PERSON_ROLE` and
> `TAX_TERM` are the two labels named below as consistency-bound.

**Precision and recall were not recorded separately** for the entity model; only
micro F1 at both strictness levels was logged. The sibling relation model reports
full P/R.

#### Domain-adaptive pretraining is what pays

Against an identical fine-tune on the raw backbone with no papyri DAPT (a paired
run on the same folds):

| | No DAPT (control) | **DAPT (this model's backbone)** | Δ |
|---|---|---|---|
| Strict micro F1 | 0.495 | **0.589** | **+9.5** |
| Relaxed micro F1 | 0.663 | 0.719 | +5.6 |
| `PERSON` | 0.458 | **0.648** | **+19.0** |
| `PLACE` | 0.503 | **0.617** | **+11.4** |
| `MONEY_AMOUNT` | 0.575 | 0.634 | +5.8 |

*(This comparison was run at an earlier stage on a 65-document gold set, so the
absolute values are lower than the headline 0.737; the paired contrast is the
result.)* Gains concentrate exactly where predicted — the open-class onomastic
labels — and **no label regressed**. Lexicon-reachable labels barely move
(`CURRENCY` 0.78 → 0.79), which is the expected shape: DAPT buys you the words a
gazetteer cannot enumerate.

#### How much to trust these numbers

115 documents over 5 folds is roughly **23 documents per fold**, so every figure
above is a point estimate on a small sample. The micro totals rest on 2,995
entities and are the sturdiest. **Per-label figures for rare labels rest on far
fewer instances and should be read as indicative of rank, not as precise values** —
ten more annotated documents could move them. **Per-fold variance was not recorded
and is a known gap.** The headline comparisons (DAPT vs no-DAPT, silver-only vs
silver→gold) are paired runs on identical folds, which is what makes their
*direction* reliable at this n.

---

## Bias, Risks, and Limitations

- **Label ceilings are annotation-consistency-bound, not data-bound.**
  `TRANSACTION`, `PERSON_ROLE` and `TAX_TERM` are open, formulaic classes where
  the limit is how consistently a human can draw the span, not how much data the
  model sees. More annotation of the same kind will not lift them much.
- **Fragmentary text degrades accuracy.** Papyri carry lacunae, editorial
  brackets and supplied readings; heavily broken passages are harder for the model
  in the same way they are for a reader.
- **Onomastic bias.** `PERSON` recognition leans on Greek and Egyptian name shapes
  attested in the corpus. Rare, foreign or heavily abbreviated names are recognised
  less reliably, which means the entities this model finds are not a uniform sample
  of the people in the documents.
- **Downstream gender inference is not the model's output.** OIKONOMIA-DB infers
  gender from names and formulae *after* this model tags a span. Those inferences
  are aggregate-level and rule-based, not a claim by this model about an
  individual — see the dataset card.
- **Collapsed persons.** A `PERSON` span is the name as written, frequently name +
  patronymic in one span; splitting individuals for kinship is a downstream step.
- **Corpus bias is inherited.** The training corpus is *surviving, published,
  digitized* papyri — skewed toward the Arsinoite nome and dry sites.

### Recommendations

Report relaxed F1 alongside strict when your downstream step only needs the right
token region. For quantitative history, prefer relative contrasts (across periods,
regions, document types) to absolute totals, since extraction error is roughly
common-mode across buckets but does not cancel in a total.

---

## Licence & lineage

Released under **apache-2.0**, inherited from `bowphs/GreBerta` (apache-2.0). The
training corpus (DDbDP) is **CC BY 3.0** and must be attributed. No ancestor
carries a NonCommercial term — deliberately: the release is gated in code by a
licence firewall that refuses any artifact of NonCommercial or unverified lineage
(`oikonomia.models.licensing`; audit trail in `MODEL_LICENSES.md`).

## Citation

```bibtex
@misc{oikonomia_grammateus_2026,
  title  = {{OIKONOMIA-Grammateus}: Entity Recognition for Greek Documentary Papyri},
  author = {Ainouche, Abderahmane},
  year   = {2026},
  url    = {https://huggingface.co/ainouche-abderahmane/grammateus},
  note   = {Base model bowphs/GreBerta; trained on the Duke Databank (DDbDP, CC BY 3.0)}
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
