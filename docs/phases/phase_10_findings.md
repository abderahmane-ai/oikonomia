# Phase 10 — The findings

**Status:** ✅ recorded (2026-07-24). Deliverable #3.
**Inputs:** the Phase-9 database (`data/processed/db/`), published as
[`ainouche-abderahmane/oikonomia-db`](https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db).
**Every number below was recomputed from the shipped parquet tables when this
document was written.** Nothing here is quoted from an earlier session.

---

## 0. What a "finding" has to satisfy here

The project's claim is not "a model scores X." It is: *documentary papyri, read
automatically at corpus scale, reproduce known economic history and answer
questions nobody has counted by hand.* So each finding below is stated as a claim
with four things attached:

1. **The number**, with its denominator.
2. **The mechanism** — which part of the pipeline produced it (lexicon+rules, or
   the trained models), because the two have different failure modes.
3. **The control** — a fact from the historical literature the same table has to
   recover, unsupervised, before its novel numbers are worth reading.
4. **The limits** — stated up front, not in a footnote.

Findings are ordered by **evidential strength**, not by how interesting they are.
Two of them (F1, F2) are *validation* findings: they are already-known history,
and their job is to prove the pipeline is measuring the world. Two (F3, F4) are
*novel* counts at a scale no one has done by hand. One (F5) is honest but thin.

---

## F1 — The silver→gold monetization transition (validation, strongest)

**Claim.** The currency system of Egypt flips from silver to gold across the 4th–5th
century AD, and the flip is visible in the raw money mentions with no historical
input whatsoever.

**The number** — share of dated, system-attributed money facts denominated in gold:

(every century with n > 1,000 — nothing is omitted)

| Century | n facts | gold share |
|---|---|---|
| 3c BC | 18,256 | 0.000 |
| 2c BC | 6,329 | 0.006 |
| 1c BC | 2,399 | 0.003 |
| 1c AD | 15,569 | 0.002 |
| 2c AD | 67,191 | 0.000 |
| 3c AD | 11,890 | 0.001 |
| **4c AD** | 7,539 | **0.155** |
| **5c AD** | 2,677 | **0.931** |
| 6c AD | 21,359 | 0.875 |
| 7c AD | 6,524 | 0.996 |
| 8c AD | 25,028 | 1.000 |

Eleven centuries of near-zero gold, then a two-century flip, then saturation.

**Mechanism.** Lexicon + rules over the whole corpus (`oik db build`), 195,906
monetary facts across 12,592 distinct TM ids, **98.7% normalized to a canonical
currency, 94.3% datable**. The `system` field comes from the currency id, the
century from HGV metadata already carried in `corpus.parquet`. No model involved.

**Control it recovers.** This is the textbook periodization: the debasement and
collapse of the Alexandrian silver tetradrachm through the 3rd century, and
Constantine's gold *solidus* (introduced 309–312 AD) becoming the unit of account
by the 5th. The pipeline reproduces the shape *and the timing* — the crossover
sits between the 4c and 5c samples — without ever being told coinage history.

**Limits.** Century-level resolution only; the 4c bucket (0.155) is the transition
itself and averages over decades that differ sharply. Document survival is uneven
across centuries, so shares are reliable and raw counts are not.

---

## F2 — The fiscal-regime map: Egyptian taxation periodizes itself (validation, strong)

**Claim.** Named taxes in the corpus sort themselves into the correct political
eras — Ptolemaic, Roman, Byzantine — from text alone.

**The number** — 6,441 tax-linked monetary facts, 18 distinct named taxes.
Counts by century for the six that carry the periodization:

| Tax | 3c BC | 1c AD | 2c AD | 3c AD | 6c AD | 8c AD | total |
|---|---|---|---|---|---|---|---|
| *prosdiagraphomena* (surcharge) | 0 | 1,940 | 751 | 16 | 0 | 0 | 2,710 |
| *demosia* (land tax) | 0 | 13 | 34 | 12 | 942 | 598 | 1,674 |
| *phoros* (rent/tribute) | 32 | 41 | 322 | 42 | 179 | 0 | 662 |
| *laographia* (poll tax) | 0 | 226 | 285 | 49 | 0 | 0 | 569 |
| *merismos* (apportionment) | 0 | 8 | 305 | 12 | 4 | 2 | 348 |
| *phylakitikon* (guard tax) | 183 | 25 | 41 | 0 | 0 | 0 | 252 |

Read the rows as regimes:

- ***laographia*** — the poll tax — is confined to the Roman centuries: **560 of
  569 attestations fall in the 1st–3rd centuries AD, and zero after the 3rd**. The
  remaining 9 sit in the 1c BC bucket, which straddles the 30 BC annexation. There
  is not a single attestation in the 3rd or 2nd century BC. Correct: the poll tax
  is an Augustan institution (24/23 BC) and dissolves in the 3rd-century reforms.
  The pipeline draws both boundaries of Roman Egypt from text alone.
- ***prosdiagraphomena*** — the Roman surcharge — is 99% confined to the 1st–3rd
  centuries AD, peaking in the 1st.
- ***phylakitikon*** — the Ptolemaic guard tax — is 73% in the 3rd century BC and
  gone after the 2nd century AD.
- ***demosia*** — becomes dominant in the 6th–8th centuries AD (1,596 of 1,674):
  the Byzantine/early-Arab land tax.

**Poll-tax payment sizes** (`oik db taxes`, 539 clean *laographia* payments):

| Century | n | median (dr) | p90 (dr) |
|---|---|---|---|
| 1c AD | 217 | 4.00 | 16.0 |
| 2c AD | 262 | 4.17 | 38.7 |
| 3c AD | 48 | 8.00 | 20.0 |

The median ~4 dr is an **installment**, not an annual assessment; the p90 tail
(16–39 dr) brackets the known annual rate of roughly 16–40 dr depending on nome.
Regional variation is real and large in the same direction the literature reports
(Arsinoite nome high, Herakleopolite low).

**Mechanism.** Lexicon + rules. Taxes are the *cleanest* slice of the fact table
because a tax payment is an amount attached to a named tax — there is no per-unit
division to get wrong (contrast F5).

**Limits.** Two entries in the 18-tax list (`drachma`, `year`, 24 facts combined)
are lexicon contamination, not taxes — they are visible, small, and do not touch
the six rows above. Counts track document survival, so compare *within* a tax
across time, never *between* taxes.

---

## F3 — Women's autonomy: the χωρὶς-κυρίου curve (novel, model-driven)

**Claim.** Among women who appear in transactions with a guardianship formula, the
share acting **without** a guardian (χωρὶς κυρίου) rises from **0% before the 2nd
century AD to 39% in the 3rd and 80% in the 4th.**

**The number** — `data/processed/db/autonomy.parquet`, by century:

| Century | with guardian (μετὰ κυρίου) | without (χωρὶς κυρίου) | n | autonomous share |
|---|---|---|---|---|
| 3c BC | 59 | 0 | 59 | 0.00 |
| 2c BC | 86 | 0 | 86 | 0.00 |
| 1c BC | 116 | 0 | 116 | 0.00 |
| 1c AD | 385 | 0 | 385 | 0.00 |
| 2c AD | 808 | 10 | 818 | 0.01 |
| **3c AD** | 134 | 85 | 219 | **0.39** |
| **4c AD** | 7 | 28 | 35 | **0.80** |
| 6c AD | 3 | 10 | 13 | 0.77 |

**Mechanism — this one is the trained models' finding, not the rules'.**
[Grammateus](https://huggingface.co/ainouche-abderahmane/grammateus) was run over
**all 61,249 text-bearing documents on an A10** (chunked and strided, so long
documents lose no one) → **1,368,079 entities, 350,206 PERSON spans**, offsets
validated against `corpus.parquet` with **0 mismatches in 1.37M**. Those spans were
split into head + patronymic chains (129k father links recovered), gendered by a
precision-ordered rule cascade over the *model's* spans, and the guardianship
formula typed as with/without. Rules cannot find the people — PERSON is open-class
and the model beats the rule baseline by +19 F1 there. Rules can only read the
formula once the people are found.

**Control it recovers.** This is the spread of the *ius liberorum* (the exemption
from tutelage granted to freeborn women with three children, extended widely after
the Constitutio Antoniniana of 212 AD) and the general decline of *tutela mulierum*.
The curve's inflection sits exactly where Roman legal history puts it — and the
pipeline was never told about any of it.

**Validation** (`oik db validate-women`, against the 115-document all-human gold):
the gender rules are **100% deterministic** — 613/613 matched spans agree with
gold. PERSON relaxed recall is 0.91. The guardian counting **over-counts on the
μετὰ (with) side** while **χωρὶς matches gold exactly** — which means the error
pushes the autonomous share *down*. **The rise is conservative, not inflated.**

**Limits.** Denominators shrink hard after the 3rd century (n=35 in the 4c, n=13 in
the 6c) — the *direction* is solid and the *level* in late centuries is not. The
regional cut is confounded by each nome's era composition and is not reported as a
finding. Only women whose text carries an explicit formula are counted; silence is
not evidence of autonomy.

---

## F4 — Women as principals, and the deal-type gradient (novel, model-driven)

**Claim.** Women are **18.0% of transaction principals** by mention and **20.1% of
distinct principals** by head-count — and their share is **three times higher in
property transactions than in fiscal paperwork.**

**The numbers.** 21,895 principals extracted; 9,130 gender-attributable; women
1,641 → **17.97%**. By deal type (n ≥ 40 gender-attributable):

| Deal type | n | women's share |
|---|---|---|
| **sale** | 191 | **0.304** |
| **loan** | 144 | **0.285** |
| register | 113 | 0.248 |
| contract | 3,708 | 0.230 |
| declaration | 102 | 0.225 |
| petition | 250 | 0.204 |
| lease | 140 | 0.150 |
| letter (private) | 179 | 0.117 |
| list | 86 | 0.105 |
| **receipt** | 2,200 | **0.102** |
| order | 239 | 0.096 |
| account | 76 | 0.079 |
| **delivery** | 59 | **0.051** |

The gradient is the finding: **sale 30% / loan 28%** (women disposing of and
lending property in their own name) versus **receipt 10% / delivery 5%** (the
fiscal and administrative paper trail, where the named party is usually the male
taxpayer of record). A single corpus-wide "women's share" number averages two very
different worlds and should not be quoted alone.

Secondary numbers, all consistent with F3: of the 520 women principals carrying a
guardianship formula, **92% μετὰ / 8% χωρὶς** — the *same* split step 4 measured
independently, so the relation model did not distort the gender/guardian layer.
**64.8%** of women principals carry a patronymic, which is the hook for
cross-document prosopography.

Women's share by century (gender-attributable principals, n ≥ 100) is flat-to-
declining — 1c AD 0.254, 2c 0.224, 3c 0.203, 4c 0.137, 6c 0.116 — which is *not*
in tension with F3: F3 measures how women transact when they do, F4 measures how
often they appear at all, and the late-period drop tracks a corpus that becomes
dominated by fiscal and ecclesiastical paperwork.

**Mechanism.** Both models end to end.
[Homologia](https://huggingface.co/ainouche-abderahmane/homologia) was run over the
corpus's model-predicted entities on an A10 → **228,945 relations, 16,315
PARTY_OF**; PARTY_OF/PAID_* heads were kept, joined to the gendered person table,
and tagged by deal type. The honest accuracy figure for this chain is the
**end-to-end PARTY_OF F1 of 0.623** on predicted entities (not the 0.705 oracle) —
the entity cascade costs about 0.08.

**Limits.** 0.623 is noisy, so treat the *ordering* of deal types as the result and
the exact percentages as approximate; the ordering is stable for every bucket with
n ≥ 40. 58% of principals are not gender-attributable and are excluded, not
imputed. 35 dense registers were skipped by design (quadratic candidate cost, no
party structure to find). Mentions are not people — the 18.0% and 20.1% figures
answer different questions and both are reported for that reason.

---

## F5 — Commodity prices (real, but thin — the weakest finding)

**Claim.** A wheat price series can be extracted, and where it is dense it agrees
with the literature; elsewhere it is too sparse to defend.

**The number** — `oik db prices`, 98 clean observations after filtering
(wheat 70, wine 14, barley 11, oil 3). Wheat, drachmas per artaba:

| Century | n | median | IQR |
|---|---|---|---|
| 3c BC | 14 | 2.53 | 1.50–7.75 |
| 1c AD | 5 | 2.44 | 1.50–16.00 |
| **2c AD** | **37** | **13.33** | **6.00–27.50** |
| 3c AD | 9 | 3.76 | 2.42–8.00 |

The 2c AD figure is the only bucket with a usable n. Its IQR (6–27.5) brackets the
literature's ~7–12 dr/artaba, and the 3c BC Ptolemaic value (2.53 vs a literature
~1–2) is the right order of magnitude. The 3c AD median moving *down* is an
artifact, not deflation — that century is where the currency itself is collapsing
(see F1) and the per-unit arithmetic is least trustworthy.

**Mechanism.** Lexicon + rules, then aggressive precision filtering: drop the
`value_num == quantity` double-link artifact (48% of raw candidates), bronze
*chalkous* amounts, wrong units, implausible quantity/price pairs.

**Limits — stated plainly.** 98 observations out of 195,906 monetary facts is the
honest cost of that filtering. Two known defects remain: `unit_price =
value / quantity` **over-divides when the recorded amount is already per-unit**,
and non-wheat commodities are too sparse to report at all (the 1c BC wine median
of 502 and the 4c wine median of 294 are unit errors, not prices, and are shown
here only to mark where the arithmetic breaks). **This series is not yet at the
standard of Rathbone or Bagnall and should not be published as a price history
without the per-unit fix and an outlier model.** It is included because suppressing
it would misrepresent what the database currently supports.

---

## Reproducing every number in this document

All tables are gitignored and re-derivable on a laptop; no GPU is needed for any
step below (the two corpus-scale model runs are already materialized as
`ner_corpus.jsonl` / `re_corpus.jsonl`, pullable from the `oikonomia-ner` volume).

```bash
.venv/bin/oik db build --sample 0    # 195,906 facts  → F1, and the input to F2/F5
.venv/bin/oik db taxes               # 592 clean tax payments      → F2
.venv/bin/oik db persons             # 350,206 gendered spans      → F3
.venv/bin/oik db autonomy            # the χωρὶς curve             → F3
.venv/bin/oik db principals          # 21,895 principals           → F4
.venv/bin/oik db prices              # 98 clean price obs          → F5
.venv/bin/oik db validate-women      # gold validation of F3/F4
```

Then query them directly (DuckDB is not a project dependency — `pip install duckdb`):

```sql
-- F1, the monetization transition
SELECT century, count(*) AS n,
       round(avg(CASE WHEN system='gold' THEN 1 ELSE 0 END), 3) AS gold_share
FROM monetary WHERE system IS NOT NULL AND century IS NOT NULL
GROUP BY century ORDER BY century;

-- F2, the fiscal-regime map
SELECT tax_id, century, count(*) AS n FROM monetary
WHERE tax_id IS NOT NULL AND century IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 2;

-- F3, the autonomy curve
SELECT * FROM autonomy WHERE dimension = 'century' ORDER BY bucket;

-- F4, the deal-type gradient
SELECT deal_type, count(*) AS n,
       round(avg(CASE WHEN gender='female' THEN 1 ELSE 0 END), 3) AS women_share
FROM principals WHERE gender IN ('female','male')
GROUP BY 1 HAVING n >= 40 ORDER BY women_share DESC;
```

Bootstrap the views with `duckdb -init docs/db.sql` from the repository root.
Column dictionaries, join model, controlled vocabularies and the eight pitfalls:
[`docs/database.md`](../database.md).

---

## Threats to validity that apply to all five

1. **Survival bias is not correctable.** Every count is a count of *surviving,
   published, digitized* papyri, skewed toward the Arsinoite nome and toward dry
   sites. Shares within a bucket are interpretable; raw counts across buckets are
   not.
2. **Dates are HGV's, not ours.** 94–98% of documents carry a date range; the
   century is the midpoint. Broad ranges are assigned to one century and that
   smears sharp transitions (which makes F1's sharpness more impressive, not less).
3. **Mentions ≠ people.** Only the export's `persons_distinct` (17,362 people,
   coreference-lite) is a head-count. The fact tables count mentions.
4. **Two different error regimes.** F1/F2/F5 are lexicon+rules: high precision,
   closed vocabulary, systematic misses. F3/F4 are neural: open-class recall the
   rules cannot reach, with a measured cascade cost (entity 0.737 strict →
   relation 0.623 end-to-end on PARTY_OF). Never blend an error bar across the two.
5. **No entity resolution across documents yet.** The same Aurelia in three
   receipts is three rows. The 64.8% patronymic coverage in F4 is the hook for
   fixing this, and it is the single highest-value next step.

---

## What would strengthen this, in priority order

1. **Fix the per-unit price semantics** (F5). This is a bounded, deterministic fix
   and it converts the weakest finding into a defensible series with error bars.
2. **Cross-document entity resolution** (all person findings). Turns 21,895
   principal *mentions* into a prosopography and lets F3/F4 be measured per person
   rather than per mention.
3. **More payment-direction gold** (only if a credit-flow finding needs it).
   PAID_BY sits at 0.145 and is data-bound; it is the one thing blocking "who lent
   to whom," and nothing else in this document depends on it.

Not on the list: further relation-F1 tuning. It is measured out (Phase 8a), and no
finding here is limited by it.
