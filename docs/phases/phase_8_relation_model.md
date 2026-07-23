# Phase 8 — Relation Extraction Model & OIKONOMIA-RE Plan

### ✅ Phase 8 — Relation model: span-pair RE beats the baseline (F1 0.713, oracle entities)

**RESULT (2026-07-23, `xval --backbone b1 --loss ce`, 5-fold CV on gold docs; oracle entities):**

| Stage | Relation Micro F1 | Precision | Recall |
|---|---|---|---|
| Nearest-pair baseline (`oik relation score`) | 0.443 | 0.299 | 0.852 |
| Silver-only | 0.6552 (65.5%) | 0.6986 (69.9%) | 0.6169 (61.7%) |
| **Silver $\rightarrow$ Gold (CE)** | **0.7129 (71.3%)** 🚀 | **0.7575 (75.8%)** 🔥 | **0.6732 (67.3%)** |

**Per-type Breakdown:**
- `HAS_UNIT`: **0.8738 (87.4%)**
- `HAS_CURRENCY`: **0.8830 (88.3%)**
- `HAS_QUANTITY`: **0.7439 (74.4%)**
- `PARTY_OF`: **0.6517 (65.2%)**
- `HAS_PRICE`: **0.4444 (44.4%)**
- `CHARGED_UNDER`: **0.3750 (37.5%)**
- `DATED_TO`: **0.3692 (36.9%)**
- `PAID_TO`: **0.3000 (30.0%)** (Rescued from 0.0)
- `PAID_BY`: **0.1455 (14.6%)**

---

### 🔶 OIKONOMIA-RE — Maximal Relation-Extraction Program

#### 8a — Accuracy on current 9 types
- Neuro-symbolic direction features: verb-class / verb-position / payer-marking.
- Functional schema constraints (`constrain_decode` in `relations/decode.py`).
- Single-encode SpERT-style neural head in `modal_app/relations.py`.

#### 8b — Schema Expansion (Coverage Win)
- Extend `RELATION_SIGNATURES`: `HAS_OCCUPATION`, `HAS_AGE`, `HAS_STATUS`, `ORIGIN_OF`, `LOCATED_IN`.
- Introduce document-level Virtual `EVENT` node.
- Party role typing and Transaction classification.

#### 8c — Data Engine (Per-Type Silver + BOND)
- Apposition silver rules for local attribute relations.
- BOND self-training across 67,980 corpus documents.

#### 8d — DB Assembly Layer
- Morphological genitive parse for `CHILD_OF` kinship & gender.
- HGV date & Pleiades place linking hooks for Phase 9.
