---
license: cc-by-3.0
language:
- grc
tags:
- papyrology
- ancient-greek
- economic-history
- digital-humanities
- dataset
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

# OIKONOMIA-DB: A 195,000-Fact Database of Economic Life in Greco-Roman Egypt

**OIKONOMIA-DB** is a structured, auditable Parquet database derived from **61,249 text-bearing documentary papyri** of Greco-Roman Egypt (300 BCE – 700 CE). Every extracted fact carries byte-exact character-span provenance `(tm_id, stem, start_char, end_char)` linking directly back to original EpiDoc XML text in the Duke Databank of Documentary Papyri (DDbDP) at pinned corpus revision `d7a34f302d1e44e271256092c2b780733187b478`.

---

## 🗂️ Tables at a Glance

| Table | File Path | Rows | Grain (One row =) | Primary Join Key |
|---|---|---:|---|---|
| `documents` | `export/documents.parquet` | **61,249** | One text document | `stem` / `tm_id` |
| `persons_distinct` | `export/persons_distinct.parquet` | **17,362** | One distinct person (coref-lite) | `person_id` |
| `monetary` | `monetary.parquet` | **195,906** | One monetary amount | `tm_id` + char span |
| `prices` | `prices.parquet` | **98** | One clean price observation | `tm_id` + char span |
| `taxes` | `taxes.parquet` | **592** | One clean tax payment | `tm_id` + char span |
| `persons` | `persons.parquet` | **350,206** | One `PERSON` mention | `stem` + char span |
| `principals` | `principals.parquet` | **21,895** | One transaction principal | `stem` + char span |
| `autonomy` | `autonomy.parquet` | **32** | One time/region bucket | `dimension` + `bucket` |

The first seven are **data**. `autonomy` is different: it is a **derived summary**
(a published aggregate of `principals` × century/region), shipped so the headline
finding is inspectable, not because it is a source of new facts. To re-slice the
autonomy question by nome, document type or a different time granularity, group
`principals.parquet` yourself — that is the underlying table.

`person_id` is a stable 16-hex-char hash of the coreference-lite identity key
(normalized name + patronymic + place). It is deterministic across rebuilds. The
key under-merges rather than over-merges, so 17,362 is an **upper bound** on the
true number of distinct people.

---

## ⬇️ Getting the data

One table, straight into a dataframe:

```python
from datasets import load_dataset

prices = load_dataset("ainouche-abderahmane/oikonomia-db", "prices", split="train")
```

Every config name in the table above works: `monetary`, `prices`, `taxes`,
`persons`, `principals`, `autonomy`, `documents`, `persons_distinct`.

The whole database (14 MB) as local Parquet files:

```python
from huggingface_hub import snapshot_download

path = snapshot_download("ainouche-abderahmane/oikonomia-db", repo_type="dataset")
```

Or without Python at all:

```bash
hf download ainouche-abderahmane/oikonomia-db --repo-type dataset --local-dir oikonomia-db
```

---

## 💻 Quickstart (DuckDB & Python)

Query the Parquet tables directly in DuckDB with zero import step (run from the
directory you downloaded them into):

```sql
-- Wheat prices by century. n is small outside the 2nd century AD — see Limitations.
SELECT century, count(*) AS n, round(median(unit_price), 2) AS dr_per_artaba
FROM 'prices.parquet'
WHERE commodity = 'wheat'
GROUP BY 1 ORDER BY 1;
```

```python
import duckdb

con = duckdb.connect()
# Query women's share of transaction principals by deal type
df = con.execute("""
    SELECT deal_type, count(*) AS n,
           round(100.0 * sum(gender = 'female')
                 / nullif(sum(gender IN ('male','female')), 0), 1) AS pct_women
    FROM 'principals.parquet'
    WHERE deal_type <> '?'
    GROUP BY 1 HAVING sum(gender IN ('male','female')) >= 40 ORDER BY pct_women DESC;
""").df()
print(df)
```

---

## 🔍 Structural Provenance & Integrity

- **Span-Level Auditability:** Every row in `monetary`, `prices`, `taxes`, `persons`, and `principals` links back to `(document, start_char, end_char)` in `corpus.parquet`.
- **Metal Currency System Separation:** Ptolemaic-Roman **Silver Drachmas (140,040 facts)** and Byzantine **Gold Solidi (54,771 facts)** are strictly separated in `monetary.parquet` (`system = 'silver'` vs. `system = 'gold'`) to prevent invalid cross-system summation.
- **Authority Linking:** Geography linked to [Pleiades Gazetteers](https://pleiades.stoa.org/), dates normalized to HGV, and EpiDoc `<num>` tags decoded.

---

## ⚠️ Limitations — read before quoting a number

- **`prices` is 98 observations, not a millennium-long series.** Only **2nd
  century AD wheat (n=37, median 13.33 dr/artaba, IQR 6–27.5)** has enough
  observations to defend; the 3rd century has 9 and the rest fewer. Two known
  defects remain: `unit_price = value / quantity` over-divides where the recorded
  amount is already per-unit, and the non-wheat commodities are too sparse to use
  (some wine rows are unit errors, not prices). Treat this table as a validated
  method on a thin sample, not as a price history.
- **Two different error regimes.** `monetary`, `prices` and `taxes` come from a
  lexicon + deterministic rules — high precision, closed vocabulary, systematic
  misses. `persons` and `principals` come from the trained models, whose measured
  end-to-end accuracy is entity F1 0.737 (strict) and `PARTY_OF` 0.623 on
  predicted entities. Do not blend an error bar across the two.
- **Payment direction is not in this database.** There are no `paid_by` /
  `paid_to` columns. The relation model scores direction at `PAID_BY` F1 0.145,
  too low to ship, so "who paid whom" is deliberately absent rather than present
  and wrong. `principals` records *that* someone is a party to a deal, not which
  side of the payment they stand on.
- **58% of principals have no attributable gender** and are excluded from the
  gendered shares, never imputed. They are **not** damaged text — 100% carry a
  parsed head name; exclusion reflects closed-vocabulary coverage of the gender
  rules. One of those rules (the guardian formula) can only ever return *female*,
  so women's share is **18.0% including it and 13.0% without it** — use 13.0% as
  the conservative floor. The deal-type ordering is stable across both.
- **Mentions are not people.** `persons` and `principals` count mentions;
  `persons_distinct` is the only head-count table.
- **Survival bias is not correctable.** Everything here counts *surviving,
  published, digitized* papyri, skewed toward the Arsinoite nome and dry sites.
  Shares within a bucket are interpretable; raw counts across buckets are not.
- **Dates are HGV's**, assigned to a century by range midpoint, which smears
  sharp transitions.

---

## 📜 Citation & Attribution

Source papyrological texts are derived from the **Duke Databank of Documentary Papyri (DDbDP)** and **Heidelberg Gesamtverzeichnis (HGV)** under **CC BY 3.0**.

```bibtex
@dataset{oikonomia_db_2026,
  author       = {Ainouche, Abderahmane},
  title        = {OIKONOMIA-DB: A 195,000-Fact Database of Economic Life in Greco-Roman Egypt},
  year         = {2026},
  publisher    = {Hugging Face},
  url          = {https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db}
}
```
