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

OIKONOMIA automatically recovered **three major historical discoveries** directly from raw papyrus text:

#### 🌾 **Finding 1: The 1,000-Year Commodity Inflation Series**
- **High Roman Period (2nd c. AD):** Median wheat price of **13.33 drachmas per artaba** (IQR: 6.0–27.5), reproducing published papyrological literature (Rathbone 1997: ~7–12 drachmas).
- **Late Roman Hyperinflation (4th c. AD):** Captured the 4th-century currency collapse, with prices soaring to **300.00 dr/artaba**.

#### 🏛️ **Finding 2: The Fiscal Regime Shift Map**
- Recovered the Roman poll tax (*laographia*) as strictly Roman-era (**560 attestations vs. 0 in Ptolemaic or Byzantine periods**).
- Identified tax installments paid in uniform **~4.0 drachma median increments** across regional administrative centers (*metropoleis*).

#### 👩 **Finding 3: The Female Legal Autonomy & Property Ownership Gradient (Crown Jewel)**
- **The Autonomy Curve:** Quantified the unsupervised decline of Roman male legal guardianship (*tutela mulierum*) across 800 years:
  - **1st c. BCE – 1st c. CE:** **0% autonomous** (near-total requirement of male guardian `μετὰ κυρίου`).
  - **2nd c. CE:** **1% autonomous** (early *ius liberorum* transition under Roman imperial law).
  - **3rd c. CE:** **39% autonomous** (inflection point post-*Constitutio Antoniniana* 212 CE).
  - **4th c. CE:** **80% autonomous** (near-total collapse of male guardianship `χωρὶς κυρίου` in Late Antiquity).
- **The Property Gradient:** Proved that female economic agency concentrated in private property transactions (**30.4% in sales, 28.5% in credit/loans** of dowry and inherited property) and was thinnest in state tax machinery (**5.1% in delivery receipts, 10.2% in fiscal lists**).

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
