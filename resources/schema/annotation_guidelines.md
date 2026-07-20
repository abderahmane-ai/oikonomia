# OIKONOMIA annotation guidelines (v0.2)

Scope: entity and relation annotation over Greek documentary papyri from the
DDbDP, at corpus rev `d7a34f302d1e44e271256092c2b780733187b478`.

This is the contract between the gold annotation (Phase 5), the weak/silver
labeling (Phase 6), and the models (Phases 7–8). Every example below is real
text from the corpus, not invented.

---

## 0. The ten rules

The whole method in one screen. Everything below §0 is the reasoning and the
edge cases; if two parts of this document ever seem to disagree, **these ten
win.** Each is stated as a rule because annotation needs rules, not
preferences — the target is Cohen's κ ≥ 0.80 between annotators.

**I. Annotate the transaction, not the prose.** The target is a database row
that stands on its own — *who* moved *what*, *how much*, *to whom*, *when*,
*under what heading*. If a span does not help build or trace such a row, it is
not annotated. `ιϛ ἔτος πυροῦ ἀρτάβας τεσσαράκοντα` → commodity wheat, qty 40,
unit artaba, dated to a regnal year.

**II. Every span selects exactly its own text — and you prove it with the
tool, not your eyes.** Offsets are half-open `[start, end)`, so `end` is one
past the last character (`ἔτους` at 57 ends at **62**). Carry the `text`
field, and run `oik gold check` (and `--fix`) after every session. Never count
characters by hand.

**III. Every numeral gets exactly one decision.** No numeral is left unlabelled
by accident. It is `QUANTITY`, `MONEY_AMOUNT`, `FRACTION`, `AGE`, or part of a
`DATE_REF` — or, rarely and *deliberately*, nothing (an isopsephism like `χμγ`,
a sheet number like `κολλήματος μϛ`). "I didn't get to it" and "it is not a
quantity" must never look the same in the data.

**IV. A number's type is fixed by what it counts.** Governed by a `CURRENCY` →
`MONEY_AMOUNT`; by a unit or good → `QUANTITY`; sitting in a date → *inside*
the `DATE_REF`, not a separate span; a stated age → `AGE`. The shape of the
numeral is irrelevant; its job decides.

**V. Annotate the sense in context; the lexicon is a hint, never the
authority.** `χαλκοῦν` the adjective ("bronze cup") is not `χαλκοῦ` the coin;
`τιμή` the price is not a tax; `φορά` the donkey-load is a `UNIT`, `φόρος` the
rent is a `TAX_TERM`; `Πύρων` is a man, not a commodity. Same stem, different
word — read the word.

**VI. People: one span, with three labels.** A personal name is a single
`PERSON` including its filiation (`Θεόδωρος Ἱππίου` is one span). A trade or
office is `OCCUPATION` (`Ἀρτεμίδωρος` **and** `ἰατρός`, two spans). A party
named only by role — including an unnamed one — is `PERSON_ROLE`, **and its
modality is inside the span**: `χωρὶς κυρίου`, never bare `κυρίου`.

**VII. A `DATE_REF` is the time expression and nothing else.** The ruler named
inside a dating formula is a `PERSON`; the iteration figure (`τὸ ι`) is its own
`DATE_REF`. Keep date spans short and syntactically whole (`ἔτους ὀγδόου`,
`Φαρμοῦθι ιδ`). An anaphora that only points back at a date (`ἐκείνου τοῦ
ἔτους`, "of that year") is not one.

**VIII. Anchor every transaction on its trigger word, and hang the full graph
off it.** The word that names the deal — `ὁμολογία`, `μίσθωσις`, `δάνειον`,
`ὁμολογεῖ`, `μισθώσασθαι` — is a `TRANSACTION` span. Every party gets
`PARTY_OF → TRANSACTION`; the date gets `DATED_TO`; the price gets `HAS_PRICE`.
A document with eight contracts has eight anchors. A bare account line with no
trigger gets none — its `HAS_QUANTITY`/`HAS_UNIT` links need no anchor.

**IX. Restored text is real; lost text is not invented; ellipsis is kept.**
Annotate the `edited` view including `<supplied>` restorations. If a numeral is
lost to a `<gap>`, annotate the good and leave the quantity unlinked — do not
invent it. If the scribe elides the head noun (`μικρότερα α`, "smaller [ones]
1"), annotate the surviving word as the `COMMODITY`; the value is real.

**X. When genuinely torn, choose completeness of the row and agreement between
annotators.** Prefer the shorter, reproducible span; never drop real value to
avoid a hard call (half an aroura is half an aroura); and when a new case forces
a decision, **write it into §5 in the same commit** so the next document is
decided the same way. A rule you keep in your head is a rule the other
annotator does not have.

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
| `PERSON` | personal names | **one span incl. filiation** (`Θεόδωρος Ἱππίου` whole); person-linking across mentions is a later post-process, not annotated here |
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
They are recorded as rules so a second annotator reaches the same answer. Three
were confirmed as project-owner decisions and are now **settled** (relation
scope = full; names = one span with filiation; genitive-named parcels =
`PLACE`); the rest stand until a real counter-example overturns one — and then
it changes here, in the same commit, never silently.

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

**A κλῆρος named after a person is a `PLACE`, and the span includes `κλήρου`.**
`ἐκ τοῦ Εἰρηναίου κλήρου` → `PLACE` = `Εἰρηναίου κλήρου` (likewise `Φίλωνος
κλήρου`, `Ἀνδρονίκου κλήρου`). The holding is identified by its original
allottee, but the referent is a parcel of land, so it feeds the geographic
analysis, not the prosopography. Including the structural word `κλήρου` in the
span is what keeps the eponym from reading as a bare `PERSON`. Same treatment
for other genitive-named places built on `κώμη`, `ἄμφοδον`, `ἐποίκιον`.
*(Settled decision, not a provisional one — the model may learn that some
person-looking strings are places, and that is correct.)*

**Elliptical commodities are annotated.** Account lines drop the head noun:
`χλαμύδες χρωμάτιναι γ / μικρότερα α / λευκὰ α` — the second and third entries
are "smaller [ones]" and "white [ones]". Annotate the surviving adjective as
`COMMODITY`; the alternative is losing two thirds of the transactions on the
page.

**Counted people are linked with `HAS_QUANTITY`.** `ἱερεῖς β` ("two priests")
is an `OCCUPATION` plus a `QUANTITY`, joined `ἱερεῖς → β`. `HAS_QUANTITY`
therefore accepts `OCCUPATION` and `PERSON_ROLE` heads, not only `COMMODITY` —
an allocation register that records *how many priests drew rations* is data,
and discarding it to satisfy a narrow type constraint was the wrong trade. (The
first draft left these unlinked; this supersedes it.)

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

## 6. The batch file, and how to work it

The batch is **`data/gold/to_annotate.jsonl`** — one JSON object per line,
regenerable with `oik gold sample --n 150 --iaa 30 --blind 30` (deterministic
for a seed). Output goes to **`data/gold/annotated.jsonl`**, same schema with
`entities` and `relations` filled in. Both live in `data/gold/`, which is
tracked in git.

```json
{
  "doc_id": "10067",
  "text": "ἀντίγραφον διαγραφῆς διὰ τῆς Φανίου τραπέζης …",
  "meta": { "genre": "loan", "split": "train", "corpus_rev": "d7a34f30…" },
  "entities": [],
  "relations": [],
  "suggested_entities": [ {"start": 57, "end": 62, "label": "DATE_REF", "text": "ἔτους"} ],
  "double_annotate": false
}
```

| field | meaning |
|---|---|
| `text` | **The only thing you annotate.** Whitespace is already canonical (rule II), so offsets are stable. |
| `entities` / `relations` | **You fill these.** Entity format `{"start","end","label","text"}`; relation format `{"head","tail","type"}` where `head`/`tail` index *your* `entities` in the order you wrote them. |
| `suggested_entities` | A machine pre-annotation from the weak baseline. **Often wrong, and not gold** — delete what is wrong rather than working around it. `null` on blind documents. |
| `double_annotate` | `true` → a second annotator does this document independently, for agreement. Do not compare notes first. |

Three workflow rules, in order of how often they are broken:

1. **Run `oik gold check` after every session** (and `--fix` to repair
   offsets from the `text` field). This is rule II, and it is not optional —
   it is the only thing standing between you and a silently corrupt gold set.
2. **Annotate the ~30 blind documents (`suggested_entities: null`) first,
   while unanchored.** Seeing a suggestion anchors you to it, so the blind
   subset is the only honest basis for later measuring how good the baseline
   was. If you annotate suggested documents first you contaminate that number.
3. **Do the `double_annotate` documents independently** — no discussion
   beforehand. Target Cohen's κ ≥ 0.80; disagreements resolve into §5 as new
   rules.

For fully worked, rule-conformant examples, read `data/gold/annotated.jsonl` —
the first 15 documents are annotated to this guide and pass `oik gold check`.

## 7. Annotation unit and agreement

- The unit of annotation is the **document**.
- Double-annotate a sample for inter-annotator agreement; report Cohen's κ on
  entity labels and exact-span F1. Target: κ ≥ 0.80 on entities before gold
  annotation is considered reliable.
- Disagreements resolve into this file as new rules in §5. This document is
  expected to grow; version it when rules change.

## 8. Status

v0.2 — the ten rules in §0 are now the spine, and §5 records every decision
taken against real text. Calibrated against the first 15 annotated documents
(`data/gold/annotated.jsonl`, 420 entities / 124 relations, `oik gold check`
clean). Sections 3–4 are stable enough to build the Phase 6 weak labeler
against; §5 grows fastest as real documents are annotated.

Settled by the project owner (2026-07-21):
- **Relation scope is full** — every transaction carries `PARTY_OF` for all
  parties, `DATED_TO`, and `HAS_PRICE`, not only the measurable
  quantity/unit/currency links. This is what lets the DB answer "who", not just
  "how much".
- **A `PERSON` is one span including filiation**; cross-mention person-linking
  is a later post-process, not part of gold.
- **A genitive-named parcel is a `PLACE`** (`Εἰρηναίου κλήρου`), span including
  the structural word.

Resolved since v0.1:
- `TRANSACTION` and `AGE` added as entity types; `PARTY_OF`/`DATED_TO` now
  anchored on the `TRANSACTION` span (they previously had no anchor).
- `FRACTION` documented in the §3 tables (it was emitted and used but never
  defined).
- `DATE_REF` no longer absorbs ruler titulature — the ruler is a `PERSON`.
- `HAS_QUANTITY` widened to accept `OCCUPATION`/`PERSON_ROLE` heads (`ἱερεῖς β`).
- `τιμή` → `PRICE_TERM`; `φορά` → `UNIT`; `φυλακιτικόν` → `TAX_TERM`; adjectival
  metal dropped from `CURRENCY`.

Still open:
- No `PERSON`, `PERSON_ROLE` or `PLACE` lexicons. Personal names are the hard
  case — folding erases the capital that distinguishes `Γεώργιος` (a name)
  from `γεωργός` (a farmer), handled by exclusion in `occupations.yaml`.
- `PAID_BY`/`PAID_TO` are defined but not yet exercised on gold; their
  direction is the hardest thing for annotators to agree on, and the first
  documents used `PARTY_OF` instead. Introduce them only where a text states
  direction of transfer unambiguously.
- `oik lexicon verify` guards attestation, not sense.
