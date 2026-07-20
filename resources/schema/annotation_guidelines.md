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
| `FRACTION` | a fractional part of a quantity or amount | `ἡμίσους`, `𐅵` (½), `𐅷` (⅔) |

`FRACTION` is a separate span, not folded into the `QUANTITY`, because the two
are separate tokens with separate lexica (`resources/lexicon/fractions.yaml`)
and because the fraction frequently attaches to a *unit* rather than to the
number (`ἀρούρης α 𐅵` = one and a half arouras). **Do not drop it:** half an
aroura of land or half an artaba of wheat is real value, and a price series
built from truncated quantities is wrong rather than merely incomplete.

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
| `AGE` | a person's stated age | `πεντήκοντα ὀκτὼ` in `ὡς ἐτῶν πεντήκοντα ὀκτὼ` |
| `TRANSACTION` | the word that *names* the transaction | `ὁμολογία`, `μίσθωσις`, `δάνειον`, `ὁμολογεῖ`, `μισθώσασθαι` |
| `TAX_TERM` | a named impost, due or payment heading | `λαογραφίας`, `μερισμοῦ`, `φόρου`, `φυλακιτικοῦ` |
| `PRICE_TERM` | a price or valuation | `τιμῆς` |

`DATE_REF` is the **in-text** date reference. It is distinct from the
document's HGV dating, which is metadata and is not annotated. A regnal-year
expression is a single `DATE_REF` spanning the numeral and the year word
(`ιϛ ἔτος`), and the numeral inside it is *not* separately a `QUANTITY`.

## 4. Relations

| Relation | From → To | Example |
|---|---|---|
| `HAS_QUANTITY` | `COMMODITY`/`OCCUPATION`/`PERSON_ROLE` → `QUANTITY` | πυροῦ → τεσσαράκοντα; ἱερεῖς → β |
| `HAS_UNIT` | `QUANTITY` → `UNIT` | τεσσαράκοντα → ἀρτάβας |
| `HAS_CURRENCY` | `MONEY_AMOUNT` → `CURRENCY` | μ → δραχμάς |
| `HAS_PRICE` | `COMMODITY` → `MONEY_AMOUNT` | the price paid for the good |
| `PARTY_OF` | `PERSON`/`PERSON_ROLE` → `TRANSACTION` | every party, named or not |
| `PAID_BY` / `PAID_TO` | `PERSON`/`PERSON_ROLE` → `MONEY_AMOUNT`/`COMMODITY` | direction of transfer |
| `DATED_TO` | `TRANSACTION` → `DATE_REF` | |
| `CHARGED_UNDER` | `MONEY_AMOUNT` → `TAX_TERM` | ὑπὲρ λαογραφίας |

Relations are annotated **within a document**, and may cross line boundaries.
They may not cross documents.

## 5. Hard cases

These are the cases that actually recur; each is a rule, not a suggestion.

**Adjectival metal is not currency.** In `ποτήριον χαλκοῦν` ("a bronze cup"),
`λυχνίαι χαλκαῖ β` ("two bronze lampstands") or `σπονδεῖα χαλκᾶ δ` ("four
bronze bowls"), the metal word is an adjective describing material — annotate
`COMMODITY` for the object, nothing for the adjective. Contrast `χαλκοῦ
νομίσματος` ("in bronze coin"), where it *is* `CURRENCY`. The test: does it
name what an amount is reckoned in, or what an object is made of?

The consistently adjectival forms (`χαλκοῦν`, `χαλκᾶ`, `χαλκαῖ`, `χρυσοῦν`,
`χρυσᾶ`) have been dropped from the currency lexicon, so the common cases no
longer produce false positives. `χρυσᾶ` had a second problem: folded, it is
also the personal name **Χρυσᾶ**. Genuinely monetary forms (`χαλκοῖ` in
`δραχμαὶ ε … χαλκοῖ ζ`) are kept. The residue — a monetary form used
adjectivally — still needs gold annotation to resolve.

**`τιμή` is a price, not a tax.** `τιμῆς` in `ἡ τιμὴ τοῦ βασιλικοῦ σίτου`
("the price of the royal grain") is a sale price. It was misfiled under
`TAX_TERM` in v0.1 and now has its own `PRICE_TERM` category — which cut
spurious `CHARGED_UNDER` relations by 30%. The general rule stands: annotate
the *sense in context*; the lexicon's category is a hint, never authority.

**`φορά` is a load, not an impost.** `ὀνικαὶ φοραὶ β` is "two donkey-loads" —
a `UNIT` of carriage. Distinguish it from `φόρος` (rent/tribute), which is a
genuine `TAX_TERM`. Same stem, different word.

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

### Decisions taken while annotating the first 15 documents

Each of these recurred immediately and had to be settled to annotate at all.
They are recorded as rules so a second annotator reaches the same answer; each
is still open to being overturned, but not silently.

**A `DATE_REF` covers the temporal expression only; a ruler's name inside a
dating formula is a `PERSON`.** So

> `ἔτους ὀγδόου` `[Τιβερίου Κλαυδίου Καίσαρος Σεβαστοῦ Γερμανικοῦ
> Αὐτοκράτορος]` `Φαρμοῦθι ιδ`

is `DATE_REF` + `PERSON` + `DATE_REF`, **not** one 130-character span.

*This reverses the first draft of this rule,* which absorbed the titulature
into the date. Two reasons to prefer splitting:

- **Agreement.** The formula varies constantly, so annotators must agree
  exactly where titulature begins and ends — on a span mostly made of proper
  nouns. Short, syntactically coherent spans (`ἔτους ὀγδόου`, `Φαρμοῦθι ιδ`,
  `Παχὼν κα`) are reproducible; the target is κ ≥ 0.80 and long variable spans
  put it at risk. Splitting took the mean `DATE_REF` from 30 to **8.2**
  characters.
- **The original reason expired.** Absorbing rulers existed to keep emperors
  out of the list of economic actors. Now that `TRANSACTION` exists, the
  parties are whoever carries `PARTY_OF` — so `PERSON` can be complete, and a
  ruler is simply a `PERSON` with no `PARTY_OF` edge. Ask "who were the
  parties?" by following `PARTY_OF`, never by listing every `PERSON`.

Consular dates work the same way: `ὑπατείας` is the `DATE_REF`, the consul is
a `PERSON`, and an iteration figure (`τὸ ι`, "for the 10th time") is its own
`DATE_REF`.

**A date word whose numeral is lost still gets a `DATE_REF`.** `κλήρου … ἔτους`
has the year in a lacuna; annotate `ἔτους`, exactly as a `COMMODITY` keeps its
label when its quantity is lost. But do **not** annotate an anaphoric mention
that refers back to a date rather than stating one — `ἐκείνου τοῦ ἔτους`
("of that year") is not a `DATE_REF`.

**A κλῆρος named after a person is a `PLACE`.** `ἐκ τοῦ Εἰρηναίου κλήρου`,
`ἐκ τοῦ Φίλωνος κλήρου`, `ἐκ τοῦ Ἀνδρονίκου` — the holding is identified by
its original allottee, but what is being referred to is a parcel of land.
Annotate the name as `PLACE`. **This is the least certain rule here**; the
alternative (PERSON) is defensible and it should be revisited once there are
enough instances to see which way the model generalises.

**Elliptical commodities are annotated.** Account lines drop the head noun:
`χλαμύδες χρωμάτιναι γ / μικρότερα α / λευκὰ α` — the second and third entries
are "smaller [ones]" and "white [ones]". Annotate the surviving adjective as
`COMMODITY`; the alternative is losing two thirds of the transactions on the
page.

**Counted people are not `HAS_QUANTITY`.** `ἱερεῖς β` ("two priests") is an
`OCCUPATION` and a `QUANTITY`, but `HAS_QUANTITY` is defined `COMMODITY →
QUANTITY`, so the two are left unlinked rather than mistyped. If counting
people matters to the database, the schema needs a relation for it.

**Amounts link to the denomination, not the metal.** In `ἀργυρίου ταλάντου
ἑνὸς καὶ δραχμῶν ἐνακοσίων`, both `ἀργυρίου` and `ταλάντου`/`δραχμῶν` are
`CURRENCY`, but `HAS_CURRENCY` goes from each amount to its *denomination*
(`ἑνὸς → ταλάντου`, `ἐνακοσίων → δραχμῶν`). The metal qualifies the whole sum
and is left unlinked.

**Numbers that are not quantities are not annotated.** `χμγ` heading a
Byzantine contract is an isopsephism (= ἀμήν), and `κολλήματος μϛ` is a papyrus
sheet number. Neither is an economic quantity. Read the number's job, not its
shape.

**A transaction is anchored on the word that names it.** `PARTY_OF` and
`DATED_TO` used to point at "the transaction", which was not an entity — so
there was nothing to point at and nothing to check. The fix is to annotate the
trigger itself as a `TRANSACTION` span: `ὁμολογία`, `μίσθωσις`, `δάνειον`,
`ὁμολογεῖ`, `μισθώσασθαι`, `ἐξοικονομοῦντες`.

This is not a formality — it is what makes multi-transaction documents
representable at all. A register like doc 11974 puts **eight** contracts on
eight lines, each opening with its own trigger; a document-level attribute
could not tell them apart, and anchoring on the goods or the money would
misattribute parties across contracts.

Where a document records a transaction with no trigger word — a bare account
line — annotate no `TRANSACTION`. `HAS_QUANTITY` and `HAS_UNIT` do not need
one, and the `lines` table already groups such entries.

**Unnamed parties are `PERSON_ROLE`, and they matter.** `καὶ τῆς γυναικὸς`
("and his wife") is a contracting party with no name. Annotate the role phrase
and give it `PARTY_OF` like any other party — otherwise every transaction with
an unnamed participant silently loses one.

**Annotate the guardian formula.** `χωρὶς κυρίου` ("without a guardian") and
`μετὰ κυρίου τοῦ ἀνδρός` ("with her husband as guardian") are `PERSON_ROLE`
spans, and the modality is part of the span — `χωρὶς κυρίου`, not bare
`κυρίου`. This is the single clearest textual marker of whether a woman is
acting as a legal principal in her own right, which is one of this project's
stated research questions. Dropping the negation makes the two cases
indistinguishable and the question unanswerable.

**Ages are `AGE`, not `QUANTITY`.** `ὡς ἐτῶν πεντήκοντα ὀκτὼ` ("about 58 years
old") is a number, so leaving it unlabelled trains the model on an
inconsistent negative: a numeral that looks exactly like every `QUANTITY` it
is asked to find. Every numeral in a document should receive a decision —
`QUANTITY`, `MONEY_AMOUNT`, `DATE_REF`, `FRACTION` or `AGE`.

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

Resolved since the first draft:
- `τιμή` moved to its own `PRICE_TERM` category.
- `φορά` moved from `TAX_TERM` to `UNIT`; `φυλακιτικόν` (guard tax) added to
  `TAX_TERM`.
- Adjectival metal forms dropped from `CURRENCY`.
- `OCCUPATION` now has a mined lexicon (13 entries), covering the stem-sharing
  false friends the guidelines warn about: `χαλκεύς`, `σιτολόγος`,
  `ἐλαιουργός`, `κεραμεύς`.

Still open before Phase 5:
- No `PERSON`, `PERSON_ROLE` or `PLACE` lexicons. Personal names are the hard
  case — folding erases the capital that distinguishes `Γεώργιος` (a name)
  from `γεωργός` (a farmer), and that collision is already handled by
  exclusion in `occupations.yaml` rather than by any general rule.
- `oik lexicon verify` guards attestation, not sense: it proves every form
  occurs in the corpus, not that it is filed under the right category. Only
  gold annotation settles sense.
