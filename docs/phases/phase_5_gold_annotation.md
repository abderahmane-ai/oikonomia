# Phase 5 — Gold Annotation

### ✅ Phase 5 — Gold annotation (115 docs, ALL human_validated)

**Status: 115 documents** (`data/gold/annotated.jsonl`, **2,995 entities /
623 relations**, `oik gold check` **0 errors**, `numerals_checked: true`, every
text byte-identical to `corpus.parquet`). **All 115 are now
`provenance: human_validated` / `reviewed_by: abderahmane-ai`** — the owner
reviewed this session's 20 model-drafts (13 hard-batch + 7 AGE-targeted), so the
whole set is a clean eval/fine-tune anchor with no draft-scoring-draft
circularity (the Phase-7b "±few pts from un-reviewed drafts" caveat is now
retired). Drafted by `claude-opus-4-8`, reviewed by the owner. Guidelines **v0.3**.

#### AGE un-starved: 6 → 133 (2026-07-22, second half of session)

AGE was the last unlearnable class (6 instances; Phase-7b scored it 0.0). Fixed
by mining the **train split** for the census/signalement age formula
`(ὡς) ἐτῶν N` (`scratchpad/find_age_docs*.py`: rank by age-numeral density, dedup
by `group_id`, exclude gold), then annotating **7 age-dense docs** →
**+127 AGE** (now 133, a fully learnable class):
- `25173 26167 27453 11440 29529` — signalement/poll-tax lists where **every
  tagged numeral is an age**; AGE spans generated **directly from the corpus
  `<num>` offsets** (`scratchpad/age_build.py`, `age_all=True`) — zero surface
  ambiguity — with names forward-scanned. `11440` alone: 33 ages + 62 PERSON
  (registrant + mother, per the mother rule). `29529`'s trailing `N φυλῆς` tribe
  ordinals are `non_referential` skips.
- `12351` (grazing lease, 12 witness-ages + a freedman `ἀπελεύθερος`) and
  `12906` (epikrisis, 14 ages + `δοῦλος`/`ἰδιώτης` statuses) — mixed age+date
  docs, every span explicit; the `θ ἔτει`/`ιζ ἔτους` regnal years correctly went
  to DATE_REF, not AGE (verified: no date numeral mislabeled as age).

Session entity lift (committed HEAD 85 docs → 115): **AGE +127, PERSON +288,
TAX_TERM +45, FRACTION +35, PERSON_ROLE +23, OCCUPATION +70** (total +1,042
entities). Every AGE numeral gate-verified; `find_age_docs2.py` still lists ~900
more train age-docs (and huge poll-tax registers of 100–220 ages each) if more
is ever wanted.

#### Hard-batch extension + a silent-corruption fix (2026-07-22 session)

The owner curated a **hard batch** (`data/gold/hard_data_batch.jsonl`, 24 docs)
to feed the starved rare classes and hand-annotated the first 10 into gold; a
`batch_2.jsonl` holds the leftover 15 (14 hard + `702571`). This session:

1. **Verified the owner's 10 hard docs and fixed 3 load-bearing bugs.** Three of
   them (`7797`, `40966`, `41308`) had gold `text` that was **not byte-identical
   to `corpus.parquet`** — the hard-batch file itself carried a silently
   *normalized* text (`γίνεται`→`γίνονται`, final-sigma→medial-sigma). Because
   the numeral-coverage gate keys on an exact `text` match, a non-matching text
   **silently disabled the gate for those docs** (`numerals=None`), so their
   coverage was never actually checked. Fixed by rebasing each onto canonical
   corpus text and remapping all 135 entity/skip offsets through a `difflib`
   alignment (every remapped span's corpus substring re-verified against its
   recorded text). Also removed **3 phantom `skipped_numerals`** (`ω`, `μα`,
   `πρώτῃ`) that pointed at tokens the corpus never tagged `<num>`. Result: every
   gold doc byte-identical, gate live on every doc, **0 errors**.
2. **Annotated 13 more hard docs from scratch** (`77576 78637 77107 75749 79378
   702571 793 5344 7560 5414 703351 76201 43027`) via surface-string forward-scan
   (offsets computed, never hand-written — same method as
   `tools/build_gold_draft.py`, text pulled from `corpus.parquet`, **not** the
   corrupted batch files). +352 entities / +81 relations. The pre-existing
   `entities` in `hard_data_batch.jsonl` are low-quality auto-suggestions
   (broken relation indices, many uncovered numerals) — **do not trust them**;
   re-annotate.
3. **Rare-class yield** (HEAD 85 → now 108): **TAX_TERM 23→66 (+43)**,
   **FRACTION 61→96 (+35)**, **PERSON_ROLE 21→38 (+17)**, **OCCUPATION
   122→182 (+60)**, AGE 6→9 (+3, all from the owner's `7797`). The 13
   model_drafts are TAX_TERM- and FRACTION-heavy (poll/sales/rent-tax receipts,
   aroura fractions ιϛ=1/16 λβ=1/32, Byzantine occupation lists) plus `43027`'s
   two guardian-formula `PERSON_ROLE`s and a freedwoman (`ἀπελευθέρᾳ`).

#### Phase 5c — Payment Direction (PAID_BY / PAID_TO)

**Gold direction — VALIDATED + MERGED into the gold (2026-07-23).**
- Re-derived over all 89 gold docs carrying MONEY_AMOUNT or COMMODITY.
- **38 docs, 87 `PAID_BY`/`PAID_TO` edges** merged into `data/gold/annotated.jsonl`.
- `oik gold check` 0 errors, relations 623 → 710.
