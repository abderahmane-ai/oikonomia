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

**DONE (2026-07-23) — `HAS_OCCUPATION` + `HAS_AGE`, the two unambiguous wins.**
The pure rule is `oikonomia.labeling.apposition.attribute_relations`: each
`OCCUPATION`/`AGE` links to the nearest `PERSON`/`PERSON_ROLE` that *ends before*
it, within a 40-char gap. Direction is fixed by the schema and by Greek word order
(subject precedes the attribute); anchoring on the *preceding* subject is what
survives dense signalement registers, where the next registrant's name sits right
after an age (33 such false attractors in gold). A **headcount guard** skips a
counted occupation (`ἱερεῖς β` = "priests: 2", a `HAS_QUANTITY` head, not a title
— schema-consistent with guidelines §5).

Measured on the 115-doc gold (rule applied over gold entities; the edges are a
*proposal*, not merged):

| | edges | of entities |
|---|---|---|
| `HAS_OCCUPATION` | 156 | 192 OCCUPATION |
| `HAS_AGE` | 86 | 133 AGE |

- **Linked entity coverage 35.7% → 49.6% (+14.0 pts)** from these two rules alone;
  PERSON 21.2% → 41.5% (178 → 349 linked), OCCUPATION 2.1% → 83%, AGE 0 → 65%.
- **Recall guard: 0 uncovered**, and all 242 new edges are candidate-covered — the
  two signatures don't break any existing gold relation, and the model can learn
  and the DB can store every new edge.
- Wired through the single authority: `RELATION_SIGNATURES` (+2 types),
  `LOCAL_FAMILY` (both gap-capped), the silver labeler (`_attribute_relations`,
  provisional confidence 0.80/0.70), and an **auditable gold draft**
  (`tools/build_attribute_draft.py` → `data/gold/attribute_draft.jsonl`, 242 edges
  / 70 docs) that never touches `annotated.jsonl` — the Phase-5c review pattern.
- Tests: `tests/test_apposition.py` (13 hand-computed cases incl. the false
  attractor + headcount boundary), plus silver-wiring and encoder-signature tests.

**Sequencing to a measured F1** (deliberately *not* done here): the two relations
are measurable only when **both** sides carry them — silver re-emitted (training
signal) *and* the gold draft reviewed+merged (eval labels). Doing only one gives a
misleading number (new-relation predictions score as false positives against a
gold that lacks them), and silver re-emission changes the fingerprint the next
Modal push reads. So: owner reviews the draft → next session merges approved edges
into gold (append-only, by index) **and** re-emits silver (fresh sha) → owner
push + xval measures `HAS_OCCUPATION`/`HAS_AGE` F1 and the coverage-driven
end-to-end number.

**NEXT in 8b — the fuzzier attribute relations** (`HAS_STATUS`, `ORIGIN_OF`,
`LOCATED_IN`). Deferred deliberately, and the deferral is now **backed by a gold
evidence pass** (2026-07-23), not a hunch:

*Place relations (`ORIGIN_OF` / `LOCATED_IN`).* Of 233 PLACE entities, 154 (66%)
have a PERSON/ROLE within 40 chars (median gap **10**, vs 1 for occupation), split
93 before / 61 after — looser and less directional than apposition. The structure
is **prepositional, not adjacency**: the token before a PLACE is ἀπό/ἀπ' (38 ×,
*origin*), ἐν (23 ×, *location*), περί (12 ×, *near*), plus the article of
`ἀπὸ τῆς κώμης`. Two design forks a pure rule cannot paper over:
  1. **Many place links are PLACE → PLACE, not person → place** — a village/parcel
     located *within* a nome (`Ὀξυρύγχων πόλεως περὶ Κερκεμοῦνιν`, `ἐκ τοῦ
     Ἀνδρονίκου κλήρου`): the administrative hierarchy (κώμη < μερίς < νομός).
     `LOCATED_IN` is really a place-hierarchy edge and needs its own signature.
  2. **"from X" is not always a person's origin** — it also marks a *commodity's*
     provenance (`τὸ εἶδος ἀπ' Ὀξυρύγχων`). `ORIGIN_OF` needs a schema-direction
     decision and a head-label gate, not just an ἀπό cue.
So: gate on the preposition (ἀπό/ἐκ → origin, ἐν → location), decide the
signatures (`ORIGIN_OF`: PERSON/PERSON_ROLE → PLACE; `LOCATED_IN`: PLACE → PLACE),
and only then write the rule.

*`HAS_STATUS`.* Overlaps the existing dual use of `PERSON_ROLE` — a status word
(δοῦλος, ἀπελεύθερος) *is* tagged `PERSON_ROLE`, which already heads PARTY_OF /
PAID_* / the new HAS_* apposition. Adding HAS_STATUS means splitting the role
vocabulary (status vs office) first; a schema question, not a rule.

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

#### End-to-end eval — DONE (2026-07-24, `relations.py::eval_e2e`, saved all-gold RE model)

The shippable RE model (`launch` → `/vol/models/relation/final`, silver→all-gold,
custom `state_dict`+`config.json`) was run on the 115 gold docs **twice**: oracle
(gold entity spans) vs end-to-end (the NER model's corpus-run spans, joined by
stem). `docs_missing_pred = 0` — the stem↔doc_id join is clean.

| PARTY_OF (the edge the women step-8 finding rides on) | F1 |
|---|---|
| Held-out oracle — `launch` 5-fold CV, gold entities (**the honest generalization number**) | **0.705** |
| Same-model oracle on gold docs (`eval_e2e`) | 0.993 ⚠️ train-on-test: these docs are in the all-gold model's training set; **not** a generalization estimate — it only confirms the save/load + constrained-decode inference path works |
| **End-to-end — NER-predicted entities** | **0.623** |

**The entity cascade costs ≈ 0.08 on PARTY_OF** (held-out oracle 0.705 →
end-to-end 0.623). The 0.623 is itself mildly optimistic (the saved model trained
on these gold docs), so the true corpus-wide end-to-end PARTY_OF is likely a shade
under 0.62 — but it **survives the cascade at ~0.6, usable (noisy) for step 8**.
Full end-to-end profile: overall RE F1 0.970 oracle → 0.609 e2e (P 0.771 / R
0.503); direction stays weak as parked (PAID_BY 0.231, PAID_TO 0.507); rare
relations HAS_PRICE / CHARGED_UNDER collapse to 0.0 e2e (NER rarely predicts their
COMMODITY/PRICE/TAX_TERM endpoints) — irrelevant to the deliverables, since the
DB's price/tax findings run on the lexicon+rules, not RE.

**This closes step 7** (revive + save the RE model + standalone e2e inference).
(a) `RelationHead` → module-level `build_relation_head` factory, re-verified via
`xval` (F1 0.729, PARTY_OF 0.678). (b) `save_final`/`launch` persist the custom
model (verified: `eval_e2e` loaded it). (c)+(d) standalone RE on NER-predicted
entities + the e2e drop, above.

**Cut / shelved:** direction features (null); BOND self-training (un-auditable,
unproven); virtual EVENT node as a model construct (do it in the DB layer).
PL-Marker typed markers only if the economic core plateaus.
