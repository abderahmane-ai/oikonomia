# Phase 7 — Entity Named Entity Recognition (NER)

### ✅ Phase 7 — Entity NER: DAPT beats the control (+9.5 strict F1)

**The result the whole DAPT detour was for. B0 (no DAPT) vs B1 (papyri DAPT),
identical fine-tune on silver, scored on the 65-doc human-validated gold:**

| | b0 (control) | b1 (DAPT) | Δ |
|---|---|---|---|
| strict micro F1 | 0.495 | **0.589** | **+0.095** |
| relaxed micro F1 | 0.663 | 0.719 | +0.056 |
| PERSON | 0.458 | 0.648 | **+0.190** |
| PLACE | 0.503 | 0.617 | **+0.114** |
| MONEY_AMOUNT | 0.575 | 0.634 | +0.058 |

- **b1 ≥ b0 on every label**, strictly greater on most; nothing regressed.
  Squarely in the Gururangan "2–12 pts, largest at greatest domain distance".
- **The mechanism closed:** gains concentrate in PERSON/PLACE — the
  onomastic/toponymic labels the ~40M-param embedding remap (full-FT-only) was
  predicted to help. Lexicon-reachable labels barely move (CURRENCY .78→.79).
- **The ~0.59 ceiling is silver-bounded, not model-bounded:** b1's 0.589/0.719
  ≈ the silver labeler's own gold agreement (Phase 6). b0 can't even reach the
  silver ceiling — the weak backbone leaves ~9 pts on the table.

### ✅ Phase 7b — Two-stage silver→gold RUN: gold fine-tune is the recipe (strict 0.737 on 115-doc gold)

**Latest Peak Results (5-fold CV, CE loss, B1 backbone):**

| Stage | Strict F1 | Relaxed F1 |
|---|---|---|
| Silver-only | 0.6541 (65.4%) | 0.7533 (75.3%) |
| **Silver $\rightarrow$ Gold** | **0.7367 (73.7%)** 🚀 | **0.8370 (83.7%)** 🔥 |

**Per-label Strict F1 Scores:**
- `AGE`: **0.9742 (97.4%)**
- `PRICE_TERM`: **0.9286 (92.9%)**
- `FRACTION`: **0.8632 (86.3%)**
- `UNIT`: **0.8412 (84.1%)**
- `CURRENCY`: **0.8216 (82.2%)**
- `PERSON`: **0.7745 (77.5%)**
- `MONEY_AMOUNT`: **0.7583 (75.8%)**
- `OCCUPATION`: **0.7457 (74.6%)**
- `QUANTITY`: **0.7439 (74.4%)**
- `DATE_REF`: **0.6904 (69.0%)**
- `PLACE`: **0.6496 (65.0%)**
- `TRANSACTION`: **0.6015 (60.2%)**
