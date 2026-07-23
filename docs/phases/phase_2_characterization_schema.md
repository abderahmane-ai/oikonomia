# Phase 2 — Characterization & Schema Design

### ✅ Phase 2 — Characterization & schema design (done)

**Done so far**
- **Corpus revision pinned:** `ingest.idp_git_rev =
  d7a34f302d1e44e271256092c2b780733187b478` (papyri/idp.data HEAD, 2026-07-20)
  in `configs/base.yaml`. Every artifact now records this sha.
- **`sync.py` made efficient:** clone uses `--filter=blob:none` (blobless partial
  clone), fetching only the blobs the pinned rev needs instead of every blob in
  the repo's multi-GB history.
- **Corpus downloaded (partially checked out)** — see §9 for exact state.

**Delivered (all five planned items)**
1. **Full-corpus build at parse rate 1.000.** All 67,980 DDbDP docs, 0 failures
   (~85s). `oik corpus stats` recomputes the §7 ledger over the whole table in
   ~7s, streaming record batches. See §7 for the numbers this corrected.
2. **Lexicons mined, not recalled** — `resources/lexicon/{currency,measures,
   commodities,tax_terms,fractions,date_terms}.yaml`, 55+ entries. `oik lexicon
   mine` harvests tokens adjacent to every `<num>` (clipped to the numeral's own
   line) and ranks by document frequency; the generator hard-fails on any form
   absent from that evidence.
3. **Lexicon code**: `labeling/normalize.py` (folding + exact per-character
   origin map), `lexicon.py`, `matcher.py` (leftmost-longest, token-boundary
   anchored, spans returned in *original* offsets), `mine.py`, `evaluate.py`.
4. **`resources/schema/annotation_guidelines.md`** — entity/relation contract,
   grounded in real corpus text, with the recurring hard cases in §5.
5. **`weak_rules.py` proximity baseline**, written before any model exists.

**Measured results (the bar Phases 7–8 must beat)**
- Lexicon attachment: **62.35%** of 528,085 numerals get a lexicon term
  (`oik lexicon eval`). By genre it tracks document type: register ~80%,
  account ~68%, list ~67%, vs petition ~35%, contract ~35% — where numerals
  are ages and regnal years, not economic quantities.
- Baseline (`oik lexicon baseline`): **74.50% numeral link rate**, 16.95% of
  numerals suppressed as dates.
- **`oik lexicon verify`: 336/336 forms attested, 0 unattested.** This is the
  standing guard on "measured, never recalled" — an invented form matches
  nothing and raises no error, so nothing else would catch it. Also a test
  (`-m corpus`, skipped when the corpus is absent).

**Resolved judgment call:** match on the **edited** view. Measured basis:
`<expan>` covers 68.8% of documents and `<supplied>` 62.4%, so the diplomatic
view would strip a majority of currency terms and lose restored amounts
outright. Reversible via the `OffsetMap`.

**Deliberately dropped:** `form_expansions.yaml` (planned in the original
Phase 2 step 2) was **not** built, and should not be. It existed to map
abbreviated forms to their expansions — which is precisely what the `edited`
view already does via `<expan><ex>`, and matching on the edited view is now the
resolved decision. The residue is handled by the `abbrev_forms` lists in each
lexicon file, and those account for only **1.15%** of all matches. Revisit only
if diplomatic-view matching is ever adopted.

**Defects found and fixed** (each by checking real usage, not by reasoning
about the words — the context check is `oik lexicon mine` plus reading lines):
- `τιμή` was filed under `TAX_TERM`; `ἡ τιμὴ τοῦ βασιλικοῦ σίτου` is a sale
  price. Now its own `PRICE_TERM`. Cut spurious `CHARGED_UNDER` by 30%
  (9,403 → 6,603).
- `φορά` was a `TAX_TERM`; `ὀνικαὶ φοραὶ β` is "two donkey-loads". Now a
  `UNIT`. `φόρος` (rent/tribute) stays a tax. `φυλακιτικόν` (guard tax) added.
- Adjectival metal dropped from `CURRENCY`: `χαλκοῦν`/`χαλκᾶ`/`χαλκαῖ` describe
  bronze *objects* (`λυχνίαι χαλκαῖ β` = two bronze lampstands), and `χρυσᾶ` is
  also the personal name **Χρυσᾶ**. Monetary `χαλκοῖ` kept.
- `μύρια`/`μυρι` dropped from `myriad`: bare number words, not the multiplier.
- **`occupations.yaml` added** (13 entries, mined + context-checked). Covers the
  stem-sharing false friends: `χαλκεύς`, `σιτολόγος`, `ἐλαιουργός`, `κεραμεύς`.
  Excludes `γεωργίου`/`γεώργιος` — folded, those are the *name* Georgios, not
  the trade `γεωργός`.

Net: 88 entries / 336 forms across 8 categories. Attachment and link rate both
rose slightly; precision rose considerably more than the rates show.

**Still open before Phase 5:**
- No `PERSON` / `PERSON_ROLE` / `PLACE` lexicons. Personal names are the hard
  case: folding erases the capital distinguishing `Γεώργιος` from `γεωργός`.
- `verify` guards *attestation*, not *sense* — it proves a form occurs, not
  that it is filed under the right category. Only gold annotation settles that.
