---
license: cc-by-3.0
language:
- grc
pretty_name: "OIKONOMIA-DB: An Auditable Economic Database of Greco-Roman Egypt"
tags:
- papyrology
- ancient-greek
- economic-history
- digital-humanities
- gender-history
- tabular
- parquet
- duckdb
size_categories:
- 100K<n<1M
configs:
- config_name: monetary
  data_files: monetary.parquet
- config_name: prices
  data_files: prices.parquet
- config_name: taxes
  data_files: taxes.parquet
- config_name: persons
  data_files: persons.parquet
- config_name: principals
  data_files: principals.parquet
- config_name: autonomy
  data_files: autonomy.parquet
- config_name: documents
  data_files: export/documents.parquet
- config_name: persons_distinct
  data_files: export/persons_distinct.parquet
---

# OIKONOMIA-DB: An Auditable Economic Database of Greco-Roman Egypt

**195,906 monetary facts, 350,206 gendered person mentions and 21,895 transaction
principals, extracted from 61,249 documentary papyri spanning 300 BCE – 700 CE.
Every row traces back to a character span in a specific document at a pinned
corpus revision.**

Documentary papyri — tax receipts, leases, loans, wage accounts, census returns,
private letters — are the only large body of evidence for the *everyday* economy
of the ancient world. Historians have read them one at a time for a century.
OIKONOMIA-DB is the first attempt to turn the whole Duke Databank into a
structured database that can be queried.

- 📄 **Source corpus:** [Duke Databank of Documentary Papyri](https://github.com/papyri/idp.data) (DDbDP) + HGV metadata, CC BY 3.0
- 🔒 **Pinned revision:** `d7a34f302d1e44e271256092c2b780733187b478`
- 🤖 **Extraction models:** [OIKONOMIA-Grammateus](https://huggingface.co/ainouche-abderahmane/grammateus) (entities) · [OIKONOMIA-Homologia](https://huggingface.co/ainouche-abderahmane/homologia) (relations)
- 💻 **Code:** [github.com/abderahmane-ai/oikonomia](https://github.com/abderahmane-ai/oikonomia)

---

## Dataset Details

### Dataset Description

Eight Parquet tables. Seven hold facts at the grain of a single extracted
statement; one (`autonomy`) is a published aggregate, shipped so a headline result
is inspectable without recomputation.

| Table | File | Rows | One row is | Key |
|---|---|---:|---|---|
| `documents` | `export/documents.parquet` | 61,249 | one text document (the spine) | `stem` |
| `monetary` | `monetary.parquet` | 195,906 | one monetary amount | `tm_id` + span |
| `prices` | `prices.parquet` | 98 | one clean commodity unit-price | `tm_id` + span |
| `taxes` | `taxes.parquet` | 592 | one clean tax payment | `tm_id` + span |
| `persons` | `persons.parquet` | 350,206 | one PERSON mention, gendered | `stem` + span |
| `principals` | `principals.parquet` | 21,895 | one party to a transaction | `stem` + span |
| `persons_distinct` | `export/persons_distinct.parquet` | 17,362 | one distinct person (coref-lite) | `person_id` |
| `autonomy` | `autonomy.parquet` | 32 | one century/region bucket (derived) | `dimension`+`bucket` |

Two extraction regimes produce them, and **they have different error profiles that
must not be blended**:

- `monetary`, `prices`, `taxes` come from a **deterministic lexicon + rules** over
  EpiDoc-decoded numerals. Closed-class vocabulary (*drachma*, *artaba*, *wheat*)
  is matched at gazetteer ceiling. High precision, systematic misses.
- `persons`, `principals`, `persons_distinct`, `autonomy` come from the **trained
  models**, whose measured end-to-end accuracy is entity F1 0.737 (strict) and
  `PARTY_OF` F1 0.623 on predicted entities.

### Dataset Sources

- **Repository:** https://github.com/abderahmane-ai/oikonomia
- **Corpus:** [papyri/idp.data](https://github.com/papyri/idp.data) — DDbDP texts and HGV metadata, CC BY 3.0
- **Authority files:** dates from [HGV](https://aquila.zaw.uni-heidelberg.de/), places from [Pleiades](https://pleiades.stoa.org/), document ids from [Trismegistos](https://www.trismegistos.org/)

---

## Uses

### Direct Use

Built for quantitative ancient economic history and digital papyrology:
price and wage series, fiscal history, gender and legal capacity, prosopography,
regional comparison. Also usable as a **span-linked evaluation set** for Greek
information extraction, since every row carries its source offsets.

### Out-of-Scope Use

- **Not a training corpus for language models.** It holds extracted facts, not text.
- **Not a source of absolute economic aggregates.** Survival bias is uncorrectable
  (see Limitations); shares within a bucket are interpretable, raw counts across
  buckets are not.
- **Not a payment-direction dataset.** Who paid whom is deliberately absent — the
  relation model scores direction at F1 0.145, too low to ship.
- **Not a substitute for reading the papyrus.** Every row gives you the span to go
  and check; for a claim about an individual document, check it.

---

## Getting the data

```python
from datasets import load_dataset

prices = load_dataset("ainouche-abderahmane/oikonomia-db", "prices", split="train")
```

Every table name in the inventory above is a valid config: `monetary`, `prices`,
`taxes`, `persons`, `principals`, `autonomy`, `documents`, `persons_distinct`.

The whole database (14 MB) as local Parquet:

```bash
hf download ainouche-abderahmane/oikonomia-db --repo-type dataset --local-dir oikonomia-db
```

```python
from huggingface_hub import snapshot_download
path = snapshot_download("ainouche-abderahmane/oikonomia-db", repo_type="dataset")
```

### Quickstart (DuckDB)

```sql
-- Women's share of transaction principals, by type of deal.
SELECT deal_type,
       count(*) AS n_gendered,
       round(100.0 * sum(gender = 'female') / count(*), 1) AS pct_women
FROM 'principals.parquet'
WHERE gender <> 'unknown' AND deal_type <> '?'
GROUP BY 1 HAVING count(*) >= 40
ORDER BY pct_women DESC;
```

```
┌─────────────────┬────────────┬───────────┐
│    deal_type    │ n_gendered │ pct_women │
├─────────────────┼────────────┼───────────┤
│ sale            │        191 │      30.4 │
│ loan            │        144 │      28.5 │
│ contract        │       3708 │      23.0 │
│ receipt         │       2200 │      10.2 │
│ delivery        │         59 │       5.1 │
└─────────────────┴────────────┴───────────┘
  (abridged: the full result is 15 rows)
```

```sql
-- The monetization transition: gold's share of dated money facts, by century.
SELECT century, count(*) AS n,
       round(sum(system = 'gold') * 1.0 / count(*), 3) AS gold_share
FROM 'monetary.parquet'
WHERE century IS NOT NULL AND system IN ('gold','silver','bronze')
GROUP BY 1 ORDER BY 1;
```

---

## Dataset Structure

### How the tables join

Two provenance keys, both resolving to the source corpus:

- **`stem`** — the *unique* per-document key (DDbDP file stem). Used by the
  person-derived tables (`documents`, `persons`, `principals`).
- **`tm_id`** — the Trismegistos document id, used by the money-derived tables
  (`monetary`, `prices`, `taxes`). **`tm_id` is not unique**: 61,249 documents
  carry 60,862 distinct TM ids, so a `tm_id` join fans out (Pitfall 2).

```
documents ──stem──< persons ──stem+span──> principals ──folded──> persons_distinct
documents ──tm_id──< monetary ──filtered subset──> prices, taxes
persons   ──aggregated by century/region──> autonomy
```

`prices` and `taxes` are not separate extractions: they are `monetary` with
precision filters applied, same grain, same columns plus two.

Referential integrity is exact: 0 of 195,906 `monetary` rows have a `tm_id` absent
from `documents`; 0 of 21,895 `principals` rows have a `stem` absent from
`documents`.

### Character-span provenance

Every fact table carries a start/end offset pair into the canonical text view
(`edited_text`) of its document: `amount_start`/`amount_end` in the money tables,
`person_start`/`person_end` in the person tables. Offsets are **0-based and
end-exclusive** (Python slicing). DuckDB's `substr` is 1-based, so the slice is
`substr(edited_text, start + 1, end - start)`.

### Column reference

"cov" is the percentage of non-null rows, measured on this build — it tells you
what a filter on that column costs.

#### `documents` — the spine (61,249 rows)

One row per text document: metadata plus per-document counts folded in from every
other table. Every document survives the fold, so `0` means "nothing extracted",
not "no data".

| column | type | cov | meaning |
|---|---|---|---|
| `stem` | VARCHAR | 100% | unique document key (DDbDP file stem) |
| `tm_id` | VARCHAR | 100% | Trismegistos id — **not unique**, 60,862 distinct |
| `century` | DOUBLE | 97.1% | signed century from the HGV date (+2 = 2nd c. AD, −2 = 2nd c. BC) |
| `place_pleiades` | DOUBLE | 74.1% | Pleiades id of the document's place |
| `deal_type` | VARCHAR | 100% | primary genre; `'?'` when the corpus gives none (17,932 docs) |
| `n_persons` | BIGINT | 100% | PERSON mentions in the document |
| `n_women_mentions`, `n_men_mentions` | BIGINT | 100% | of those, by attributed gender |
| `n_principals`, `n_women_principals` | BIGINT | 100% | principals, by gender |
| `has_guardian_woman` | BOOLEAN | 100% | a woman with a μετὰ-/χωρὶς-κυρίου formula is present |
| `n_money_facts` | BIGINT | 100% | monetary facts — **folded by `tm_id`, shared by TM-siblings** |
| `has_price`, `has_tax` | BOOLEAN | 100% | a clean price / tax row exists — also `tm_id`-shared |

#### `monetary` — the fact table (195,906 rows)

One row per monetary amount carrying a currency, with its normalized value and
whatever the relation graph attaches: the commodity it prices, that commodity's
quantity and unit, the tax it discharges.

| column | type | cov | meaning |
|---|---|---|---|
| `tm_id` | VARCHAR | 100% | document key (not unique) |
| `amount_start`, `amount_end` | BIGINT | 100% | char span of the amount (0-based, end-exclusive) |
| `amount_text` | VARCHAR | 100% | the Greek surface string of that span |
| `value_num` | DOUBLE | 100% | the decoded numeral inside the span |
| `currency_id` | VARCHAR | 100% | canonical denomination id (see vocabularies) |
| `system` | VARCHAR | 100% | `silver` \| `gold` \| `unknown` — **never aggregate across systems** |
| `value_base` | DOUBLE | 98.7% | value in drachmas (silver) or nomismata (gold) |
| `commodity_id` | VARCHAR | 3.9% | the priced commodity, when a `HAS_PRICE` link exists |
| `quantity` | DOUBLE | 3.4% | how much of it |
| `unit_id` | VARCHAR | 0.3% | the measure (`artaba`, `metretes`, …) |
| `unit_price_base` | DOUBLE | 3.3% | `value_base / quantity` — raw, **over-divides** (Pitfall 4) |
| `tax_id` | VARCHAR | 3.4% | the tax discharged, when a `CHARGED_UNDER` link exists |
| `confidence` | DOUBLE | 100% | labeler confidence — **constant 0.82, carries no information** |
| `date_lo` | DOUBLE | 93.4% | earliest year of the HGV date range (signed; negative = BC) |
| `date_hi` | DOUBLE | 78.3% | latest year of the range |
| `date_mid` | DOUBLE | 94.3% | range midpoint — what `century` is derived from |
| `century` | DOUBLE | 94.3% | signed century, range −4 … +10 |
| `bin50` | DOUBLE | 94.3% | start year of the 50-year bin, floored toward −∞ (`−124 → −150`) |
| `place_pleiades` | DOUBLE | 80.7% | Pleiades id |
| `genres` | VARCHAR | 100% | **JSON array as a string**, e.g. `["list","account"]` (Pitfall 7) |

Low `commodity_id`/`tax_id` coverage is expected: most amounts in a papyrus are
bare sums (a receipt total, a wage, a rent) with nothing attached. The 3.9% that
do carry a commodity are what the price series is made of.

#### `prices` — clean price observations (98 rows)

`monetary` restricted to genuine, comparable **unit prices**. The filters drop the
`value_num == quantity` double-link artifact (48% of naive candidates), bronze
`chalkous`, units that are not the commodity's own dry/liquid measure, and
implausible quantity/price combinations. All `monetary` columns, plus:

| column | type | cov | meaning |
|---|---|---|---|
| `unit_price` | DOUBLE | 100% | drachmas per unit — the series value |
| `commodity` | VARCHAR | 100% | `wheat` (70) \| `wine` (14) \| `barley` (11) \| `oil` (3) |

#### `taxes` — clean tax payments (592 rows)

`monetary` restricted to rows carrying a named tax. These are **payments** (often
installments), not tax *rates*. Cleaner than prices because no per-unit division
is involved. All `monetary` columns, plus:

| column | type | cov | meaning |
|---|---|---|---|
| `payment` | DOUBLE | 100% | the payment in drachmas |
| `tax` | VARCHAR | 100% | `laographia` (539, the poll tax) \| `demosia` (53, the land tax) |

#### `persons` — gendered person mentions (350,206 rows)

Gender and guardian status for **every** PERSON span the NER model found. One row
per *mention*, not per person.

| column | type | cov | meaning |
|---|---|---|---|
| `stem`, `tm_id` | VARCHAR | 100% | document keys |
| `person_start`, `person_end` | BIGINT | 100% | char span of the mention |
| `person_text` | VARCHAR | 100% | the full mention as written ("name son-of-father …") |
| `head_text` | VARCHAR | 100% | the person's own name, split out of the blob |
| `father_text` | VARCHAR | 36.8% | the patronymic, when present |
| `gender` | VARCHAR | 100% | `male` (82,817) \| `female` (22,901) \| `unknown` (244,488) |
| `gender_basis` | VARCHAR | 100% | which rule decided it (see vocabularies) |
| `gender_confidence` | DOUBLE | 100% | 0.0 (unknown) … 0.97 (guardian formula) |
| `guardian` | VARCHAR | 100% | `with` (1,628) \| `without` (143) \| `none` (348,435) |
| `date_mid`, `century`, `bin50` | DOUBLE | 95.9% | document date |
| `place_pleiades` | DOUBLE | 81.7% | Pleiades id |
| `genres` | VARCHAR | 100% | JSON array string |

Only 30% of mentions are gender-attributable, **by design**: the rules fire only
when a name or formula is decisive, and record *which* rule fired rather than
guessing. Nothing is imputed.

#### `principals` — principals, gendered and deal-typed (21,895 rows)

The people a deal turns on: a PERSON the relation model links as `PARTY_OF` a
transaction, or `PAID_BY`/`PAID_TO` an amount, joined to its gender/guardian/
patronymic from `persons`. Spans 11,002 documents. All the `persons` columns
above (with `father_text` at 53.9% — principals are named formally in contracts),
plus:

| column | type | cov | meaning |
|---|---|---|---|
| `roles` | VARCHAR | 100% | sorted, `\|`-joined subset of `party`, `payer`, `payee` |
| `transaction_term` | VARCHAR | 68.9% | the Greek verb/noun naming the deal (`ὁμολογῶ`, `ἐμίσθωσεν`, …) |
| `deal_type` | VARCHAR | 100% | the document's primary genre; `'?'` for 3,514 rows |
| `confidence` | DOUBLE | 100% | relation-model score, 0.34 … 1.00 (median 0.85) — **informative, filter on it** |

#### `persons_distinct` — coreference-lite people (17,362 rows)

Principal *mentions* folded into distinct *people* by a conservative surface key
(normalized name, normalized patronymic, place). Answers "how many distinct
women", not "how many mentions". It **under-merges** — a person named without
their father, or appearing in two nomes, splits into two rows — so the count is an
**upper bound**, the safe direction for a "not fewer than" claim. This is not full
prosopographical coreference.

| column | type | cov | meaning |
|---|---|---|---|
| `person_id` | VARCHAR | 100% | stable 16-hex hash of the identity key; unique, identical across rebuilds |
| `head_text` | VARCHAR | 100% | representative name |
| `father_text` | VARCHAR | 57.7% | representative patronymic |
| `place_pleiades` | DOUBLE | 85.0% | representative place |
| `gender` | VARCHAR | 100% | folded across mentions (attributed beats `unknown`, majority wins) — `female` 1,414 \| `male` 5,608 \| `unknown` 10,340 |
| `guardian` | VARCHAR | 100% | folded with `without` winning: one unambiguous χωρὶς-κυρίου attestation establishes she acted alone |
| `n_mentions` | BIGINT | 100% | mentions folded into this person (max 32) |
| `deal_types` | VARCHAR | 100% | `\|`-joined set of deal types the person appears in |
| `first_century` | DOUBLE | 98.5% | earliest century of attestation |

#### `autonomy` — the published curve (32 rows)

A **derived summary, not a fact table**: the χωρὶς-κυρίου share of guardian-formula
women, by century and by region. Shipped so the headline finding is inspectable.
To re-slice by nome, deal type or a different time granularity, group `principals`
yourself — that is the underlying table.

| column | type | cov | meaning |
|---|---|---|---|
| `dimension` | VARCHAR | 100% | `century` (8 rows) or `region` (24 rows) |
| `bucket` | VARCHAR | 100% | the signed century as a string (e.g. `"3.0"`) or the place name |
| `n_with`, `n_without` | BIGINT | 100% | women attested with / without a guardian |
| `n` | BIGINT | 100% | `n_with + n_without` |
| `autonomous_share` | DOUBLE | 100% | `n_without / n` |

### Controlled vocabularies

Ids are canonical lexicon ids, not surface forms — the labeler resolves inflected
Greek to these before anything is written. Counts are from `monetary` unless noted.

**`system`** · `silver` 140,040 (Ptolemaic–Roman drachma system, base unit the
drachma) · `gold` 54,771 (Byzantine solidus system, base unit the nomisma) ·
`unknown` 1,095 (a money word with no fixed denomination).

**`currency_id`** · *Silver ladder* (1 talent = 6,000 drachmas; 1 drachma = 6
obols; 1 obol = 8 chalkoi): `drachma` 65,672 · `obol` 23,253 · `talent` 12,513 ·
`diobol` 7,317 · `triobol` 7,099 · `chalkous` 6,745 · `hemiobelion` 6,680 ·
`tetrobol` 6,346 · `pentobol` 3,422 · `argyrion` 993 (generic "silver money", no
denomination → `value_base` is null). *Gold* (24 keratia = 1 nomisma): `nomisma`
36,168 · `keration` 18,047 · `chrysion` 556 (generic gold, **including gold as
metal, not only coin**).

**`commodity_id`** · `grain` 2,098 · `garden` 1,066 · `wheat` 1,057 · `wine` 758 ·
`oil` 673 · `barley` 429 · `donkey` 395 · `hay` 212 · `vegetables` 161 · `land` 149 ·
`house` 148 · `camel` 139 · `sheep` 139 (+ a long tail).

**`unit_id`** · `artaba` 399 (dry measure) · `aroura` 59 (land) · `metretes` 34 and
`keramion` 28 (liquid) · `xestes` 26 · `kotyle` 19 · `myriad` 18 · `choinix` 10 ·
`litra` 10 · `naubion` 7 · `pechys` 6.

**`tax_id`** · `prosdiagraphomena` 2,788 (Roman surcharge) · `demosia` 1,722 (land
tax) · `phoros` 700 · `laographia` 574 (poll tax) · `merismos` 349 ·
`phylakitikon` 254 (Ptolemaic police tax) · `telesma` 110 · `stephanikon` 40 ·
`genema` 36 · `syntaxis` 17. **A small tail of ids in this slot are not taxes** —
`drachma` 20, `obol` 3, `hemiobelion` 2, `chalkous`, `chrysion`, `aroura`, `year`,
`time` — 8 ids / 33 dated facts (0.5%), a measured contamination rate. Filter to
the named taxes above rather than taking every non-null `tax_id`.

**`deal_type`** (in `documents`) · `?` 17,932 · `receipt` 15,194 · `contract`
5,117 · `list` 4,193 · `letter_private` 3,603 · `account` 3,342 · `mummy_label`
2,212 · `order` 2,146 · `petition` 1,908 · `letter` 1,724 · `letter_official`
1,228 · `declaration` 734 · `register` 643 · `delivery` 417 · `sale` 318 (+ `loan`,
`lease`, a tail). **`?` means "the corpus records no genre", not "other"** — exclude
it, don't bucket it.

**`gender_basis`** (in `persons`), in precision order · `guardian` 1,770 (a κύριος
formula, conf 0.97) · `nomen` 21,864 (Αὐρήλιος / Αὐρηλία, 0.9) · `kin` 5,781
(θυγάτηρ / υἱός, 0.9) · `gazetteer` 31,153 (attested name list, 0.8) ·
`egypt_prefix` 45,122 (Egyptian `Τα-` female / `Πα-` male, 0.72) · `ethnic` 28 ·
`none` 244,488 (no rule fired → `unknown`).

**`guardian`** · `with` — a μετὰ κυρίου formula (she transacts under a guardian) ·
`without` — χωρὶς κυρίου (she transacts alone) · `none` — no formula in the window.

**`roles`** (in `principals`) · `party` 13,738 · `payee` 3,605 · `payer` 3,176 ·
`party|payee` 1,111 · `party|payer` 227 · `payee|payer` 32 · `party|payee|payer` 6.
Multi-valued: one person can be both a party to the contract and the payer of its
price. Match with `LIKE '%payer%'` or
`list_contains(str_split(roles,'|'),'payer')`, **never with `=`**.

---

## Dataset Creation

### Curation Rationale

Economic historians extract these facts by hand, one papyrus at a time. That
limits every quantitative claim about the ancient economy to the sample one
scholar can read. The goal here was a database where each fact is (a) derived
mechanically from a named revision of a public corpus and (b) traceable to the
exact characters it came from, so a reader can disagree with any individual row.

### Source Data

DDbDP EpiDoc XML at a pinned git revision, parsed into a dual-view text
representation (a diplomatic view and an edited view) at a parse rate of 1.000
over all 67,980 documents; 61,249 carry real text. HGV supplies dates (95–98%
coverage) and places (74–76%, linked to Pleiades authority ids); EpiDoc `<num>`
elements supply decoded numeral values. So dates, places and numerals are
*given* by the corpus, not re-extracted — the database normalizes and assembles
them.

### Annotations

The papyri carry **no entity or relation markup upstream** (0% over a 200-document
audit). All supervision was built for this project:

1. A deterministic lexicon + rules labeler (mined lexicons: 132 entries / 545
   attested surface forms, 0 unattested) produced *silver* labels over ~49k
   training documents.
2. **115 documents form the reference set** — 2,995 entities, 710 relations —
   drafted by one language model and re-checked by a second. Mechanically
   validated (offsets, byte-identity, numeral coverage, schema legality) but
   **not adjudicated by a papyrologist**; the maintainers do not read Ancient
   Greek. Model scores are agreement with this reference, not expert accuracy.
3. Models were silver-pretrained and gold fine-tuned, then run over the whole
   corpus (1,368,079 entities; 228,945 relations).
4. The money layer runs on the rules, not the models, because closed-class
   vocabulary is matched at ceiling by a gazetteer.

### Personal and Sensitive Information

The named individuals are inhabitants of Greco-Roman Egypt who died between
roughly 1,300 and 2,300 years ago, named in documents published openly by
papyrologists for over a century. There is no living-person privacy concern.

Gender attribution is **inferred** from onomastic and formulaic evidence, and is
recorded as an inference with its basis (`gender_basis`) and confidence, never as
ground truth about an individual. It is fit for aggregate history, not for a claim
about any one person.

---

## What has been found with it

Five results, strongest first. Full write-up in the
[project repository](https://github.com/abderahmane-ai/oikonomia); every number
below was recomputed from these shipped tables.

**1. The monetization transition, recovered unsupervised.** Gold's share of dated
money facts sits at ~0.00 for eleven centuries, then **4th c. AD 0.155 → 5th c.
0.931 → 8th c. 1.000** (n = 195,906). That is the textbook silver-to-solidus
transition, reproduced without being told about it. Restricted to *coined* gold
(`nomisma`/`keration`), pre-4th-century attestations number **22** — the earlier
residue is `chrysion`, gold as metal.

**2. The fiscal-regime map periodizes itself.** 6,441 dated tax facts across 18
tax ids: *laographia* (the Roman poll tax) is **560 of 569 in the 1st–3rd c. AD,
zero after, zero in the Ptolemaic centuries**; *prosdiagraphomena* is 99.9% Roman;
*phylakitikon* is 73% Ptolemaic; *demosia* is 1,596 of 1,674 in the 6th–8th c.
Poll-tax medians (~4 dr) read as installments, with a p90 of 16–39 dr matching the
known annual rate.

**3. Women's legal autonomy rises sharply (novel).** The χωρὶς-κυρίου
("without a guardian") share of guardian-formula women: **0% up to the 1st c. AD
(n=646, zero autonomous) → 1.2% (2nd) → 38.8% (3rd) → 80% (4th, n=35)**. Validated
against gold: the over-count is on the μετὰ side, so **the rise is conservative**.
Quote it in tiers, not decimals — the 4th-century cell is directional.

**4. Women as principals, by type of deal (novel).** 21,895 principals; women are
**18.0% of gendered mentions and 20.1% of distinct people**. The finding is the
gradient: **sale 30.4% · loan 28.5% · contract 23.0% vs receipt 10.2% · delivery
5.1%**. Dropping the female-only guardian channel gives a **13.0% floor** and the
ordering survives (Spearman ρ 0.856).

**5. Prices (weakest — flagged as such).** 98 clean observations. Only **2nd c. AD
wheat, 13.33 dr/artaba [IQR 6.0–27.5], n=37** is defensible; the literature says
~7–12, which the IQR brackets. See Limitations.

---

## Bias, Risks, and Limitations

### Limitations

- **`prices` is 98 observations, not a millennium-long series.** Only 2nd c. AD
  wheat (n=37) has enough observations to defend; the 3rd century has 9 and the
  rest fewer. Two known defects remain: `unit_price = value / quantity`
  over-divides where the recorded amount is *already* per-unit, and the non-wheat
  commodities are too sparse to use (some wine rows are unit errors, not prices).
  Treat this table as a validated method on a thin sample, not as a price history.
- **Two different error regimes, never to be blended.** Rules (high precision,
  systematic misses) for money; models (entity F1 0.737 strict, `PARTY_OF` 0.623
  end-to-end) for people. Do not put one error bar across both.
- **Payment direction is absent by choice.** There are no `paid_by`/`paid_to`
  columns. The relation model scores `PAID_BY` at F1 0.145, so direction is
  deliberately missing rather than present and wrong. `principals` records *that*
  someone is party to a deal, not which side of the payment they stand on.
- **58% of principals have no attributable gender**, excluded from gendered shares
  and never imputed. They are **not** damaged text — 100% carry a parsed head
  name; the exclusion reflects closed-vocabulary coverage of the gender rules. One
  rule (the guardian formula) can only ever return *female*, so women's share is
  18.0% including it and **13.0% without it — use 13.0% as the conservative
  floor**. The deal-type ordering is stable either way.
- **Mentions are not people.** `persons` and `principals` are mention-grain;
  `persons_distinct` is the only head-count table, and it under-merges.
- **Survival bias is not correctable.** Everything counts *surviving, published,
  digitized* papyri, skewed toward the Arsinoite nome and dry sites. Shares within
  a bucket are interpretable; raw counts across buckets are not.
- **Dates are HGV's**, assigned to a century by range midpoint, which smears sharp
  transitions across a boundary.
- **Regional labels are findspot-based**, and a papyrus can be written in one nome
  and found in another.

### Pitfalls — read before publishing a number

1. **Never aggregate `value_base` across `system`.** Silver drachmas and Byzantine
   gold nomismata are different metals six centuries apart and are not
   convertible. Always `WHERE system = 'silver'`, or `GROUP BY system`.
2. **`tm_id` is not unique; a `tm_id` join fans out.** 61,249 documents share
   60,862 TM ids. In `documents`, `n_money_facts`/`has_price`/`has_tax` are
   TM-level facts shared across siblings, not document-level ones.
3. **Mentions ≠ people.** Women are 18.0% of principal *mentions* and 20.1% of
   distinct gendered principals — different denominators, both correct. Say which.
4. **`monetary.unit_price_base` over-divides** and must not be used for a
   published series. Use `prices.unit_price`, which has the filters applied.
5. **`confidence` means two different things.** In `monetary`/`prices`/`taxes` it
   is the rule labeler's constant 0.82 and carries no information — filtering on it
   does nothing. In `principals` it is the relation model's score (0.34–1.00,
   median 0.85) and *is* a usable precision knob.
6. **Trust the contrasts, not the absolute totals.** Extraction error is real, so
   the robust claims are relative ones — across deal types, centuries, regions —
   where error is roughly common-mode.
7. **`genres` is a JSON string**, not a list: query it with
   `list_contains(cast(json(genres) AS VARCHAR[]), 'receipt')`, or just use the
   already-resolved `deal_type`.
8. **`century` skips year zero, and `'?'` is not a category.** +1 covers 1–100 AD,
   −1 covers 1–100 BC, so `abs()` merges a BC and an AD century. `bin50` floors
   toward −∞ and is safe to sort across the BC/AD line.

### Recommendations

Report the denominator you used (mentions vs people, gendered vs all). Prefer
within-bucket shares to cross-bucket counts. When a claim rests on a small cell,
give n — several buckets here are under 50 rows. And when a single row matters,
follow its span back to the papyrus and read it.

---

## Reproducibility

Re-running the pipeline at the same `corpus_rev` reproduces every table
bit-for-bit: the assembly stages are deterministic and the two model outputs are
frozen artifacts. `manifest.json` in the repo records the revision, schema
version, licence and per-table inventory, so the export is self-describing.

```bash
oik db build --sample 0   # monetary facts  → monetary.parquet
oik db prices             # price series    → prices.parquet
oik db taxes              # tax payments    → taxes.parquet
oik db persons            # gendered people → persons.parquet
oik db autonomy           # the curve       → autonomy.parquet
oik db principals         # principals      → principals.parquet
oik db export             # spine + people  → export/
```

---

## Citation

Source texts are derived from the **Duke Databank of Documentary Papyri** (DDbDP)
and the **Heidelberger Gesamtverzeichnis** (HGV) under CC BY 3.0, which requires
attribution. Please cite both the corpus and this dataset.

```bibtex
@dataset{oikonomia_db_2026,
  author    = {Ainouche, Abderahmane},
  title     = {{OIKONOMIA-DB}: An Auditable Economic Database of Greco-Roman Egypt},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db}
}
```

Duke Databank of Documentary Papyri (DDbDP), Duke Collaboratory for Classics
Computing (DC3) and papyri.info, CC BY 3.0.

## Dataset Card Contact

Issues and corrections: https://github.com/abderahmane-ai/oikonomia/issues
