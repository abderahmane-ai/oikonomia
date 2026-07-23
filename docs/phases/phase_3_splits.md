# Phase 3 — Dataset Splits

### ✅ Phase 3 — Splits (done)

**Why it got its own phase:** splits are small in code and irreversible in
practice. Once models are trained and numbers published nobody re-does them, so
the only defence against a quietly wrong split is being able to rebuild and
inspect it. `build_splits` is a versioned stage like everything else.

**Deliverables**
- `splits/dedup.py` — MinHash + LSH near-duplicate clustering over character
  5-gram shingles of the *folded* text. 128 permutations, 16 bands, Jaccard
  threshold 0.8, seeded and deterministic.
- `splits/assign.py` — group-aware stratified assignment (`random`) and
  temporal holdout (`chronological`), plus `report_split` which verifies no
  group straddles a split.
- `splits/build.py` — the stage → `processed/splits.parquet` + report.
- CLI `oik splits {build,report,check}`. 26 tests.

**Results over the 61,249 documents with real text**
- **475 duplicate clusters covering 1,769 docs (2.89%)**. These would have
  leaked across a naive random split. *(Was 399 / 1,553 / 2.54% before the
  `<lb break="no"/>` parser fix — see §7. Split words made near-duplicates look
  different from each other, so the old figure understated leakage by 216
  documents. Detected only because the fixed parser forced a rebuild.)*
- 59,581 atomic groups. Grouping unions two signals: shared TM id and
  near-duplicate cluster.
- `random`: 49,004 / 6,145 / 6,100. Max stratum drift **0.0078**, stratum TV
  distance 0.0023 — i.e. every stratum is split ~80/10/10, not just the corpus.
- `chronological`: train −350→466 CE, dev 466→625, test 600→1050. Residual
  temporal overlap **0.07%** (35 docs), reported rather than hidden.

**Two decisions worth keeping**
- **Publication volume is NOT a grouping signal.** It is right in spirit
  (fragments of a roll share a volume) but the largest volume holds 2,023
  documents; grouping there would force whole volumes into one split and make
  stratification impossible. Group on evidence of textual identity instead.
- **Undated documents go to train in the chronological regime.** They cannot
  support a claim about temporal generalisation, and putting them in test would
  dilute the exact measurement the regime exists to make.

**Bug worth remembering:** the first implementation balanced splits against a
*global* deficit. Train's deficit is largest until it is nearly full, so whole
strata landed in train and only the strata processed last were divided —
`receipt|high_roman` came out 33/33/33 and every `nogenre|*` stratum went 100%
to train. **The corpus-level 80/10/10 was exact throughout**, which is what
made it invisible. Only a per-stratum assertion catches it; there is now a test
that fails on the old algorithm and passes on the new one.
