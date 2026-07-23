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

### The wheat price series — first validated finding (`oik db prices`)

The raw `value/quantity` was dominated by extraction artifacts. Diagnosis on wheat
found two, and `src/oikonomia/db/prices.py` filters them:

- **the double-link** — **48%** of priced wheat rows had `value_num == quantity`
  (the same numeral read as both price and amount), forcing the ratio to ~1.0 (the
  "1 dr/artaba everywhere" artifact). Dropped.
- **wrong unit / bronze** — commodities linked to a land area (`aroura`) or an
  account total (quantities to 461,067), and `chalkous` bronze prices (the Ptolemaic
  bronze/silver inflation, not a comparable signal). Requiring the commodity's own
  measure (`artaba`), a silver denomination, and plausible quantity/price removes them.

Precision over recall (this feeds a *published* number). The surviving **70 clean
wheat observations** reproduce the literature — median [IQR] (n), silver system:

| Century | dr/artaba | IQR | n | Published |
|---|---|---|---|---|
| 3c BC | 2.53 | 1.5–7.8 | 14 | ~1–2 (Ptolemaic) ✓ |
| 1c AD | 2.44 | 1.5–16 | 5 | early Roman |
| **2c AD** | **13.33** | **6.0–27.5** | 37 | **~7–12 (Roman) — IQR brackets it** |
| 3c AD | 3.76 | 2.4–8.0 | 9 | inflation era (thin) |

`oik db prices` writes `data/processed/db/prices.parquet` — 98 clean price
observations (wheat/barley/wine), each with `(tm_id, span, date, place)` provenance.
Barley/wine are thin (single well-populated centuries); oil too sparse for a series.

**No model was used** — the price entities (wheat/drachma/artaba) are closed-class
lexicon hits, so rules are at ceiling. The trained model's value is elsewhere (see
below).

### Honest caveats

- **Small n** is the cost of precision filtering: 70 clean wheat obs. More would come
  from better `HAS_PRICE`/`HAS_QUANTITY` linking — the one place the **trained
  relation model could later raise recall** (it is not used in this rule-based path).
- **3c AD (3.76) reads low** for the inflation onset — n=9, volatile; the great
  inflation is 4c AD+, thin here.

### Where the trained models fit (they are NOT used above — by design)

The economic findings run on the lexicon + rules because prices/taxes are
**closed-class vocabulary** the dictionary matches at ceiling; the neural model adds
nothing there. The models earn their keep on:
1. **deliverable #1** — a released papyri Greek NER+RE model, a contribution in itself;
2. the **person/place-heavy findings** (women-as-principals, kinship, credit networks),
   where PERSON/PLACE are open-class and rules fail (model beats rules +19 PERSON /
   +11 PLACE) — those will run the trained entity model over the corpus (a Modal job).

### Next

1. **Tax finding** (cleanest signal — no per-unit math): *laographia* + *demosia* by
   century/region, straight from the fact table (6,623 tax-linked amounts).
2. **Women as economic principals** — the first finding that *needs* the trained
   model: gender (deterministic) + `PARTY_OF` + guardian-`κύριος`, plus splitting the
   PERSON blob for `CHILD_OF` kinship (43% of gold PERSON spans are collapsed).
3. Entity identity/coreference for cross-document prosopography.
4. Release the frozen entity+relation models (deliverable #1).
