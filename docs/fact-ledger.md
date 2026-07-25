# OIKONOMIA — Verified Fact Ledger

> Load-bearing facts checked against live sources during planning/implementation.
> **Do not re-derive.** If reality contradicts one, treat it as a finding and update it here.
> This is the reference companion to `CLAUDE.md` (which keeps only the most-consulted subset inline).

### Corpus (github.com/papyri/idp.data)
- **Pinned revision: `d7a34f302d1e44e271256092c2b780733187b478`** (HEAD on
  2026-07-20). Set in `configs/base.yaml`. Repin deliberately, never incidentally.
- Licence **CC BY 3.0** (in every file; no repo `LICENSE`). README is stale
  (documents `DDB_EpiDoc_XML`/`HGV_trans_EpiDoc`; real dirs are `DDbDP` /
  `Translations`).
- `DDbDP` 67,980 files · `HGV_meta_EpiDoc` 66,872 · `Translations` 8,001.
- **Translations are multilingual, and smaller than recorded** (corrected in
  Phase 2 against all 8,001 files; the old "6,474 unique DDbDP docs = 9.8%,
  English" was wrong). Actual: 7,116 `en` · 576 `de` · 190 `fr` · 89 `it` ·
  small tails (`es`, `ar`, `el`, `pl`, `bg`) · 14 with no translation div.
  English covers **6,156 unique docs, of which 5,989 join a DDbDP document =
  8.81%**. Document-level only. Note stray malformed lang codes (`ge`, `fe`).
- **Path conventions (asymmetric — verified empirically):**
  - DDbDP `DDbDP/{id//1000}/{stem}.xml`
  - HGV `HGV_meta_EpiDoc/HGV{id//1000+1}/{stem}.xml`  ← **+1 and "HGV" prefix**
  - Translations `Translations/{id//1000}/{id}-{seq}.xml`
  - Letter-suffixed stems exist (`13a`); bucket by numeric part.
- DDbDP↔HGV join **98.27%** by TM id (whole corpus; the 98.3% sample estimate
  held).
- **Duplicate `xml:id` is endemic and must not be fatal.** 512 of 67,980 DDbDP
  files (0.75%) carry repeated ids (`_ctr`, `column_i`, `_FrA`, `_1`…) from
  editors merging fragments. lxml collects ids and enforces uniqueness by
  default, which rejected all 512. Parse with `collect_ids=False`
  (`ingest/xml_parser.py`, the single parser factory) — nothing resolves
  IDREFs, so the id table is unused. **With this, parse rate is 1.000.**
- HGV dates at `msDesc/history/origin/origDate` (`when=` or `notBefore/notAfter`,
  ISO, BCE = leading `-`). Whole-corpus: **98.63%** machine-readable, **23.68%**
  exact-day, **17.18%** span >120y, **3.71%** alternative datings
  (`xml:id="dateAlternativeN"` — the 2.5% sample estimate was low).
- HGV linkable places in `<provenance type="located">//placeName/@ref`
  (space-separated TM+Pleiades URIs), **77.59%** (Pleiades specifically 75.0%).
  `<origPlace>` is free German text — **never used for joins**.
- **DDbDP markup, whole corpus** (`oik corpus stats`; supersedes the 200-doc
  sample estimates, which ran high on `gap`/`supplied`/`unclear`):
  numerals 64.82% · `<expan>` 68.81% · `<unclear>` 68.18% · `<gap>` 66.16% ·
  `<supplied>` 62.39% · `<choice><reg>` 44.53% · `<abbr>` 15.58% ·
  `<surplus>` 3.45% · `<choice><corr>` 0.20%.
  Numerals are **not** a `MarkupKind` — they live in their own table. Derive
  any kind list from the `MarkupKind` enum, never by hand: a wrong name reports
  0.0, which is indistinguishable from "absent from the corpus".
- Corpus text mass: 37.4M edited chars, 934,923 lines, 568,449 numerals,
  median 233 chars/doc.
- **`n_chars_edited` counts whitespace, so it is not "how much text there is".**
  6,731 docs (**9.90%**, flagged `empty_edited_text`) hold only the newline
  scaffolding left by `<lb>` elements — `n_chars_edited` 4–77, but
  `.strip()` is empty. Filter on `parse_flags` or `.strip()`, never on
  `n_chars_edited > 0`, which is true for every document in the corpus.
- **Usable subset for supervision: 61,249 docs with real text, of which 44,064
  also carry at least one numeral.** These are the denominators Phase 3 should
  sample and split against — not 67,980.
- **Zero entity markup** (`persName`/`placeName`/`measure`/`rs`/`w` = 0% of 200).
  All entity supervision must be built. This makes Phase 5 gold the critical path
  and Phase 8 relations the scientific risk.
- Economic docs are numeral-dense (whole corpus, numerals/line): account 1.34 ·
  list 1.14 · receipt 0.67 · lease 0.65 · loan 0.32 · sale 0.25 · contract 0.21
  · petition 0.15 · **letter_private 0.09**. The genre signal is real and large.
- **Word order: units PRECEDE their numeral.** Measured over every `<num>`
  neighbour: `δραχμαι` sits left of the numeral in 81.5% of occurrences,
  `αρταβαι` in 80.4%. Greek accounts read *commodity, unit, number*
  (`πυροῦ ἀρτάβαι ιβ`). Any proximity rule must break ties leftward.
- **Many alphabetic numerals are never tagged `<num>`.** `ιβ`, `ιϛ`, `κδ`, `λβ`
  and friends are among the most frequent tokens adjacent to tagged numerals —
  i.e. editors tagged one and left the next bare. Do not treat `<num>` as a
  complete inventory of numbers; annotation guidelines say to read the number,
  not the tag.
- **`<lb break="no"/>` means the line break falls INSIDE a word — no separator
  belongs there.** The scribe ran out of room and continued on the next line.
  **23,982 of 67,980 documents (35.28%)** contain at least one; **96,323**
  occurrences corpus-wide. The parser emitted a separator at every `<lb>`
  regardless, so ναύκληρος came out as "ναύκλη ρος" — text no lexicon matches
  and no tokenizer handles well.
  **Two whitespace sources, and fixing only the first does nothing visible:**
  (a) the newline the parser itself emits, and (b) the XML file's own
  pretty-print indentation (`'\n\n    '`), which lands in the *preceding*
  element's tail and is what actually produced the visible space. Measured
  distribution of where (b) lives: `prev.tail` 82%, `parent.text` 9%, *inside*
  the previous element (e.g. `<supplied>ά\n  </supplied>`) 2%. On the far side,
  only `lb.tail` ever carries leading whitespace (0 of 705 cases where the tail
  is empty and an element follows). Handled by `_join_broken_words`, a pre-pass
  over the tree, so all offset accounting downstream sees correct text.
- **Near-duplication: 2.89%** (1,769 of 61,249 texted docs in 475 clusters,
  MinHash Jaccard >=0.8 over folded 5-grams). Enough to inflate a naive random
  split; not enough to distort corpus statistics. **This number moved from
  2.54% when the `break="no"` fix landed** — differently-broken words made two
  copies of the same text look different. A text-quality bug upstream is a
  leakage bug downstream.
- **Whitespace is canonical in `corpus.parquet`, and the parser is the only
  thing that decides it** (since `build_corpus` v4). Within a line, single
  spaces; one `\n` per real line break; nothing at a `break="no"` break; no
  leading or trailing padding. **Do not re-collapse it in a consumer** — that
  shifts every offset and silently decouples your spans from the stored text,
  which is exactly the bug v4 fixed. Verified over 1,500 random documents:
  0 occurrences of `'  '`, `' \n'`, `'\n '`, `'\n\n'`, or edge padding.
- **Gold `text` must be byte-identical to `corpus.parquet.edited_text`, and the
  numeral gate SILENTLY skips any doc where it is not.** `oik gold check` keys
  the `<num>` tags by exact `text` match (`_load_gold_numerals`); a mismatched
  text returns `numerals=None`, so `check_numeral_coverage` never runs for that
  doc and its coverage goes unchecked — no error, no warning. Found 2026-07-22:
  3 of the owner's hard docs (`7797`, `40966`, `41308`) carried a *normalized*
  text from `hard_data_batch.jsonl` (`γίνεται`→`γίνονται`, final `ς`→medial `σ`)
  that differed from corpus by 1–4 chars, so their gates had been silently off.
  **Any hand-curated batch file's `text` is suspect** — always source gold text
  from `corpus.parquet`, never from a batch/suggestion file, and cross-check
  byte-identity (a two-line diff) whenever gold rows are added by hand.
- **`<space>` is a *vacat*** — blank space deliberately left on the papyrus —
  and emits a space of its own. The source also puts literal spaces around it,
  so all three used to collide (`'Ποκῶτος   δραχμὰς'`). It is not a
  `MarkupKind`, so it produces no markup span.
- **Canonicalising text after spans exist requires remapping the spans**, and
  aligned segments must be *split*, not merely shifted: a character can survive
  in the edited view but not the diplomatic one (or vice versa), since each
  view's whitespace runs differ. Corpus-scale check: for every segment,
  `edited[e0:e1] == diplomatic[d0:d1]` — 0 mismatches over 1,500 documents.
- **618 documents share a TM id with another** in the 61,249-document working set
  (231 groups) — the same papyrus edited or republished separately. A real leakage
  group, and cheap to detect. Over all 67,980 rows it is 2,313 documents in 607
  groups; the extra rows are the empty letter-suffixed stems below.
  **This entry read "1,706 documents" until 2026-07-25 — that number matched
  nothing recomputable** (`splits.parquet`: `tm_id.value_counts()` gives 618/231)
  and it had already propagated into the CHR paper. Recompute, don't quote it.
- **`stem` is the unique per-row key; `tm_id` is NOT** (verified 2026-07-24 on
  `corpus.parquet`: 67,980 distinct stems for 67,980 rows, zero collisions; but
  **607 tm_ids span >1 row and 231 span >1 *non-empty* row**). Letter-suffixed
  stems (`13`, `13a`, `13b`) share one tm_id, and the suffix rows are often empty.
  So **any join that slices a document's text back from a span must key on `stem`,
  not `tm_id`** — keying on tm_id silently matches the wrong (often empty) row for
  those 231 docs. The corpus-NER predictions (`ner_corpus.jsonl`) carry `stem`
  for exactly this reason; the Phase-9 DB is unaffected because it assembles each
  fact inline and never re-joins text by tm_id.
- Publication volume is far too coarse to group on: 1,025 volumes, largest
  holding 2,023 documents.
- **Lexicon size is 132 entries / 545 unique surface forms over 8 categories**
  (OCCUPATION 52 · COMMODITY 20 · DATE_REF 16 · UNIT 16 · CURRENCY 13 · TAX_TERM
  10 · FRACTION 4 · PRICE_TERM 1), **545/545 attested, 0 unattested**
  (`oik lexicon verify`, 2026-07-25). Phase 2's "88 entries / 336 forms" is that
  phase's snapshot and has been superseded — it grew with 8b's occupations. Quote
  the verifier, not the phase doc.
- Lexicon false friends share stems across categories: `χαλκεύς` (coppersmith)
  vs currency `χαλκοῦς`; `σιτολόγος` (grain officer) vs commodity `σῖτος`;
  `ἐλαιουργός` (oil-worker) vs `ἔλαιον`. These are OCCUPATION. Stem matching
  alone will mislabel them.

### Silver labeling (Phase 6, measured against the 65-doc gold draft)
- **PERSON is capitalisation.** 99.8% of gold PERSON spans are capital-initial;
  of all capitalised tokens, 71.6% are PERSON, 13.3% PLACE, ~6% titulature-in-
  dates, ~6% months — so capitalisation minus those exclusions is a strong
  PERSON detector. TRANSACTION and PERSON_ROLE are the opposite: **0/41 and
  0/20 gold instances are capitalised**, so those stems must be lowercase-gated.
- **The silver labeler's noise is ~99% systematic, not diffuse.** Corpus
  self-consistency (same form, same label across docs) is **0.992** before any
  denoising. Consequence, verified the hard way: a corpus-majority vote is
  *harmful* — 96% of its label changes flipped PLACE→PERSON, amplifying the
  systematic bias. **Aggregation cannot fix systematic noise; only independent
  signals or abstention can.**
- **Corpus-agreement confidence predicts correctness.** For surface-decided
  labels, confidence = the form's corpus-wide share of that label. Precision by
  bucket: ≥0.9 → 0.90, **0.7–0.9 → 0.33** (the danger zone), unseen novel form
  → 0.91. A `--min-confidence 0.5` filter drops the measured-noisy labels
  (DATE_REF 0.35, QUANTITY 0.46, TAX_TERM 0.26 and the PARTY_OF/DATED_TO tail).
- **The 65-doc gold cannot measure corpus-scale changes.** Both the place
  gazetteer and the consensus denoiser scored ~0.000 on it — their effects are
  on forms/docs outside the sample. Validating corpus-scale denoising (or a
  label-model combiner) requires a larger / human-reviewed gold. All Phase-6
  numbers are agreement-with-`model_draft`, not ground truth.
- **Seed-stem greediness is a real precision bug.** `αλεξανδρ` matched both
  Ἀλεξάνδρεια (place) and the person Ἀλέξανδρος; tightening to `αλεξανδρε`
  fixed it (PLACE precision 0.69→0.74). Month names (Θῶυτ, Ὑπερβερεταίου)
  missing from the date lexicon leak to PERSON unless stem-excluded.

### EpiDoc rendering (confirmed vs EpiDoc Guidelines)
- `<choice>`: edited uses `<reg>`/`<corr>`; diplomatic uses `<orig>`/`<sic>`.
- `<expan>`: `<ex>` (expansion) is edited-only; abbr letters are in both.
- `<supplied>` (lost/omitted): edited-only. `<surplus>`: diplomatic-only.
- `<app>`: render `<lem>` (chosen reading); ignore `<rdg>`.
- papyri.info blocks bots (Anubis) — rendered-text cross-checks are done with
  hand-crafted fixtures, not by scraping.

### Backbones (re-verified 2026-07-20, directly against HF model files)

**The bowphs family** (Heidelberg NLP, "Exploring LLMs for Classical Philology"):
- `bowphs/GreBerta` — **encoder-only RoBERTa-base, apache-2.0**, 12 layers,
  768d, 52k vocab, `max_position_embeddings` **514**. Reports UAS 88.20 /
  LAS 83.98 on UD 2.10.
- `bowphs/GreTa` — T5-base encoder-decoder, 0.2B, apache-2.0. Trained on
  Internet Archive OCR + Open Greek & Latin + CLARIN Medieval + Patrologia.
- `PhilBerta` / `PhilTa` are the multilingual (Greek+Latin+English) variants.

**Own models** (`ainouche-abderahmane/*`, all LoRA adapters over GreTa):
- `koineformer` r=16 α=32, 3.7M trainable / 220M, 14 MB, **CC-BY-SA-4.0**
  (the SA is inherited from MorphGNT, not chosen).
- `koine-t5`, `koine-t5-omni` — **CC-BY-NC-SA-4.0**. GreTa is apache-2.0, so
  the NC is *not* inherited from the backbone. Audit where it came from before
  assuming the firewall is immovable.
- All three are adapted on ~1.5M tokens of SBLGNT + Apostolic Fathers, i.e.
  **biblical literary Koine — a different register from documentary papyri.**

**Case handling differs by model — and an earlier version of this ledger got
it wrong.** It claimed case was destroyed family-wide, inferred from reading
vocabulary files. Tokenising actual text shows otherwise:

| | `Ἡλιοδώρου` vs `ἡλιοδώρου` | round-trip |
|---|---|---|
| **GreTa** | identical ids `[11655, 17067]` | lowercased — **case lost** |
| **GreBerta** | `[2213, 513, 50508]` vs `[1342, 513, 50508]` | `Ἡλιοδώρου` — **case kept** |

GreTa's tokenizer normalizer contains `{"type": "Lowercase"}`, so case is gone
before the model sees it. **GreBerta has no such normalizer and preserves case
fine** — ByteLevel BPE composes capitals from byte pieces, and an absent
uppercase *merge* is not an absent uppercase *representation*. `Γεώργιος` and
`γεωργός` tokenise to entirely different ids.

**Keeping case costs −0.59% tokens** over the corpus, i.e. it is *cheaper* as
well as more informative. 16.16% of corpus tokens are capitalised and in papyri
capitals mark proper names, so lowercasing throws away the strongest available
PERSON/PLACE cue for nothing. `pranaydeeps/Ancient-Greek-BERT` does state
"de-accentuating and lower-casing" outright (and declares no licence — unusable
for a released artifact), but that is a property of that model, not of the
field.

**Consequence:** the planned B2 arm ("does an explicit capitalisation feature
help?") is largely moot for GreBerta — the backbone already sees case. Reuse
that slot for something that is actually in question.

**Architecture evidence for the task (token classification, not generation):**
- Encoder-only beats encoder-decoder on NER by a wide margin: 84.7 vs 68.1 F1
  in-domain, 76.6 vs 58.9 out-of-domain (~15–17.7 points). Cause is
  architectural — MLM pretraining aligns with sequence labelling, and
  autoregressive decoding accumulates errors across tokens.
- The bowphs paper itself credits T5's decoder specifically for
  **lemmatization** — a generative task, which ours is not.

### DAPT method (verified)
- Gururangan et al., "Don't Stop Pretraining": DAPT gains **2–12 points**,
  largest when the target domain is *furthest* from the pretraining domain.
  Documentary papyri vs literary Classical/Medieval Greek is a large distance,
  so expect the upper half of that range. ~12,500 steps was their setting.
- **TAPT (task-adaptive pretraining) helps on top of DAPT** — cheap, do both.
- **Full fine-tuning, not LoRA, for DAPT.** "LoRA learns less and forgets
  less": LoRA's value is preserving source-domain ability, which is exactly
  what we do *not* need — literary Greek performance is not a deliverable.
  GreBerta is 0.1B, so full FT fits an A10 (24 GB) comfortably.
- Weak/silver supervision (Phase 6) carries **20–60% label noise** in the
  literature. Budget for noise-robust loss + filtering, not naive training.
- Joint span-based entity+relation extraction outperforms pipelines when well
  designed (pipelines suffer error propagation) — but a badly designed joint
  model underperforms a pipeline.

### Ablation plan (restructured 2026-07-20 on the evidence above)

| Arm | Backbone | DAPT | Licence | Role |
|---|---|---|---|---|
| **B0** | GreBerta | none | apache-2.0 | **Control.** Isolates what DAPT buys. |
| **B1** | GreBerta | papyri | apache-2.0 | **Primary. The released model.** |
| **B2** | GreBerta | papyri, seq_len 256 | apache-2.0 | Median papyrus is ~74 tokens; a 512-block packs ~7 unrelated documents. |
| **A1** | GreTa | papyri | apache-2.0 | Architecture control: encoder vs encoder-decoder. |
| **A3** | koine-t5-omni | — | **CC-BY-NC-SA** | Comparison only. **Never released.** |

B0 is a real arm, not a formality: if DAPT does not clear it, that is the
finding and there is no reason to ship a DAPT'd model. B1 vs A1 tests the
architecture claim on our own data rather than on the literature's.

### Context length (measured against this corpus)
- GreBerta's 512 tokens covers **~93%** of documents whole (median 267 chars,
  p90 1,228, p95 1,830; ~6.8% exceed ~512 tokens, 2.0% exceed ~1024).
  Sliding window with overlap handles the tail.
- koine-t5/omni's 256-token limit would truncate ~25% — another reason not to
  build on them.

### Modal API (verified at modal.com/docs — re-check before Phase 4)
- `modal.App` (`modal.Stub` is an error in ≥1.0). GPU string **`gpu="A10"`**,
  24 GB, `"A10:2"` for multi. **`"A10G"` is no longer in the documented GPU
  list** (T4, L4, A10, L40S, A100, H100, H200, B200, B300, RTX-PRO-6000) —
  use `"A10"`. `gpu=["H100", "A100-40GB:2"]` expresses ordered fallbacks.
- `modal.gpu.*` objects, `modal.Mount`/`mount=`, automounting of local modules:
  **all deprecated/removed** — add local source explicitly
  (`add_local_python_source`, `add_local_dir`).
- Volumes `from_name(create_if_missing=True)`, `volumes={...}`, `.commit()`;
  **background commits every few seconds plus a final snapshot on shutdown**
  are confirmed current. Pass `version=2` for v2 Volumes. Set the HF Trainer's
  `output_dir` inside the Volume and checkpointing is automatic.
- `@app.function(gpu=, volumes=, secrets=, timeout=, retries=, max_containers=,
  single_use_containers=)`; timeout max 86400; `concurrency_limit`→`max_containers`.
- Preemption-resilient pattern: Volume checkpoints + `retries=` +
  `single_use_containers=True` + resume-from-last-checkpoint.

