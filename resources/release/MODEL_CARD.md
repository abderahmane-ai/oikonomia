---
license: apache-2.0
language:
- grc
library_name: transformers
pipeline_tag: token-classification
base_model: bowphs/GreBerta
tags:
- token-classification
- named-entity-recognition
- ancient-greek
- papyrology
- digital-humanities
- economic-history
datasets:
- papyri/DDbDP
metrics:
- f1
model-index:
- name: OIKONOMIA-NER
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

# OIKONOMIA-NER — Named Entity Recognition for Greek Documentary Papyri

A token-classification model that reads the everyday economic language of the
documentary papyri of Greco-Roman Egypt — tax receipts, leases, loans, wages,
sales, census returns — and tags the entities an economic historian extracts by
hand: people, places, money, commodities, units, taxes, dates, ages, occupations.

It is the entity-extraction arm of **OIKONOMIA**, a project turning the ~68,000
Duke Databank (DDbDP) papyri into a structured, auditable database of ancient
economic life. This is deliverable #1: an open model for a low-resource language
with essentially no prior NER supervision.

- **Base model:** [`bowphs/GreBerta`](https://huggingface.co/bowphs/GreBerta)
  (RoBERTa-base, Ancient Greek, apache-2.0) + **domain-adaptive pretraining
  (DAPT)** on the papyri corpus (full fine-tune).
- **Architecture:** RoBERTa-base encoder + token-classification head, 512 context,
  case-preserving 52k-token vocabulary.
- **Task:** BIO tagging over 15 economic entity types.

## Entity labels (15)

| Label | What it marks |
|---|---|
| `PERSON` | personal names (name + patronymic as written) |
| `PLACE` | toponyms (villages, nomes, cities) |
| `MONEY_AMOUNT` | a monetary quantity |
| `CURRENCY` | denomination (drachma, obol, talent, nomisma, …) |
| `COMMODITY` | traded goods (wheat, wine, oil, barley, …) |
| `QUANTITY` | a counted/measured amount |
| `UNIT` | measure (artaba, aroura, …) |
| `FRACTION` | fractional numerals |
| `PRICE_TERM` | pricing vocabulary (τιμή, …) |
| `TAX_TERM` | named taxes (laographia, demosia, …) |
| `TRANSACTION` | the act (sale, lease, loan, receipt) |
| `OCCUPATION` | professions / trades |
| `PERSON_ROLE` | a party by role (lessor, creditor, …) |
| `DATE_REF` | dating expressions (regnal year, month) |
| `AGE` | stated ages |

## Evaluation

5-fold cross-validation on **115 fully human-validated gold documents** (2,995
entities), cross-entropy loss. "Strict" requires an exact span+label match;
"relaxed" credits an overlapping span of the right label.

| | Strict micro F1 | Relaxed micro F1 |
|---|---|---|
| Silver only (no gold fine-tune) | 0.654 | 0.753 |
| **Silver → gold fine-tune (this model)** | **0.737** | **0.837** |

**Per-label strict F1** (selected):

| Label | F1 | | Label | F1 |
|---|---|---|---|---|
| `AGE` | 0.974 | | `MONEY_AMOUNT` | 0.758 |
| `PRICE_TERM` | 0.929 | | `OCCUPATION` | 0.746 |
| `FRACTION` | 0.863 | | `QUANTITY` | 0.744 |
| `UNIT` | 0.841 | | `DATE_REF` | 0.690 |
| `CURRENCY` | 0.822 | | `PLACE` | 0.650 |
| `PERSON` | 0.775 | | `TRANSACTION` | 0.602 |

**Domain-adaptive pretraining pays off.** Against an identical fine-tune on the raw
backbone (no papyri DAPT), DAPT adds **+9.5 strict F1** overall, concentrated in the
open-class onomastic labels the adaptation was meant to help: **PERSON +19.0**,
**PLACE +11.4** — with no label regressing.

## Intended use

```python
from transformers import AutoTokenizer, AutoModelForTokenClassification
import torch

repo = "<your-org>/oikonomia-ner"  # set to the published repo id
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

Built for **information extraction over documentary (not literary) Ancient Greek**,
to populate a structured economic database. Well suited to research in papyrology,
digital humanities, and ancient economic history.

## Limitations

- **Domain-specific.** Trained on documentary papyri; not intended for literary
  Greek, epigraphy, or Modern Greek.
- **Label ceilings are consistency-bound.** `TRANSACTION`, `PERSON_ROLE` and
  `TAX_TERM` are open, formulaic classes whose ceiling is annotation *consistency*,
  not data volume.
- **Collapsed persons.** A `PERSON` span is the name as written — often name +
  patronymic together; it does not split the individuals for kinship.
- **Fragmentary text.** Papyri carry lacunae and editorial marks; very broken
  passages degrade accuracy.
- **Not a normalizer.** It finds spans; mapping surface forms to canonical
  currency/commodity/unit ids is done downstream by the OIKONOMIA lexicon.

## Training data & provenance

- **Corpus:** the Duke Databank of Documentary Papyri (DDbDP) via
  [`papyri/idp.data`](https://github.com/papyri/idp.data), **CC BY 3.0** — pinned
  to a specific corpus revision.
- **Supervision:** the papyri carry **no entity markup upstream**. All labels were
  built for this project: a deterministic lexicon+rules labeler produced *silver*
  over ~49k training documents, and **115 documents were fully human-annotated and
  validated** as gold. The model is silver-pretrained then gold fine-tuned.

## Licence & lineage

Released under **apache-2.0**, inherited from the `bowphs/GreBerta` backbone
(apache-2.0). The training corpus (DDbDP) is **CC BY 3.0** and must be attributed
(see below); no ancestor carries a NonCommercial term. Release is gated in code by
a licence firewall that refuses any artifact of NonCommercial or unverified lineage
(`oikonomia.models.licensing`; audit trail in `MODEL_LICENSES.md`).

## Citation

If you use this model, please cite the OIKONOMIA project, the GreBerta backbone,
and the DDbDP corpus:

```bibtex
@misc{oikonomia_ner,
  title  = {OIKONOMIA-NER: Named Entity Recognition for Greek Documentary Papyri},
  author = {OIKONOMIA project},
  year   = {2026},
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
