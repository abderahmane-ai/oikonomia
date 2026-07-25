# Phase 12 — Publication (CHR 2027)

**Status: SUBMITTED AND COMPLETE (EasyChair #7).** Corrected abstract stored,
final PDF uploaded, artifact deposited at `10.5281/zenodo.21576045`. Final state:
16/16 checks, **5,984 of 6,000 words, 15 pp, 5 figures**, anonymity clean on four
surfaces. Nothing outstanding.

PDF replacement stays open until **14 Aug 2026, 23:59:59 UTC-12 (AoE)** if a real
defect turns up. **Notification: 23 Oct 2026.**

> **A trap that cost a round trip: EasyChair displays timestamps in UTC while the
> machine is UTC+1.** An already-current upload looked 53 minutes stale until the
> version history was lined up against local `git log` times. Add an hour before
> concluding anything from an EasyChair timestamp.
>
> **And the stored abstract is a separate metadata field.** Replacing the PDF does
> not touch it. The submitted abstract carried the round-1 "eighteen named taxes"
> error for hours after the PDF was fixed, because nobody thought to check a field
> that no upload updates. If the paper's abstract changes, change it in both
> places.

> **The paper itself lives in `paper/chr2027/`, which is GITIGNORED.** The prose
> exists only on the owner's machine. This file is the part of it that survives a
> fresh clone: the decisions, the audit history, and what is still open. The
> figures regenerate from `data/processed/db/` via `figures/make_figures.py`; the
> ACH template re-fetches from `anthology.ach.org`; the prose does not regenerate.

---

## 1. Venue: chosen after a live scan, not from memory (2026-07-25)

What was actually open, checked against each venue's own site:

| Venue | Verdict |
|---|---|
| LT4HALA 2026 | happened May 2026 @ LREC — missed; next likely 2028 |
| NLP4DH 2026 | happened Jul 2026 @ ACL — missed |
| ML4AL | ran once, ACL 2024 — dormant |
| EMNLP 2026 main | closed; none of its 27 workshops fit |
| ARR Aug → EACL 2027 | 3 Aug — too tight |
| ARR Oct → ACL 2027 | 12 Oct — the *model* paper's slot |
| **CHR 2027** | **winner** — Manchester, 6–8 Jan 2027, subs 14 Aug 2026 AoE |

CHR's stated priorities (ML applications + hypothesis-driven modelling in the
humanities) are exactly phases 9–10. Long paper: **6,000 words excluding
abstract, references and tables/illustrations**; no page limit. EasyChair, ACH
LaTeX template.

**Plan of record: two papers, two audiences.** CHR 2027 is the *findings* paper.
The *resource/model* paper (Grammateus + Homologia + the weak→reference recipe +
the DAPT ablation) goes to the **ARR October** cycle → ACL 2027. Do not rush it
into an August ARR deadline. The declared per-label / per-fold gaps
(`ner.py::xval`) are a prerequisite for the ACL paper only — CHR needs no GPU run.

## 2. What the paper claims

Title: *How Often, and How Freely: Women in Greco-Roman Egypt, and an Auditable
Economic Database of 61,249 Documentary Papyri.* The hook names the two novel
findings (F3 "how freely", F4 "how often"). **F1/F2 are deliberately not in the
title** — they are validation, not contributions. F5 (prices) is reported as a
negative result.

Five contributions: the auditable database; an evaluation protocol for extraction
without ground truth (require the table to recover known history unsupervised
before it may state a novel count); the two counts; the design argument (closed vs
open lexical classes need different machinery and their error bars must never be
blended); and the released artifacts.

## 3. Submission record

- **EasyChair submission #7**, 2026-07-25. Author: Abderahmane Ainouche, ENSIA,
  Algeria (corresponding, early-career = yes). Long paper.
- Topics ticked: text analysis · LLMs · knowledge representation · infrastructure
  and tools · open science · history · linguistics · social sciences.
- **`statistics` and `spatial analysis` deliberately NOT ticked** — they drive
  reviewer assignment, and the paper reports medians/IQRs/tiers rather than CIs,
  and explicitly declines the regional cut.
- **Presentation format: "short oral presentation" — correct, and not a
  mis-click.** EasyChair forces a binary (poster vs oral) on every submission
  type, but the CFP gives the choice only to *short* papers and says "the final
  decision on the format will be taken by the program committee". **Long papers
  are presented orally as full presentations**, so the field binds nothing here.
  Do not re-flag it.
- **Anonymity period runs to 23 Oct 2026** (notification). Do not promote the
  paper publicly before then. Preprinting is permitted (CHR names arXiv/Zenodo/
  HAL) — **use Zenodo, not ResearchGate**, and preferably only once the
  expert-validation question is settled. arXiv needs an endorser since its
  2026-01-21 policy change; an ENSIA supervisor with cs.CL papers could endorse.
- **Add the gmail as a secondary EasyChair email.** The submission used
  `@ensia.edu.dz` and the author is a 5th-year student; notification is 23 Oct
  2026 and the conference is Jan 2027, so a lapsing student address is a real way
  to miss an acceptance.

## 4. Audit history — five rounds after submission

Each round found real defects. Recorded so they are not re-found or re-argued.

### Round 1 — full reread (2026-07-25)

A 5th contribution bullet was added claiming the released artifacts; they had been
missing from the contributions list entirely while "open science" was a submitted
topic. Then seven more defects, three serious:

- the threats section referred to findings as "F1/F2/F3/F4", labels the paper
  never defines and which collide with the F-measure used 10+ times;
- it claimed the validation findings "do not depend on the reference set being
  right" when the labeler's rules were in fact calibrated against it — now stated
  as a tuned threshold, not a learned representation;
- abstract + conclusion said "eighteen named taxes sort themselves" when 18 were
  *extracted* and only **six** carry the periodization.

Plus a stray "silver" left from the terminology rename, "four quantitative
results" above a five-item list, two tax denominators (6,441 dated vs 6,623 total)
used without saying so, and an unhedged "first … models" priority claim.

### Round 2 — numbers audit (2026-07-25, commit `152e9ab`)

Every quantitative claim recomputed **from the artifacts**, not from the phase
docs. Two stale numbers had reached the paper:

- **`1,706 documents share a TM id`** — nothing produces that. `splits.parquet`
  gives **618 in 231 groups** over the working set (2,313 in 607 groups over all
  67,980 rows). The fact-ledger already carried the correct count in a later
  entry, so it contradicted itself; the paper picked up the older line. Fixed at
  the source: ledger, `splits/assign.py`, `gold/sample.py`, `tests/test_splits.py`.
- **lexicon `88 entries / 336 forms`** — the phase-2 snapshot. `oik lexicon
  verify` says **132 entries / 545 unique forms**, 545 attested, 0 unattested.

Also: a duplicated "and" in the introduction, and §5.1 describing the plotted
denominator as "system-attributed" when it includes the 1,095 unknown-system rows.

**A review claiming the paper's Spearman ρ 0.861 should be 0.856 was WRONG.**
0.861 is over the 15 deal-type buckets the figure plots; 0.856 includes the
unclassified (`?`) bucket. Both are correct on their own basis and the figure
states which it uses. **Do not "fix" it.** Same for the 3.8× → 3.1× ratio: that is
the unweighted mean of the four bucket shares; pooled it is 2.9× → 2.6×.

### Round 3 — reread of the worked examples (2026-07-25)

Grep cannot catch these; they were found by reading the figure against the tables.
**Figure 1 is the paper's auditability demo, so a mismatch there is expensive.**

- **(a) "yields one row."** TM 76409 yields **seven** rows, one per amount. The
  offsets shown are correct — 108–118 `λαογραφίας`, 127–134 `δραχμὰς`, 135–136
  `δ`, value 4.0 drachma silver, `tax_id` laographia, AD 126 — but the document
  does not produce a single row. Now says seven, one per amount, with the row
  shown being one of them.
- **(b) head/patronymic were idealised, not what the pipeline produces.** The
  figure said head `Ἀλέκα`, patronymic `Ἀπολλωνίου`. `persons.parquet` says
  **head `Αὐρηλία`, filiation `Ἀλέκα`**: `parse_person_name` takes the first real
  token as head, so a Roman *nomen* occupies the head slot and pushes the personal
  name into the filiation slot. **3.8% of the 350,206 person rows** are like this.
- **(b) `basis` was wrong.** The figure said `basis=nomen`; the row for that span
  says **`basis=guardian`** (a second, shorter mention of the same woman is
  `basis=nomen`, which is probably where the figure's value came from).
- **Consequence for §7's coreference hook.** 64.8% of women principals carry a
  recovered filiation name — that number is right — but **34.8% of those (370 of
  1,063) have a nomen in the head slot**, so their "patronymic" is the personal
  name, not a father. Still a usable matching key; not filiation. The paper now
  says so.

### Round 4 — the annotation rules the findings rest on (2026-07-25)

**What the CFP actually says** (checked live at
`2027.computational-humanities-research.org/cfp/`, do not re-derive):

- Appendices **are allowed** ("to improve reproducibility … pre-processing
  decisions, model parameters, prompts, pseudocode"), but **only references,
  abstract and tables/illustrations are excluded from the 6,000 words** —
  appendices are not, so an appendix costs the same as body text.
- *"Reviewers are not required to read the appendices and supplementary materials
  during review. The main text of each paper must be stand-alone."*
- **No artifact upload slot is documented.** Submission is "PDF documents via
  EasyChair". The CFP's own mechanism for artifacts is an **anonymised link**,
  and it names the two services: `anonymous.4open.science` and
  `zenodo.org/record/xxxxx`.

So anything a reviewer must believe goes in the body, paid for by cuts. Three
additions, all lifted from `resources/schema/annotation_guidelines.md` §5:

1. **The guardian rule** (§6.1) — the modality lives *inside* the span,
   `χωρὶς κυρίου` and never bare `κυρίου`, because dropping the negation makes
   the two cases indistinguishable and the question unanswerable. **The autonomy
   finding rests entirely on this decision and the paper had never stated it.**
2. **A definition of "principal"** (§6.2) — the head of a party or payment edge.
   The schema annotates *every party, named or not*, so an unnamed
   `καὶ τῆς γυναικὸς` enters through its role phrase.
3. **The concession that goes with it** — the guidelines contain **no rule
   excluding witnesses or scribes** from `PARTY_OF`, and the data cannot settle
   it: the `roles` column is structural (party 13,738 · payee 3,605 · payer
   3,176), with no witness marker to filter on. The paper now says it counts
   parties as the schema defines them, not principals in the legal sense.

Paid for by trimming the DoRA paragraph and the parser paragraph — both are
material for the ACL model paper rather than this one. **5,954/6,000 words.**

**The reviewer bundle's README was wrong and is fixed.** It called the reference
set "the 115 **human-validated** gold documents" — the false claim retracted
everywhere else on 2026-07-25, and one that flatly contradicts the paper it
accompanies — and quoted the lexicon as 88 entries / 336 forms. Both corrected in
`paper/chr2027/make_anon_bundle.py` (the generator, so it cannot regress) and the
archive regenerated. The gold JSONL itself was already correct
(`provenance: model_drafted_model_checked`), as was the bundled `database.md`;
only the generated README was stale. **Audit the bundle's own prose, not just its
filenames** — `check_submission.py` verifies anonymity and file inventory, not
whether the README tells the truth.

### Round 5 — the coverage objection, measured (2026-07-25)

Adding a plot turned into a finding, so it is recorded here rather than in a
caption. Figures cost **no words** at CHR (tables/illustrations are excluded), so
the only price is page space — verified empirically: caption edits do not move
`wordcount.py`.

**The question:** only 42% of principals get a gender verdict. If that coverage
varies by deal type, the F4 gradient could be a map of where the gender cascade
fires rather than a fact about women. The paper's old defence was a two-point
spot check (sale 0.461 vs receipt 0.417 attribution).

**What the data says — the spot check was too kind.** Over the 15 deal-type
buckets with n ≥ 40, attribution rate and women's share **do** correlate:
**Spearman ρ = 0.589**. It is not the female-only guardian channel doing it —
removing that channel only drops it to **0.500**.

**But the gradient is not explained by coverage.** Restricted to the seven
buckets whose attribution rate lies between 0.373 and 0.476 — a 10-point window
— women's share still spans **3.0×** (receipt 0.102 → sale 0.304) and the
within-band correlation collapses to **ρ = 0.143**. Coverage moves ten points
there; the outcome moves threefold.

The paper now states the correlation instead of the flattering pair, and
`figures/coverage.pdf` (`fig_coverage` in `make_figures.py`, regenerated from
`principals.parquet` like the other four) plots all fifteen buckets with the
matched-coverage band shaded. **Do not replace this with the old sale-vs-receipt
sentence** — a reviewer who computes ρ over all buckets gets 0.59 and would
rightly feel handled.

Figures considered and rejected: a corpus-coverage-by-century bar chart (the
fiscal heatmap already prints per-century counts), a price series for F5
(plotting a deliberate negative result gives it weight the text denies it), and
any model-performance plot (ACL model-paper material). A "crossing curves"
figure — women's share of principals falling while autonomy rises — is viable
and the data is verified, but the two series have different denominators and
would need twin axes plus an explicit caption warning; left unbuilt.

## 5. Annotation reliability — the position the paper takes

There is one annotator, so there is **no IAA**. What §4.1 reports instead is what
the *verification pass changed*, measured from two git revisions with no schema
commit between them (`review_delta.py`): the reviewer **added 68 spans, removed 3,
relabelled none** against 1,127 drafted (span-level F1 0.969). The paper states
both readings and says the unflattering one is the one to hold us to — the drafts
may have been accurate on labels, or labels may not have been scrutinised as hard
as boundaries. Threats names the concrete fix: **16 gold docs already carry
`double_annotate: true`**, genre-stratified over 504 entities, and that is the
subset a second annotator should be given.

**The one thing tooling cannot do: get a papyrologist to read the autonomy
finding before it goes out.** That remains open and is the project's top item.

## 6. The artifact bundle — DEPOSITED

**DOI: `10.5281/zenodo.21576045`** → https://doi.org/10.5281/zenodo.21576045
Published 2026-07-26. **Verified live against the Zenodo API, not assumed:**
title "Anonymised artifact bundle for a CHR 2027 submission", resource type
Dataset, licence `cc-by-3.0`, creators `['Anonymous']`, one file
`anon-artifact.zip` at **145,404 bytes — byte-for-byte the local archive**, and
**zero hits** for the author, institution, project, model or repo names anywhere
in the public metadata. The paper's availability section cites this DOI; the old
"available through the programme chairs" wording is gone, since the CFP
describes no such relay.

**Why Zenodo and not an EasyChair attachment:** the submission form for CHR 2027
offers only *Update information · Update topics · Update authors · Update file ·
Withdraw*. "Update file" is the paper PDF; there is **no attachment slot**. The
CFP's own mechanism for artifacts is an anonymised link, and it names Zenodo.

**Licence pick, for the record:** Zenodo's picker offers CC BY 3.0 in three
flavours — Austria, United States and **Unported**. Unported (SPDX `CC-BY-3.0`)
is the jurisdiction-neutral one and the one `creativecommons.org/licenses/by/3.0/`
resolves to, which is what `DATA_ATTRIBUTION.md` cites for the DDbDP source data.
The ported national versions would misstate the source terms.

**After acceptance:** hit Edit on the record and swap `Anonymous` for the real
name and affiliation. Metadata edits need no new version and do not change the
DOI, so the citation in the published paper keeps resolving. Also note Zenodo
allows the owner to **delete a published record within 30 days**; after that only
in justified cases.

## 7. How the delivery decision was made (superseded by §6, kept for the reasoning)

`paper/chr2027/anon-artifact.zip`, 17 files, **0.1 MB zipped**. Verified
name-neutral: 0 hits for the author, institution, project, model, dataset, repo
and Hub strings across every file *and* every path.

1. **Look at the EasyChair page for submission #7 first.** Chairs can enable an
   optional attachment field; the CFP does not document one, but the form is the
   authority. If there is an upload box, use it — no anonymity risk, nothing to
   host, no link to maintain.
2. **If there is no upload box, deposit on Zenodo** — one of the two services the
   CFP names. Creators field: **`Anonymous`** (Zenodo shows the creators you type,
   not the account holder). Title something neutral, e.g. *"Anonymised artifact
   for a CHR 2027 submission"*. Licence **CC BY 3.0** (matches DDbDP). Then put
   the record URL in the paper's availability section.
   **Zenodo deposits are permanent — a published record cannot be deleted, only
   superseded.** Check the zip before publishing, not after.
3. **Do not** point `anonymous.4open.science` at the project's GitHub repo. That
   repo carries the author's name, handle and Hub identifiers throughout; the
   service filters content, and this is not a risk worth taking during a blind
   review.

**Either way, one sentence in the paper changes.** The availability section
currently says the bundle is "available to reviewers through the programme
chairs" — a channel the CFP describes nowhere. It should say either that the
bundle is attached to the submission (route 1) or give the anonymised link
(route 2).

## 8. Submission mechanics

`check_submission.py` runs 16 checks — build clean, word count, anonymity across
four surfaces (source, rendered text, PDF metadata, embedded paths including the
figure PDFs), no placeholders, all refs cited, all floats referenced, reviewer
bundle clean. Anonymisation is automatic: the class prints "Under Review /
Anonymous Submission" unless `[final]`.

Upload `paper.pdf` plus `anon-artifact.zip` (supplementary, if EasyChair takes
it). The availability section says the bundle is available "through the programme
chairs", so there is **no dead link and nothing to register**.

**Toolchain**, so a new session does not re-derive it: BasicTeX ships no
biblatex/biber — `tlmgr --usermode install biblatex …` works, but **biber is not
relocatable** (`brew install biber`). The template's 42 MB of fonts are gitignored;
re-fetch per `paper/chr2027/README.md`. `matplotlib` was added to `.venv` for the
figures (not a project dep — same category as duckdb/torch, see CLAUDE.md §4).
