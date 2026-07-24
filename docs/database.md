# The OIKONOMIA database (deliverable #2)

A structured, auditable database of everyday economic life in the ~68,000
documentary papyri of Greco-Roman Egypt. **Every row traces to a character span in
a specific document at a pinned corpus revision** — nothing is asserted that cannot
be checked against the Greek text.

- **Source corpus:** Duke Databank of Documentary Papyri (DDbDP) + HGV metadata,
  via [`papyri/idp.data`](https://github.com/papyri/idp.data), **licence CC BY 3.0**.
- **Pinned revision:** `d7a34f302d1e44e271256092c2b780733187b478` (recorded in every
  export's `manifest.json` as `corpus_rev`).
- **Universe:** the **61,249** documents that carry real edited text (of 67,980 DDbDP
  documents; the rest are empty/lost).

Regenerate the whole package (deterministic, laptop, no GPU) with:

```bash
oik db build --sample 0   # monetary facts   → db/monetary.parquet
oik db prices             # price series      → db/prices.parquet
oik db taxes              # tax payments      → db/taxes.parquet
oik db persons            # gendered persons  → db/persons.parquet   (needs ner_corpus.jsonl)
oik db principals         # principals        → db/principals.parquet (needs re_corpus.jsonl)
oik db export             # package + index   → db/export/{documents,persons_distinct}.parquet + manifest.json
```

## How the tables join

Two provenance keys, both resolving back to `corpus.parquet` at `corpus_rev`:

- **`stem`** — the *unique* per-document key (the DDbDP file stem). Person-derived
  tables (`persons`, `principals`, `documents`) key on it.
- **`tm_id`** — the Trismegistos document id. Money-derived tables (`monetary`,
  `prices`, `taxes`) key on it. ⚠️ **`tm_id` is not unique** — ~1,706 documents
  share a TM id with a sibling. So a `tm_id`-join fans out across siblings: in
  `documents`, `n_money_facts` / `has_price` / `has_tax` are shared by TM-siblings.
  For per-document money precision, join back through `corpus.parquet`
  (`stem → tm_id`) and disambiguate on the char span.

Every table with a `char-span` key (`amount_start/end`, `person_start/end`, …)
indexes into `corpus.parquet.edited_text` for that document — the canonical text
view. Dates are the HGV `date_lo/hi` (→ `date_mid`, `century`, `bin50`); places are
Pleiades ids; genres are the canonical genre list (→ `deal_type` = the primary one).

## Tables

### `documents` — the spine (61,249 rows, key `stem`)
One row per text document: its metadata plus per-document counts folded in from
every other table. The queryable entry point ("3c-AD `sale` docs with a female
principal and a price").

| column | meaning |
|---|---|
| `stem`, `tm_id` | provenance keys (see above) |
| `century`, `place_pleiades`, `deal_type` | HGV date → signed century; Pleiades place; primary genre |
| `n_persons`, `n_women_mentions`, `n_men_mentions` | PERSON mentions in the doc, by attributed gender |
| `n_principals`, `n_women_principals` | principals (PARTY_OF/PAID_* heads), by gender |
| `has_guardian_woman` | a woman with a μετὰ/χωρὶς-κυρίου formula is present |
| `n_money_facts`, `has_price`, `has_tax` | money facts / clean price / clean tax (by `tm_id`, TM-shared) |

### `persons_distinct` — coreference-lite people (17,362 rows, key `name+father+place`)
Principal *mentions* folded into distinct *people* by a conservative surface key
(normalized own-name + patronymic + place; see `oikonomia.db.identity`). **Answers
"how many distinct women", not "how many mentions".** It *under*-merges (a person
named without a father, or in two nomes, splits), so the count is an **upper bound**
on the true number of people — safe for a "not fewer than" claim; it is **not** full
prosopographical coreference.

| column | meaning |
|---|---|
| `head_text`, `father_text`, `place_pleiades` | representative name / patronymic / place |
| `gender`, `guardian` | folded across the person's mentions (χωρὶς wins: one autonomous attestation establishes it) |
| `n_mentions` | how many mentions folded into this person |
| `deal_types`, `first_century` | the set of deal types this person appears in; earliest century |

### `monetary` — the fact table (195,906 rows, key `tm_id` + char-span)
One row per monetary amount, with its normalized value and graph links (currency,
commodity+quantity+unit → a per-unit price, tax term). `value_base` is in drachmas
(silver) or nomismata (gold) — **never sum across differing `system`**.
Derived by `oik db build` from the deterministic lexicon labeler + decoded `<num>`
values. Columns: `value_num`, `currency_id`, `system`, `value_base`, `commodity_id`,
`quantity`, `unit_id`, `unit_price_base` (= `value_base/quantity`), `tax_id`, plus
date/place/genre and the `amount_*` span.

### `prices` — clean price observations (98 rows, key `tm_id` + char-span)
The high-precision priced subset (silver only, the commodity's own dry/liquid
measure, double-link and implausible rows dropped — see `oikonomia.db.prices`).
Adds `unit_price` (dr/unit) and `commodity`. Precision over recall: it feeds a
*published* series (wheat reproduces the literature: Ptolemaic ~2, Roman 2c AD ~10–13).

### `taxes` — clean tax payments (592 rows, key `tm_id` + char-span)
Poll- and land-tax *payments* (installments, not rates). Adds `payment` and `tax`.
Supports the fiscal-regime map and the poll-tax-by-century/region view.

### `persons` — gendered person mentions (350,206 rows, key `stem` + char-span)
Gender + guardian for **every** model-extracted PERSON span (`ner_corpus.jsonl`).
`head_text`/`father_text` are the split-person name/patronymic; `gender_basis` is
the rule of record (guardian / nomen / kin / …); `guardian` ∈ {with, without, none}
types the μετὰ/χωρὶς-κυρίου formula. Drives the autonomy finding.

### `principals` — principals, gendered + deal-typed (21,895 rows, key `stem` + char-span)
The people a deal turns on: a PERSON that the RE model links as `PARTY_OF` a
transaction or `PAID_BY`/`PAID_TO` an amount (`re_corpus.jsonl`), joined to its
gender/guardian/patronymic from `persons`. `roles` (party|payer|payee),
`transaction_term`, `deal_type`, `confidence`. Drives the women-as-principals
finding (women 18.0% of mentions / 20.1% of distinct people; sale 30% / loan 28% vs
receipt/delivery 5–10%).

## Findings this database supports

| finding | tables | headline |
|---|---|---|
| Commodity prices | `prices`, `monetary` | wheat 2c AD ~10–13 dr/artaba (reproduces the literature) |
| Fiscal history | `taxes`, `monetary` | laographia Roman-only; demosia the Byzantine land tax |
| Women's autonomy | `persons` | χωρὶς-κυρίου share 0%→39%→80% over 3c→4c AD (*ius liberorum*) |
| Women as principals | `principals`, `persons_distinct` | 20.1% of distinct principals; concentrated in sale/loan |

## Provenance & reproducibility

`manifest.json` (written by `oik db export`) records the `corpus_rev`,
`schema_version`, generation timestamp, licence, and — per table — grain, key, row
count and columns. Re-running the pipeline at the same `corpus_rev` reproduces every
table bit-for-bit (the stages are deterministic). Extraction uses the released
papyri Greek NER + RE models (deliverable #1); the price/tax layer is rule-based
over the mined lexicons. Extraction is imperfect (entity NER strict F1 0.737;
end-to-end PARTY_OF ≈ 0.62), so counts carry extraction error — the **relative**
comparisons (deal type, century, region) are the robust claims, not exact totals.
