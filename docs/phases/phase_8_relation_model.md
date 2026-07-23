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
Three pieces, built + committed (`ae07578`, `efd89c3`, `75e2590`):
- Neuro-symbolic direction features: verb-class / verb-position / payer-marking
  (always-on in the head).
- Wide between-span context vector (reaches before the payer).
- Functional schema constraints (`constrain` in `relations/decode.py`), applied
  only under `--constrain-decode`.
- Single-encode SpERT-style neural head in `modal_app/relations.py`.

**MEASURED 2026-07-23 — direction-features + wide-context arm came back FLAT.**
`xval --backbone b1 --loss ce` (no `--constrain-decode`; fingerprint matched
`sha=96428892f944 docs=48891`, gold_docs=98):

| Stage | F1 | P | R |
|---|---|---|---|
| Silver-only | 0.643 | 0.681 | 0.609 |
| Silver→Gold | **0.710** | 0.761 | 0.665 (Δ +0.067) |

vs the committed 0.713 baseline → **−0.003, within CV noise**. Per-type (baseline → 8a):
PAID_TO 0.300 → **0.253** ↓, PAID_BY 0.145 → 0.136, PARTY_OF 0.652 → 0.647,
HAS_PRICE 0.444 → 0.385 ↓, DATED_TO 0.369 → 0.353, HAS_QUANTITY 0.744 → 0.736,
HAS_UNIT 0.874 → **0.918** ↑, CHARGED_UNDER 0.375 → **0.471** ↑.

**Finding: direction is data-bound, not feature-bound.** The always-on features
did not deliver the payer/payee win they were built for (PAID_TO/PAID_BY nominally
*down*); with ~17 direction edges per held-out fold every move is noise. 87 gold
direction edges is too thin regardless of features — the lever is more direction
gold + the 8b coverage program, not head tuning.

**Still untested (cheap, owner-triggered):**
- `--constrain-decode` — the schema-constraint half of 8a (each MONEY→1 CURRENCY,
  QUANTITY→1 UNIT, payment→1 tax; verified recall-safe on gold). Expected to lift
  precision on the functional relations without costing recall. Run this next.
- `--no-relation-weight 0.3` — recall lever for the 24:1 negative imbalance.

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
