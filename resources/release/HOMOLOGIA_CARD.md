---
license: apache-2.0
language:
- grc
base_model: bowphs/GreBerta
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
datasets:
- papyri/DDbDP
metrics:
- f1
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
Databank (DDbDP) papyri of Greco-Roman Egypt into a structured, auditable database
of ancient economic life. It is designed to run **on top of**
[**OIKONOMIA-Grammateus**](https://huggingface.co/oikonomia/grammateus-grc), the
entity model — Grammateus finds the spans, Homologia links them.

- **Encoder:** [`bowphs/GreBerta`](https://huggingface.co/bowphs/GreBerta)
  (RoBERTa-base, Ancient Greek, apache-2.0) + domain-adaptive pretraining on the
  papyri corpus.
- **Head:** a SpERT-style span-pair classifier. Per candidate pair it sees the
  max-pooled head and tail span representations, the text *between* them, a wide
  left context reaching before the payer (where the direction verb lives), the CLS
  state, and learned entity-type embeddings.
- **Training:** silver pretraining over ~49k weakly-labelled documents, then
  fine-tuning on 115 fully human-annotated gold documents (710 relations).

> ⚠️ **This is not a `transformers` `AutoModel`.** The head is custom, so the
> checkpoint is a PyTorch `state_dict` (`relation_head.pt`) plus a `config.json`
> that describes how to rebuild it. See [Loading](#loading) — you need the
> OIKONOMIA code, not just `from_pretrained`.

## Relation labels (11 + NO_RELATION)

| Relation | Links | Reads as |
|---|---|---|
| `PARTY_OF` | PERSON / PERSON_ROLE → TRANSACTION | X is a party to this deal |
| `PAID_BY` | MONEY_AMOUNT → PERSON | this sum was paid *by* X |
| `PAID_TO` | MONEY_AMOUNT → PERSON | this sum was paid *to* X |
| `HAS_CURRENCY` | MONEY_AMOUNT → CURRENCY | the denomination of the sum |
| `HAS_PRICE` | COMMODITY → MONEY_AMOUNT | this sum is the price of that good |
| `HAS_QUANTITY` | COMMODITY → QUANTITY | how much of the good |
| `HAS_UNIT` | QUANTITY → UNIT | the measure the quantity is counted in |
| `CHARGED_UNDER` | MONEY_AMOUNT → TAX_TERM | the named tax this payment discharges |
| `DATED_TO` | TRANSACTION → DATE_REF | when the act is dated |
| `HAS_AGE` | PERSON → AGE | a stated age |
| `HAS_OCCUPATION` | PERSON → OCCUPATION | a stated trade |

Entity endpoints (13): `AGE`, `COMMODITY`, `CURRENCY`, `DATE_REF`, `FRACTION`,
`MONEY_AMOUNT`, `OCCUPATION`, `PERSON`, `PERSON_ROLE`, `QUANTITY`, `TAX_TERM`,
`TRANSACTION`, `UNIT`.

## Evaluation

5-fold cross-validation on the 115-document gold set, **with gold entity spans**
("oracle") — this isolates the relation model from entity errors.

| Stage | Micro F1 | Precision | Recall |
|---|---|---|---|
| Nearest-pair heuristic baseline | 0.443 | 0.299 | 0.852 |
| Silver only | 0.655 | 0.699 | 0.617 |
| **Silver → gold fine-tune (this model)** | **0.713** | **0.757** | **0.673** |

**Per-relation F1 (oracle entities):**

| Relation | F1 | | Relation | F1 |
|---|---|---|---|---|
| `HAS_CURRENCY` | 0.883 | | `CHARGED_UNDER` | 0.375 |
| `HAS_UNIT` | 0.874 | | `DATED_TO` | 0.369 |
| `HAS_QUANTITY` | 0.744 | | `PAID_TO` | 0.300 |
| `PARTY_OF` | 0.652 | | `PAID_BY` | 0.145 |
| `HAS_PRICE` | 0.444 | | | |

### The number that matters in practice: end-to-end

Oracle scores flatter every relation model. Run on entities predicted by
Grammateus rather than gold ones — the way you will actually use it — the cascade
costs about 8 points on the key edge:

| `PARTY_OF` | F1 |
|---|---|
| Held-out oracle (5-fold CV, gold entities) | 0.705 |
| **End-to-end, on predicted entities** | **0.623** |

Overall end-to-end relation F1 is 0.609 (P 0.771 / R 0.503). **Report end-to-end
numbers if you build on this**, not the oracle ones.

## Loading

```python
import json, torch
from modal_app.relations import build_relation_head   # the head factory

cfg = json.load(open("config.json"))
model = build_relation_head(
    backbone=cfg["reconstruct_backbone"],
    n_entity_labels=len(cfg["entity_labels"]),
    n_rel_labels=len(cfg["relation_labels"]),
    type_dim=cfg["type_dim"], feat_dim=cfg["feat_dim"], dropout=cfg["dropout"],
)
model.load_state_dict(torch.load("relation_head.pt", map_location="cpu"))
model.eval()
```

`build_relation_head` instantiates the architecture by pulling `bowphs/GreBerta`
from the Hub, then `load_state_dict` overwrites **every** weight — including the
encoder — with the papyri-adapted ones from this checkpoint. So the first load
needs network access to the base repo, and the transient "newly initialized
pooler" notice from `transformers` is expected: the pooler is unused by this head.

Candidate construction (which entity pairs to score, how to window a document
longer than 512 tokens, how to fold per-window scores into one edge per pair) lives
in `oikonomia.relations.infer` and `oikonomia.relations.encode` in the project
repository. Scoring raw pairs without that logic will not reproduce these numbers:
the schema mask (which entity-type pairs may hold which relation) and the
window-merge are part of the model's decode.

## Intended use

Structured information extraction over **documentary** (not literary) Ancient
Greek, to populate an economic database: contracts, receipts, leases, loans, sales,
tax payments. Built for research in papyrology, digital humanities, and ancient
economic history. At corpus scale it produced 228,945 relations over 61,249
documents, including 16,315 `PARTY_OF` edges — the basis of a published finding on
women as economic principals.

## Limitations

- **Payment direction is weak, and this is honest data scarcity, not a bug.**
  `PAID_BY` (0.145) and `PAID_TO` (0.300) are far below the adjacency relations.
  The gold set holds only 87 direction edges; every model-side remedy tried
  (direction features, wide context, constrained decoding) measured neutral. Treat
  a predicted payment *direction* as a hypothesis, not a fact.
- **Rare relations collapse end-to-end.** `HAS_PRICE` and `CHARGED_UNDER` fall to
  ~0 with predicted entities, because the entity model rarely supplies their
  `COMMODITY` / `TAX_TERM` endpoints. Adjacency relations (`HAS_UNIT`,
  `HAS_CURRENCY`) are the robust ones.
- **Not standalone.** It classifies pairs of *given* spans. Without an entity model
  it does nothing.
- **Dense documents are expensive.** Candidate generation is quadratic in entity
  count; giant registers (hundreds of entities) need a cap. The project skips 35
  such documents corpus-wide by design.
- **Domain-specific.** Documentary papyri only — not literary Greek, epigraphy, or
  Modern Greek.

## Training data & provenance

- **Corpus:** the Duke Databank of Documentary Papyri (DDbDP) via
  [`papyri/idp.data`](https://github.com/papyri/idp.data), **CC BY 3.0**, pinned to
  a specific corpus revision.
- **Supervision:** the papyri carry **no relation markup upstream**. All labels were
  built for this project — a deterministic lexicon+rules labeler produced silver
  over ~49k documents, and 115 documents were fully human-annotated as gold (710
  relations, including 87 hand-adjudicated payment-direction edges).

## Licence & lineage

Released under **apache-2.0**, inherited from the `bowphs/GreBerta` encoder
(apache-2.0). The training corpus (DDbDP) is **CC BY 3.0** and must be attributed;
no ancestor carries a NonCommercial term. Release is gated in code by a licence
firewall that refuses any artifact of NonCommercial or unverified lineage
(`oikonomia.models.licensing`; audit trail in `MODEL_LICENSES.md`).

## Citation

```bibtex
@misc{oikonomia_homologia,
  title  = {OIKONOMIA-Homologia: Relation Extraction for Greek Documentary Papyri},
  author = {OIKONOMIA project},
  year   = {2026},
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
