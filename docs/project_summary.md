# 🏛️ OIKONOMIA: Master Project Summary & Technical Overview

**Author:** Abderahmane Ainouche ([`ainouche-abderahmane`](https://huggingface.co/ainouche-abderahmane))  
**Repository:** [`github.com/abderahmane-ai/oikonomia`](https://github.com/abderahmane-ai/oikonomia)  
**License:** Code (MIT) · Corpus & Data (CC BY 3.0) · Models (Apache 2.0)

---

## Executive Summary

**OIKONOMIA** is an end-to-end artificial intelligence framework and structured quantitative database built to automate information extraction across the entire surviving corpus of documentary papyri from Greco-Roman Egypt (**68,000 texts** spanning 300 BCE – 700 CE).

Papyri—tax receipts, leases, loans, wage lists, census returns, private letters, and legal declarations—form the primary empirical source for the everyday economic history of antiquity. Historically, extracting economic facts required manual reading by specialized papyrologists over decades. OIKONOMIA automates this information extraction at corpus scale while preserving **100% byte-exact character-span provenance** `(tm_id, stem, start_char, end_char)` linking every single extracted fact directly back to original EpiDoc XML source text in the Duke Databank of Documentary Papyri (DDbDP).

---

## 🎯 The Three Core Deliverables

OIKONOMIA delivers three fully open-source, peer-audited components:

### 1. 🤖 **Deliverable #1: Open Deep Learning Models**
Two domain-adapted transformer models built on a papyri-adapted [`bowphs/GreBerta`](https://huggingface.co/bowphs/GreBerta) backbone (pre-trained on 8.25M papyri tokens down to **4.54 perplexity**):

- **OIKONOMIA-Grammateus (Named Entity Recognition):**  
  * *Meaning:* ***Γραμματεύς*** (*Grammateus*) — Ancient Greek for "The Scribe".
  * *Task:* 31 BIO token classification head recognizing economic amounts, commodities, currencies, dates, places, tax terms, person roles, and legal statuses.
  * *Performance:* **Strict F1: 0.737 / Relaxed F1: 0.837** (5-fold cross-validation on 115-doc all-human gold benchmark).
  * *Hugging Face Hub:* [`ainouche-abderahmane/grammateus`](https://huggingface.co/ainouche-abderahmane/grammateus)

- **OIKONOMIA-Homologia (Relation Extraction):**  
  * *Meaning:* ***Ὁμολογία*** (*Homologia*) — Ancient Greek for "The Agreement / Contract".
  * *Task:* Span-pair relation classifier scoring entity pairs across 9 economic & kinship relation types (`PARTY_OF`, `HAS_UNIT`, `HAS_CURRENCY`, `CHILD_OF`, `PAID_BY`, `PAID_TO`, etc.).
  * *Performance:* **Micro F1: 0.721 / Precision: 0.762** (`HAS_UNIT` 0.916, `PARTY_OF` 0.705).
  * *Hugging Face Hub:* [`ainouche-abderahmane/homologia`](https://huggingface.co/ainouche-abderahmane/homologia)

---

### 2. 🗂️ **Deliverable #2: Derived Database (`oikonomia.db`)**
A structured, hyper-compressed 8-table Parquet database (**12.3 MB total**) queryable via DuckDB or Pandas:

| Table | File Path | Rows | Grain (One row =) | Join Key |
|---|---|---:|---|---|
| `monetary` | `monetary.parquet` | **195,906** | One normalized monetary fact | `tm_id` + char span |
| `prices` | `prices.parquet` | **98** | One clean commodity price observation | `tm_id` + char span |
| `taxes` | `taxes.parquet` | **592** | One clean tax payment installment | `tm_id` + char span |
| `persons` | `persons.parquet` | **350,206** | One `PERSON` mention + gender | `stem` + char span |
| `principals` | `principals.parquet` | **21,895** | One transaction principal + deal type | `stem` + char span |
| `autonomy` | `autonomy.parquet` | **32** | One 800-year female guardianship bucket | `dimension` + `bucket` |
| `documents` | `export/documents.parquet` | **61,249** | Master document metadata & text spine | `stem` / `tm_id` |
| `persons_distinct` | `export/persons_distinct.parquet` | **17,362** | Deduplicated distinct person registry | `person_id` |

* *Hugging Face Datasets Hub:* [`ainouche-abderahmane/oikonomia-db`](https://huggingface.co/datasets/ainouche-abderahmane/oikonomia-db)

---

### 3. 📜 **Deliverable #3: Historical Discoveries & Findings**

Five findings, ranked by evidential strength, are recorded in
[`docs/phases/phase_10_findings.md`](phases/phase_10_findings.md) — each with its
mechanism, the known history it has to recover as a control, and its limits. Two
are *validation* findings (already-known history, recovered unsupervised); two are
*novel* counts at a scale nobody has done by hand; one is honest but thin.

#### 🪙 **F1: The silver→gold monetization transition** *(validation, strongest)*
- Gold's share of dated money facts: **eleven centuries at ~0.00, then 4th c. AD 0.155 → 5th c. 0.931 → 8th c. 1.000.**
- Recovers the collapse of the Alexandrian silver tetradrachm and Constantine's gold *solidus* (309–312 AD) from raw text, with no historical input. n = 195,906 facts.

#### 🏛️ **F2: The fiscal-regime map** *(validation)*
- 6,441 tax facts across 18 named taxes periodize themselves: *laographia* (poll tax) **560 of 569 attestations in the 1st–3rd c. AD, zero after, zero in the 3rd/2nd c. BC**; *prosdiagraphomena* 99.9% Roman; *phylakitikon* 73% Ptolemaic; *demosia* 1,596 of 1,674 in the 6th–8th c. AD.
- Poll-tax payments: corpus-wide median **~4 dr** (an installment, not an annual assessment), p90 **16–39 dr**, which brackets the known annual rate.

#### 👩 **F3: The female autonomy curve** *(novel, model-driven)*
- Women's **χωρὶς-κυρίου (unguardianed) share by century: 0% (≤1st c. AD) → 1% (2nd) → 39% (3rd) → 80% (4th)** — the spread of the *ius liberorum* and the decline of *tutela mulierum*, unsupervised.
- Gold-validated: the gender rules are 100% deterministic (613/613 matched spans), and the over-count sits on the *with-guardian* side, so **the rise is conservative**. Denominators thin sharply after the 3rd century (n=35 in the 4th).

#### 🤝 **F4: Women as principals, by deal type** *(novel, model-driven)*
- **21,895 principals; women are 18.0% of mentions and 20.1% of distinct people.** The finding is the **gradient**, not the average: **sale 30.4% · loan 28.5% · contract 23.0%** versus **receipt 10.2% · delivery 5.1%** — property transactions versus fiscal paperwork.
- End-to-end `PARTY_OF` F1 is 0.623, so the **ordering** is the result and the exact percentages are approximate; the ordering is stable for every bucket with n ≥ 40.

#### 🌾 **F5: Commodity prices** *(real, but thin — the weakest)*
- **98 clean observations.** Only **2nd c. AD wheat (n=37, median 13.33 dr/artaba, IQR 6.0–27.5)** is defensible; its IQR brackets the literature (~7–12 dr).
- The other buckets have single-digit n, the per-unit arithmetic over-divides where an amount is already per-unit, and the non-wheat commodities are too sparse to report. This is a validated method on a thin sample, **not a price history**.

---

## 🛠️ Key Technical & Engineering Innovations

1. **Two-Stage Weak-to-Clean Silver-to-Gold Fine-Tuning Recipe:**  
   Solves weak label noise by pre-training on 48,900 weakly labeled silver documents before fine-tuning on 115 human-validated gold documents (+9.5 strict F1 lift).
2. **Long-Document Windowing Engine:**  
   Implemented `plan_windows` (`stride=64`, `max_length=512`) and `merge_window_spans` to run neural inference over long legal registers without losing entity or relation spans to context truncation.
3. **Name Decomposition Parser (`parse_person_name`):**  
   Decomposes raw Greek `PERSON` text blobs into head names, patronymics, metronymics, and statuses, recovering **128,896 father links (99% patronymic recall)**.
4. **Monetary System Separation:**  
   Strictly separates Ptolemaic-Roman **Silver Drachmas (140,040 facts)** from Byzantine **Gold Solidi (54,771 facts)** to prevent invalid cross-system mathematical summations.
5. **Deterministic Pipeline & Licence Firewall:**  
   Uses SHA256 manifest keying (`data/.manifests/`) for 100% reproducible pipeline execution and includes an automated licence firewall (`assert_releasable`) ensuring no NonCommercial dependencies leak into model weights.

---

## 🧪 Quality & Verification Suite

- **Test Suite:** **612 / 612 automated unit and integration tests passing green** (`.venv/bin/python -m pytest`).
- **Static Analysis:** 100% clean under `ruff` and `mypy` across 86 Python modules.
- **Documentation:** Complete manuals in `docs/database.md`, DuckDB view script in `docs/db.sql`, 11 phase write-ups in `docs/phases/`, and model cards in `resources/release/`.

---

*OIKONOMIA stands as a complete, publication-ready research platform combining state-of-the-art Natural Language Processing, software engineering discipline, and digital papyrological discovery.*
