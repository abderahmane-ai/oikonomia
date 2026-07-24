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
dataset_info:
  features:
  - name: monetary
    description: 195,906 extracted monetary facts with character-span provenance
  - name: prices
    description: 98 clean commodity price series across 10 centuries
  - name: taxes
    description: 592 named tax payment attestations
  - name: persons
    description: 350,206 gendered person attestations
  - name: principals
    description: 21,895 economic transaction principals
  - name: autonomy
    description: 800-year legal autonomy curve of women
  - name: documents
    description: 61,249 master document join spine
  - name: persons_distinct
    description: 17,362 deduplicated distinct individuals
---

# OIKONOMIA-DB: A 195,000-Fact Database of Economic Life in Greco-Roman Egypt

**OIKONOMIA-DB** is a structured, auditable Parquet database derived from **61,249 text-bearing documentary papyri** of Greco-Roman Egypt (300 BCE – 700 CE). Every extracted fact carries byte-exact character-span provenance `(tm_id, stem, start_char, end_char)` linking directly back to original EpiDoc XML text in the Duke Databank of Documentary Papyri (DDbDP) at pinned corpus revision `d7a34f302d1e44e271256092c2b780733187b478`.

---

## 🗂️ Tables at a Glance

| Table | File Path | Rows | Grain (One row =) | Primary Join Key |
|---|---|---:|---|---|
| `documents` | `export/documents.parquet` | **61,249** | One text document | `stem` / `tm_id` |
| `persons_distinct` | `export/persons_distinct.parquet` | **17,362** | One distinct person | `person_id` |
| `monetary` | `monetary.parquet` | **195,906** | One monetary amount | `tm_id` + char span |
| `prices` | `prices.parquet` | **98** | One clean price observation | `tm_id` + char span |
| `taxes` | `taxes.parquet` | **592** | One clean tax payment | `tm_id` + char span |
| `persons` | `persons.parquet` | **350,206** | One `PERSON` mention | `stem` + char span |
| `principals` | `principals.parquet` | **21,895** | One transaction principal | `stem` + char span |
| `autonomy` | `autonomy.parquet` | **32** | One time/region bucket | `dimension` + `bucket` |

---

## 💻 Quickstart (DuckDB & Python)

Query the Parquet tables directly in DuckDB with zero import step:

```sql
-- Query wheat price series across centuries
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

## 📜 Citation & Attribution

Source papyrological texts are derived from the **Duke Databank of Documentary Papyri (DDbDP)** and **Heidelberg Gesamtverzeichnis (HGV)** under **CC BY 3.0**.

```bibtex
@dataset{oikonomia_db_2026,
  author       = {Ainouche, Abderahmane},
  title        = {OIKONOMIA-DB: A 195,000-Fact Database of Economic Life, Commodity Inflation, and Female Legal Autonomy in Greco-Roman Egypt},
  year         = {2026},
  publisher    = {Hugging Face},
  url          = {https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db}
}
```
