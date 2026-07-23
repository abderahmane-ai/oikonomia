# Phase 9 — The queryable economic database (deliverable #2/#3)

### Why this phase exists — the pivot (2026-07-23)

Phases 0–8 built the *reading* (entity NER 0.737, relation RE 0.713 oracle). But
the project's objective (CLAUDE.md §1) is a **structured, auditable database** of
economic life and the **historical findings** it enables — deliverables #2 and #3
— and after eight phases *not one database row existed and not one historical
question had been answered.* The relation-F1 grind (esp. 8a direction) was
polishing the scaffolding while the building didn't exist.

**Decision: freeze the models at their publishable bar and build the database,
driven by a concrete finding.** The model is a means (and secondary deliverable),
not the goal; for most of the graph a deterministic, *auditable* rule is not just
as good but **better**, because deliverable #2 requires every fact to trace to a
span — which a black-box pair-classifier's logic cannot.

### The enabler: the corpus already carries the hard DH infrastructure

The audit that de-risked the whole pivot — `corpus.parquet` already has, per doc:

- **`tm_id`** (Trismegistos) — 100%.
- **`date_lo` / `date_hi` / `date_precision`** — 95–98% (HGV dates as signed years;
  dating a document is a *lookup*, not an extraction — the weak `DATED_TO` relation
  is bypassed).
- **`place_pleiades` / `place_tm`** — 74–76% (places already linked to the Pleiades
  and Trismegistos authority files — the LAWD gold standard, already done).
- **`canonical_genres`, `hgv_terms`** — 100%.
- **decoded `<num>` values** in `document_json` (EpiDoc `@value`, e.g. `μϛ`→46.0) —
  numeral→number is *given* by the DDbDP editors, not parsed.

So the temporal + geographic + genre + numeric backbone of every finding is already
queryable. The model only has to carry entity recall + the strong adjacency
cluster (`HAS_CURRENCY`/`HAS_UNIT`/`HAS_QUANTITY`, 0.87–0.88); everything else is
given or deterministic.

### What was built — `src/oikonomia/db/` + `oik db build`

A GPU-free assembly layer (no learned model invoked):

- **`money.py`** — normalize `(value, currency_id)` to a system base. Silver ladder
  (talent=6000 dr, drachma=6 obols, …) → drachmas; gold system (nomisma=24 keratia)
  → nomismata. **Load-bearing invariant: the silver and gold systems are never
  convertible** (different metals, 600 years apart) — every amount is tagged
  `system` and aggregation must group by it. Identity comes from the lexicon's
  canonical currency id (`entry_id`), not surface guessing.
- **`dates.py`** — `date_lo/hi` → midpoint, signed century (respecting the absent
  year 0), 50-year bin.
- **`facts.py`** — walk a labeled doc's relation graph into `MonetaryObservation`
  rows: each currency-bearing `MONEY_AMOUNT` with its normalized value, the
  commodity it prices (`HAS_PRICE`) + that commodity's quantity/unit
  (`HAS_QUANTITY`/`HAS_UNIT` → per-unit price), and the tax it discharges
  (`CHARGED_UNDER`). Every row keeps `(tm_id, char-span)` provenance.
- **`oik db build`** — runs the deterministic labeler over the corpus, assembles,
  joins HGV date + Pleiades place, writes `data/processed/db/monetary.parquet`,
  and prints a validation view.

Tests: `test_db_money.py`, `test_db_dates.py`, `test_db_facts.py` (hand-computed).

### First run — the machine works, and the numbers are historically real

`oik db build --sample 20000` → **99,494 monetary facts from 18,443 docs**:

- **98% normalizable** (value + known denomination); provenance **100%** (every row
  → tm_id + span).
- system split: **silver 77.7k · gold 20.8k · unknown 1.0k**.
- **4,407 commodity-linked prices** (top: grain, garden, wheat, wine, oil, barley).

**Validation view 1 — wheat price (dr/artaba), median by century** (silver only):
3c BC **1.0** (n=23) · 2c AD **12.0** (n=38) · 4c AD 600 (n=1, the inflation). The
2c AD figure sits at the right order of magnitude vs the published Roman wheat
price (~7–8 dr/artaba, Rathbone/Duncan-Jones) — **a recognizable historical signal
on the first run, from noisy deterministic-only extraction.**

**Validation view 2 (free) — monetization, silver vs gold facts by century:**
silver dominates 3c BC–3c AD, gold nomisma takes over from 4c AD and totally
dominates 6c–8c AD. This is the **textbook coinage history of Egypt, recovered
unsupervised** — and it depends only on `MONEY_AMOUNT`+`CURRENCY` (0.88) + HGV
dates, *not* the noisy price relation, so it is the more robust first finding.

### Honest caveats (where the next iteration goes — and it is NOT model F1)

- **`HAS_PRICE` noise** (rule/model 0.30–0.44) drives price-view outliers (2c BC
  0.07 is a mis-parse; small-n centuries are unreliable).
- **Per-unit semantics**: `unit_price = value / quantity` assumes the amount is the
  *total* for that quantity; some amounts are already per-unit, and some linked
  quantities are wrong (a 0.2-artaba link appeared). Needs a price-construction
  model (τιμή / "per artaba" cues) and outlier filtering.
- **Sample**: 18k docs; widen to the full 68k (the run is ~minutes, laptop).

### Next

1. Harden the price slice: outlier filter, per-unit construction, full-corpus run;
   produce a defensible wheat series with error bars vs the literature.
2. **Second slice — "women as economic principals"** (the novel finding): needs
   gender (deterministic from names/morphology) + `PARTY_OF` (0.65) + guardian-
   `κύριος`, all slotting into the same DB layer; plus **split the PERSON blob** to
   recover `CHILD_OF` kinship (43% of gold PERSON spans are a name+patronymic
   collapsed into one node — the biggest structural gap for prosopography).
3. Entity identity/coreference for cross-document prosopography.
4. Release the frozen entity+relation models (deliverable #1) — already at bar.
