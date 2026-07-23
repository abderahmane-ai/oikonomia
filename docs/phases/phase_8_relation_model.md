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

### 🔶 Phase 8 plan — LEAN / DESCOPED (decided 2026-07-23)

**Why descoped.** The original spec (OIKONOMIA-RE, `~/.claude/plans/
fizzy-wondering-eich.md`) was a *maximal* program — neuro-symbolic direction
features, BOND self-training over 68k docs, a model-predicted virtual EVENT node.
8a's flat result is the evidence against that direction: **the bottleneck is data,
not model machinery.** And deliverable #2 requires every DB fact to trace to a
character span — which argues for *auditable rules* over black-box learned
machinery on the relations that are essentially adjacency. So the plan is cut to
the debuggable, high-ROI core; the glamorous / un-auditable pieces are dropped or
shelved.

**Organizing principle:** prefer the simplest auditable mechanism (a rule) for any
relation that is mostly adjacency; reserve the learned span-pair model for the
genuinely ambiguous economic core (which already works — 0.713 oracle).

#### 8a — accuracy on the current 9 types — CLOSING
Built + committed (`ae07578`, `efd89c3`, `75e2590`): direction features
(verb-class / position / payer-marking, always-on), a wide between-span context
vector, functional schema constraints (`constrain` in `relations/decode.py`, under
`--constrain-decode`), single-encode SpERT head in `modal_app/relations.py`.

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

**Finding: direction is data-bound, not feature-bound.** The always-on features did
not deliver the payer/payee win they were built for (PAID_TO/PAID_BY nominally
*down*); with ~17 direction edges per held-out fold every move is noise. 87 gold
direction edges is too thin regardless of features.

**Verdict on 8a — CLOSED, every model-side knob measured neutral.** The three runs
are one number under different seeds (silver-only F1 wobbles 0.643→0.655 run-to-run
from init alone — that is the noise floor):

| Run | silver→gold F1 | P | R |
|---|---|---|---|
| Baseline (committed) | 0.713 | 0.757 | 0.673 |
| + direction features + wide ctx | 0.710 | 0.761 | 0.665 |
| + `--constrain-decode` | **0.7145** | 0.752 | 0.680 |

- Direction features + wide context — **DROPPED** (measured null, 0.710).
- Schema constraints (`--constrain-decode`) — **MEASURED neutral**: F1 0.7145, and
  the tell is that **precision did not rise** (0.757 → 0.752). Constraints prune
  conflicting duplicates; a flat precision means the model rarely emits them, so
  there is little to fix. (The run header doesn't echo the flag, so "fired but
  no-op" vs "flag inert" is indistinguishable — but precision didn't move either
  way, so it's not a lever. Cheap future fix: echo `constrain=` in the header.)
  **Kept ON as a DB well-formedness invariant** — one currency per amount, one tax
  per payment — for the database's integrity (deliverable #2), *not* for F1.
- `--no-relation-weight 0.3` — optional recall lever, untested, low priority.
- **Bottom line:** no model-side lever remains; the economic core is ~0.71 and the
  next gains are data + coverage (8b/8c), exactly as the descope predicted.

#### 8b — coverage (the real prize) — RULES-FIRST, laptop, no GPU
- Deterministic **apposition rules** for `HAS_OCCUPATION` / `HAS_AGE` /
  `HAS_STATUS` / `ORIGIN_OF` / `LOCATED_IN`: person → attribute, adjacency-based,
  every edge auditable to its two spans. These attributes sit next to the name in
  the large majority of cases, so rules capture most of the coverage cheaply.
- Escalate to the learned model only where rules demonstrably fail.
- Target linked coverage ~25% → ~70% (79% of persons are currently in no relation).

#### 8c — data, not machinery
- **More direction gold** — the only proven lever for PAID_BY/PAID_TO: mine train
  for payment-verb docs, hand-label ~dozens, append to gold (append-only; offsets
  forward-scanned against `corpus.parquet`).
- **BOND self-training — SHELVED.** Un-auditable (silently retrains on its own
  guesses; failure is invisible) and unproven here. Revisit only if a *measured*
  gap demands it.

#### 8d — DB assembly (deterministic; Phase-9-adjacent)
- Morphological genitive parse for `CHILD_OF` kinship + gender (needed for the
  "women as principals" finding). Deterministic, auditable.
- **Event assembly by grouping a document's relations at DB-build time** — NOT a
  model-predicted virtual EVENT node (which would break span-traceability).
- HGV date + Pleiades place linking hooks for Phase 9.

#### Measurement still owed
- End-to-end eval (**predicted** entities → RE) — the real deliverable number vs
  the 0.713 oracle ceiling.

**Cut / shelved:** direction features (null); BOND self-training (un-auditable,
unproven); virtual EVENT node as a model construct (do it in the DB layer).
PL-Marker typed markers only if the economic core plateaus.
