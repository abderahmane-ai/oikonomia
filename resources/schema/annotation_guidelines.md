# OIKONOMIA annotation guidelines (v0.1, Phase 2 draft)

Scope: entity and relation annotation over Greek documentary papyri from the
DDbDP, at corpus rev `d7a34f302d1e44e271256092c2b780733187b478`.

This is the contract between the gold annotation (Phase 5), the weak/silver
labeling (Phase 6), and the models (Phases 7–8). Every example below is real
text from the corpus, not invented.

---

## 1. What we are annotating, and why

The target is **the economic transaction**: who transferred what, how much of
it, to whom, when, and under what heading. A papyrus that says

> ιϛ ἔτος πυροῦ ἀρτάβας τεσσαράκοντα
> *(16th year, forty artabas of wheat)*

must yield a row in the derived database that survives on its own: commodity
wheat, quantity 40, unit artaba, dated to a regnal year. Everything in this
schema exists to make such a row extractable and traceable.

**Zero entity markup exists upstream.** The DDbDP encodes editorial phenomena
(`<gap>`, `<supplied>`, `<expan>`) and `<num>`, but no `persName`, `placeName`,
`measure` or `rs` — verified at 0% over a 200-document sample. Every label in
this schema has to be created. That is why the guidelines are strict about
boundaries: there is no upstream convention to fall back on.

## 2. Which view to annotate

**Annotate the `edited` view.** Recorded as a decision, with its basis:

- `<expan>` covers 68.8% of documents, so on the diplomatic view a majority of
  currency and measure terms appear as bare truncations (`δραχμ`, `αρταβ`)
  with the expansion stripped out.
- `<supplied>` covers 62.4%: on the diplomatic view, editorially restored text
  is absent entirely, so a transaction can lose its unit or its amount.

The cost is that annotations then sit partly on characters no scribe wrote.
This is acceptable and reversible: every document carries a bidirectional
`OffsetMap`, so any edited-view span whose characters are shared with the
diplomatic view can be projected back. Spans that do not project are exactly
the spans that exist only because an editor restored them — which is
information we want to keep, not lose.

Offsets are Python character indices into `edited_text`, half-open `[start,
end)`, as `CharSpan`.

## 3. Entity types

### Quantity and measurement

| Label | Covers | Example |
|---|---|---|
| `QUANTITY` | the numeric amount itself | `τεσσαράκοντα`, `ιϛ`, `α` |
| `UNIT` | the unit the amount is counted in | `ἀρτάβας`, `κεράμια`, `ἀρούρας` |
| `COMMODITY` | the good being counted | `πυροῦ`, `οἴνου`, `κριθῆς` |
| `MONEY_AMOUNT` | a numeric amount of money | `μ` in `δραχμὰς μ` |
| `CURRENCY` | the denomination or money-metal | `δραχμάς`, `ταλάντων`, `νομίσματος` |

`QUANTITY` includes both alphabetic numerals (`ιϛ`) and spelled-out numbers
(`τεσσαράκοντα`). **Do not assume `<num>` marks them all** — the corpus
contains many bare alphabetic numerals the editors never tagged (`ιβ`, `κδ`
and `λβ` are among the most frequent unattached numeral-neighbours). Annotate
the number as you read it, not as the XML tags it.

`MONEY_AMOUNT` vs `QUANTITY` is decided by what the number is counted in: a
number governed by a `CURRENCY` is a `MONEY_AMOUNT`, otherwise `QUANTITY`.

### Parties and places

| Label | Covers | Notes |
|---|---|---|
| `PERSON` | personal names | include patronymic (`Ἱππίου` in `Θεόδωρος Ἱππίου`) as part of the same mention |
| `PERSON_ROLE` | transactional role | lessor, lessee, payer, payee — the role *word*, not the person |
| `OCCUPATION` | trade or office | `βαφέως` (dyer), `σιτολόγος` (grain officer) |
| `PLACE` | toponyms | `ἐν Διὸς πόλει μεγάληι` — include the qualifier |

`OCCUPATION` is the label that most often collides with the lexicons by stem.
`χαλκεύς` (coppersmith) shares a stem with the currency `χαλκοῦς`;
`σιτολόγος` (grain officer) with the commodity `σῖτος`; `ἐλαιουργός`
(oil-worker) with `ἔλαιον`. These are **OCCUPATION, never CURRENCY or
COMMODITY.**

### Time and fiscal heading

| Label | Covers | Example |
|---|---|---|
| `DATE_REF` | any in-text date expression | `ιϛ ἔτος`, `ἰνδικτίονος`, `Μεσορὴ δ` |
| `TAX_TERM` | a named impost, due or payment heading | `λαογραφίας`, `μερισμοῦ`, `φόρου` |

`DATE_REF` is the **in-text** date reference. It is distinct from the
document's HGV dating, which is metadata and is not annotated. A regnal-year
expression is a single `DATE_REF` spanning the numeral and the year word
(`ιϛ ἔτος`), and the numeral inside it is *not* separately a `QUANTITY`.

## 4. Relations

| Relation | From → To | Example |
|---|---|---|
| `HAS_QUANTITY` | `COMMODITY` → `QUANTITY` | πυροῦ → τεσσαράκοντα |
| `HAS_UNIT` | `QUANTITY` → `UNIT` | τεσσαράκοντα → ἀρτάβας |
| `HAS_CURRENCY` | `MONEY_AMOUNT` → `CURRENCY` | μ → δραχμάς |
| `HAS_PRICE` | `COMMODITY` → `MONEY_AMOUNT` | the price paid for the good |
| `PARTY_OF` | `PERSON` → transaction | with a `PERSON_ROLE` qualifier |
| `PAID_BY` / `PAID_TO` | `PERSON` → `MONEY_AMOUNT`/`COMMODITY` | direction of transfer |
| `DATED_TO` | transaction → `DATE_REF` | |
| `CHARGED_UNDER` | `MONEY_AMOUNT` → `TAX_TERM` | ὑπὲρ λαογραφίας |

Relations are annotated **within a document**, and may cross line boundaries.
They may not cross documents.

## 5. Hard cases

These are the cases that actually recur; each is a rule, not a suggestion.

**Adjectival metal is not currency.** In `ποτήριον χαλκοῦν` ("a bronze cup"),
`χαλκοῦν` is an adjective describing material — annotate nothing, or
`COMMODITY` for the cup. Contrast `χαλκοῦ νομίσματος` ("in bronze coin"),
where it *is* `CURRENCY`. The test: does it name what an amount is reckoned
in, or what an object is made of? The lexicon matcher cannot make this
distinction and will produce false positives here; the gold annotation must.

**`τιμή` is a price, not a tax.** The v0.1 lexicon files it under
`TAX_TERM`, which is wrong in the common case: `τιμῆς` in
`τιμῆς τῆς συγχωρηθείσης` ("of the agreed price") is the price of a sale.
Annotate the *sense in context*; the lexicon's category is a hint, never
authority. **This misfiling is a known defect to fix in the lexicon.**

**Line boundaries are transaction boundaries in accounts.** In an account or
register, the entry on the next line is usually a different transaction.
Do not relate a commodity on one line to a quantity on the next unless the
syntax plainly runs over.

**Damaged and restored text.** Annotate the span as it reads in the edited
view, including `<supplied>` restorations. If a numeral is lost entirely
(`<gap>`), do not invent a `QUANTITY`; annotate the `COMMODITY` and leave the
quantity unlinked.

**Repeated totals.** `γίνονται` / `γίνεται` ("total") introduces a summary
figure that restates amounts already annotated above. Annotate the total's
own entities, and mark the transaction as a summary rather than a distinct
transfer, so the database does not double-count.

## 6. Annotation unit and agreement

- The unit of annotation is the **document**.
- Double-annotate a sample for inter-annotator agreement; report Cohen's κ on
  entity labels and exact-span F1. Target: κ ≥ 0.80 on entities before gold
  annotation is considered reliable.
- Disagreements resolve into this file as new rules in §5. This document is
  expected to grow; version it when rules change.

## 7. Status

v0.1 — drafted in Phase 2, before any gold annotation exists. Sections 3 and 4
are stable enough to build the Phase 6 weak labeler against. Section 5 will
grow fastest once real annotators hit real documents.

Known defects to fix before Phase 5:
- `τιμή` is filed under `TAX_TERM` in `resources/lexicon/tax_terms.yaml` and
  should be its own `PRICE_TERM`, or moved.
- No `PERSON`, `PERSON_ROLE`, `OCCUPATION` or `PLACE` lexicons exist yet;
  those entity types currently have guidelines but no candidate generator.
