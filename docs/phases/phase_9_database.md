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

### The tax finding — fiscal history of Egypt (`oik db taxes`)

Taxes are the *cleanest* thing in the fact table: a tax fact is `amount +
CHARGED_UNDER→tax + date`, no per-unit division. `src/oikonomia/db/taxes.py` gives
two validated results.

**1. The fiscal-regime map** (attestation by era — robust to amount noise). It
reproduces the textbook fiscal history of Egypt:

| tax | Ptolemaic | Roman | Byzantine+ | reads as |
|---|---|---|---|---|
| `laographia` (poll tax) | 9 | **560** | **0** | Roman institution (~24 AD, gone in late antiquity) ✓ |
| `prosdiagraphomena` (surcharge) | 3 | **2707** | 0 | Roman surcharge ✓ |
| `demosia` (land tax) | 3 | 59 | **1612** | dominant Byzantine term ✓ |
| `phylakitikon` (guard tax) | **186** | 66 | 0 | Ptolemaic, fading ✓ |

**2. Poll-tax (laographia) payments** — silver, cleaned (comparable denomination,
individual-payment cap). These are *payments, not the rate*: the poll tax was paid
in installments, so a receipt is a partial sum (median ~4 dr) and the full annual
capitation (~16–40 dr/nome) shows in the tail (p90 = 20 dr). By century: 1c AD
4.0 [0.7–10] (n=217), 2c AD 4.2 [2–8] (n=262), 3c AD 8.0 (n=48).

**By region** (place names resolved from HGV via `db/places.py`): the variation is
real — **Arsinoites 25 dr** (n=25) vs **Herakleopolites 2 dr** (n=66), Theben 4,
Elephantine 8 — the nome-level differences the literature records.

`oik db taxes` writes `db/taxes.parquet` (592 clean poll+land-tax payments, with
provenance). Again **no model** — tax terms are closed-class lexicon hits.

### Where the trained models fit (they are NOT used above — by design)

The economic findings run on the lexicon + rules because prices/taxes are
**closed-class vocabulary** the dictionary matches at ceiling; the neural model adds
nothing there. The models earn their keep on:
1. **deliverable #1** — a released papyri Greek NER+RE model, a contribution in itself;
2. the **person/place-heavy findings** (women-as-principals, kinship, credit networks),
   where PERSON/PLACE are open-class and rules fail (model beats rules +19 PERSON /
   +11 PLACE) — those will run the trained entity model over the corpus (a Modal job).

### The women-as-principals finding — logic validated on gold (`oik db women`)

> **This rule-based path was REMOVED from the codebase on 2026-07-24**, once step 8
> superseded it end-to-end with the trained RE model (`oik db principals`). Deleted:
> `src/oikonomia/db/parties.py`, the `oik db women` command, `tests/test_db_parties.py`
> and the `db/parties.parquet` artifact. **The results below are the permanent
> record** — they were the gold validation that licensed the Modal spend, and they
> are not re-runnable at HEAD. Recover the code from git history if ever needed
> (last present at commit `b28f6c8`). The gender/guardian logic it validated
> (`db/persons.py`) is unchanged and still live; only the party-assembly wrapper
> went away.

The third finding, and the first whose *people* are open-class (a name gazetteer
can't be at ceiling the way the price/tax closed classes are). Built the
gender+party layer and **validated it on gold first** (the free, laptop path)
before spending any Modal — the decision that was teed up at the pivot.

- **`persons.py`** — deterministic, precision-ordered gender attribution for a
  PERSON span, each call returning the *rule that fired* (auditable): (1) the
  guardian formula `μετὰ`/`χωρὶς κυρίου` → female (only women had a κύριος; ~0.97);
  (2) Roman nomen declension `Αὐρήλιος` m / `Αὐρηλία` f across all cases (~0.9);
  (3) kin nouns θυγάτηρ f / υἱός m (~0.9); (4) the Egyptian article prefix *tꜣ-*
  (`Τα-`) f / *pꜣ-* (`Πα-`/`Πετε-`) m (~0.72); (5) a small Greek-name gazetteer
  (~0.8). Three guards earn their keep — the **metronymic** `… μητρὸς X` names the
  *mother*, not the head person (μήτηρ ignored); the **handoff** `… καὶ ὁ υἱὸς …` /
  `… καὶ … χωρὶς κυρίου` points the noun at a *co-ordinated other* party; and a
  **masculine-inflection veto** stops a female stem reading `Δίδυμον`/`Διδύμῳ`
  (Δίδυμος m) or `Θερμούθιος` (m) as the feminine Διδύμη/Θερμοῦθις.
- **`parties.py`** — `assemble_parties` walks `PARTY_OF`/`PAID_BY`/`PAID_TO` into
  one row per named principal: gender + basis, guardian-present flag, role
  (party/payer/payee), transaction term, date/century/genre, `(doc, span)`.
- **`oik db women --source gold|corpus`** — gold runs the human annotations (the
  honest test of the *logic*); corpus runs the rule labeler (a noisy lower bound).

**Result on gold (115 docs, human PARTY_OF):** 178 principals, 42% gender-
attributable, **women's share 13.5% (10/74)** — inside the literature's ~15–25%.
Precision on the female sample is **10/10** (every one hand-verifiable: guardian
formula, Aurelia, θυγάτηρ, Ta-/Isidora). The cut that matters: **women are 44% of
*sale* principals but 0% of leases and 6% of loans** — the textbook pattern (women
bought/sold and inherited property far more than they leased or lent). 4/10 female
principals carry an explicit κύριος guardian.

**Corpus lower bound (4,000 docs, rule labeler, noisy):** 2,587 principals, 17.7%
women, and a plausible large-n arc — 3c BC 3% → **2c AD 28%** → 3c AD 16%. The 2c
AD peak is partly a detection artifact (guardian formula + Aurelia nomina cluster
there) but also the real Roman-era rise in women's documented activity. Writes
`db/parties.parquet` with full provenance.

**A bootstrapped name gazetteer was tried and REMOVED (2026-07-24).** It voted each
name-form's gender from rule attestations corpus-wide to lift coverage 42%→54% on
gold. It worked, but it was **synthetic slop built to pump a coverage number** —
the exact shortcut CLAUDE.md §2 now forbids. Deleted (`db/name_gender.py`, its CLI
`oik db names`, its tests, `db/name_gender.json`). Gender stays on the
**high-precision, principled** signals only (guardian formula, Roman nomen, kin
noun), each labeled by `basis` so an analysis can keep only the strong ones.

**The real path — use the trained models as the extraction engine.** People and
parties are open-class; that is precisely where the model beats rules (PERSON +19,
PARTY_OF 0.28→0.65). The delivered finding runs the **trained NER model over the
corpus** (a Modal inference run) for the people, plus the deterministic legal
formulae — μετὰ / χωρὶς κυρίου (guardian; only women carry one → near-certain
gender), χρηματίζουσα, γράμματα μὴ εἰδυίης (literacy proxy) — as first-class
features. The rule-labeler `--source corpus` path served only as a noisy lower-bound
sanity check, never as the deliverable — which is why it was deleted once step 8
landed the model-driven version.

### Women as principals ACROSS DEAL TYPES — DONE (step 8, 2026-07-24, RE-driven)

The fuller women finding, on the **trained NER+RE pair** end-to-end. The saved RE
model (`modal_app/relations.py::infer` → `infer_corpus` on the A10) was run over
all 61,249 docs' NER-predicted entities → **228,945 relations, 16,315 PARTY_OF**
(`predictions/re_corpus.jsonl`). `oik db principals` keeps the people the deal
turns on (PARTY_OF / PAID_* heads) and joins each to the validated gender +
guardian + patronymic from `persons.parquet` (steps 3-4), tagged by deal type.

**21,895 principals; women's share 18.0%** (1,641 of the 9,130 gender-attributable;
42% coverage). The headline is the **deal-type gradient** (stable at n≥40):

| deal type | women's share | | deal type | women's share |
|---|---|---|---|---|
| **sale** | **30%** (58/191) | | lease | 15% (21/140) |
| **loan** | **28%** (41/144) | | letter (private) | 12% |
| contract | 23% (853/3,708) | | receipt / order / list | 10% |
| declaration | 23% | | account | 8% |
| petition | 20% (51/250) | | delivery | 5% |

**Women's economic agency concentrates in property transactions — sales and loans
(28-30%) — and is thinnest in routine fiscal paperwork** (receipts, deliveries,
accounts, 5-10%). This matches the historical picture: women acted as principals
over property they owned (dowry, inheritance), i.e. sales and loans of their own
assets, far more than in the tax-collection machinery. By century, women's share
peaks 1c BC-2c AD (22-27%) and declines through late antiquity (7-12% by 5c-7c AD).

Cross-checks that make it trustworthy: the guardian split among women principals
is **92% μετὰ / 8% χωρὶς** — identical to the person-level step-4 number, so the
RE layer did not distort the autonomy signal; and **65% (1,063/1,641) of women
principals carry a recovered patronymic** (split-person `CHILD_OF`) for
prosopography. Honest caveats: end-to-end PARTY_OF ≈ 0.62 (noisy), so the
*relative* deal-type ordering is the robust claim, not the exact percentages; and
35 giant tabular registers (>2000 entities) are RE-skipped by design — their cost
is quadratic in density but they hold no party structure (removing them dropped
~5k spurious edges while PARTY_OF fell only 761→754 on the first 2k docs). Code:
`oikonomia/relations/infer.py` (windowed candidates), `oikonomia/db/principals.py`
(assembler), `modal_app/relations.py::infer_corpus` (A10 entrypoint). Detail on
the RE model + end-to-end number: [`phase_8_relation_model.md`](phase_8_relation_model.md).

### The database, packaged — DONE (2026-07-24, `oik db export`)

The loose per-finding parquets are now a **documented, queryable database**
(deliverable #2), schema in [`../database.md`](../database.md). `oik db export`
writes: a **61,249-doc spine** (`documents.parquet` — metadata + per-doc person/
principal/money counts + price/tax flags, the queryable entry point), a
**coreference-lite distinct-person table** (`persons_distinct.parquet`,
`oikonomia.db.identity`: NFC+casefold surface key on name+father+place, folds Greek
final sigma / Unicode form; under-merges so it's an upper bound on the headcount),
and a `manifest.json` (inventory + pinned `corpus_rev` + CC BY 3.0).

The distinct-person view answers the reviewer's real question: **1,414 distinct
women principals of 7,022 gendered = 20.1%** — *higher* than the 18.0% mention
share, because men repeat more within a document, so folding mentions to people
lifts the women's share. The honest headcount strengthens the finding.

### Next

1. ✅ **Price finding** (wheat series) — done, validated.
2. ✅ **Tax finding** (fiscal-regime map + poll tax by century/region) — done, validated.
3. ✅ **Women as economic principals** — DONE end-to-end on the trained models:
   the **autonomy curve** (steps 1-6: model NER → gender+guardian → χωρὶς-κυρίου
   0%→39%→80% over 3c→4c AD, gold-validated) **and** the **principals-by-deal-type**
   finding (steps 7-8: saved RE model → PARTY_OF corpus-wide → women's share by deal
   type, sale/loan 28-30% vs receipt/delivery 5-10%). `CHILD_OF` kinship recovered
   (65% of women principals have a patronymic).
4. Entity identity/coreference for cross-document prosopography.
5. Release the frozen entity+relation models (deliverable #1).
