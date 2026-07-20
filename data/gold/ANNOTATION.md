# What to annotate, and how

Batch file: **`data/gold/to_annotate.jsonl`** — 150 documents, ~89k characters.
Full label definitions and hard cases: [`resources/schema/annotation_guidelines.md`](../../resources/schema/annotation_guidelines.md).

Regenerate with `oik gold sample --n 150 --iaa 30 --blind 30` (deterministic
for a given seed).

---

## 1. The file format

One JSON object per line. **You fill in `entities` and `relations`. Nothing
else should change.**

```json
{
  "doc_id": "10067",
  "text": "ἀντίγραφον διαγραφῆς διὰ τῆς Φανίου τραπέζης ἐν Καρανίδι ἔτους …",
  "meta": {
    "genre": "loan", "date_bucket": "early_roman", "date_mid": 74.0,
    "n_chars": 361, "split": "train", "regime": "split_random",
    "corpus_rev": "d7a34f302d1e44e271256092c2b780733187b478"
  },
  "entities": [],
  "relations": [],
  "suggested_entities": [ {"start": 57, "end": 62, "label": "DATE_REF", "text": "ἔτους"} ],
  "double_annotate": false
}
```

| field | meaning |
|---|---|
| `text` | **The only thing you annotate.** Whitespace already collapsed, so offsets are stable. |
| `entities` | **You fill this.** |
| `relations` | **You fill this.** |
| `suggested_entities` | Machine pre-annotations. **Often wrong. Not gold.** `null` on blind documents. |
| `double_annotate` | `true` → a second annotator also does this one, for agreement. Don't compare notes. |

### Entity format

```json
{"start": 57, "end": 62, "label": "DATE_REF", "text": "ἔτους"}
```

`start`/`end` are **Python character offsets** into `text`, half-open, so
`text[start:end]` is exactly the annotated string. Include `text` — it is
redundant, and that redundancy is the check that catches off-by-one errors.

> **`end` is exclusive — it is one past the last character.** This is the
> single commonest annotation error. `ἔτους` at position 57 ends at **62**,
> not 61. A one-character span like `QUANTITY` "β" at 43 is `43:44`; writing
> `43:43` selects *nothing at all* and the entity silently vanishes.
>
> Do not count characters by hand. **Run the checker after every session:**
>
> ```sh
> uv run oik gold check              # every span must select its own text
> uv run oik gold check --fix        # move offsets onto the text they claim
> ```
>
> `--fix` trusts the `text` field and repairs the offset, which is why `text`
> is required. A span whose text is not in the document is left alone and keeps
> failing — that one needs you. Relation *direction* is never auto-fixed.
>
> If offsets are drifting further out the deeper into a document you go, you
> are annotating an **outdated `to_annotate.jsonl`**. Re-export it
> (`oik gold sample --n 150 --iaa 30 --blind 30`) and re-run `--fix`.

### Relation format

Indices into **your** `entities` array (0-based, in the order you wrote them):

```json
{"head": 4, "tail": 2, "type": "HAS_CURRENCY"}
```

**Direction is fixed by the relation's name — head first, tail second:**

| Relation | head → tail |
|---|---|
| `HAS_QUANTITY` | `COMMODITY` → `QUANTITY` |
| `HAS_UNIT` | `QUANTITY` → `UNIT` |
| `HAS_CURRENCY` | `MONEY_AMOUNT` → `CURRENCY` |
| `HAS_PRICE` | `COMMODITY` → `MONEY_AMOUNT` |
| `CHARGED_UNDER` | `MONEY_AMOUNT` → `TAX_TERM` |

Read it as a sentence: *the commodity has quantity twelve*, so the commodity is
the head. `oik gold check` enforces this and tells you when endpoints are
reversed.

`PARTY_OF`, `DATED_TO`, `PAID_BY` and `PAID_TO` are defined as pointing at
"the transaction" — **which is not an entity**, so there is currently nothing
to point at. The checker flags them as `relation_unanchored`. Record them
however is natural for now (pointing at the good or the amount is reasonable)
and flag the document; the schema needs a decision here, and it is better made
against real examples than in the abstract.

---

## 2. Labels

**Money and goods**

| label | what | example |
|---|---|---|
| `MONEY_AMOUNT` | a number counted in currency | `Β` (=2000) |
| `CURRENCY` | the denomination | `δραχμῶν`, `ταλάντων`, `νομίσματος` |
| `QUANTITY` | a number counted in anything else | `μ`, `τεσσαράκοντα` |
| `UNIT` | the measure | `ἀρτάβας`, `ἀρούρας`, `κεράμια` |
| `COMMODITY` | the good | `πυροῦ`, `οἴνου`, `οἰκίας` |
| `PRICE_TERM` | a price/valuation word | `τιμῆς`, `ἀλλαγή` |

**People and places**

| label | what | example |
|---|---|---|
| `PERSON` | a personal name, with patronymic | `Νεχούτης`, `Ἥρων Ἥρωνος` |
| `OCCUPATION` | trade or office | `τελωνῶν`, `ἀντιγραφεύς`, `πράκτωρ` |
| `PERSON_ROLE` | transactional role word | lessor, lessee, payer |
| `PLACE` | toponym, with qualifier | `Κροκοδίλων πόλει` |

**Time and heading**

| label | what | example |
|---|---|---|
| `DATE_REF` | in-text date — **one span covering word AND number** | `ἔτους νβ`, `Παχὼν κα` |
| `TAX_TERM` | named impost or due | `λαογραφίας`, `δεκάτης ἐνκυκλίου` |

**Relations:** `HAS_QUANTITY`, `HAS_UNIT`, `HAS_CURRENCY`, `HAS_PRICE`,
`PARTY_OF`, `PAID_BY`, `PAID_TO`, `DATED_TO`, `CHARGED_UNDER`.

---

## 3. A fully worked example

Document 134 (in the corpus, not this batch), 394 characters:

> ἔτους νβ Παχὼν κα. τέτακται ἐπὶ τὴν ἐν Κροκοδίλων πόλει τράπεζαν ἐφʼ ἧς
> Ἀπολλώνις δεκάτης ἐνκυκλίου … παρὰ Πανίσκου καὶ Κεφάλωνος τελωνῶν …
> Πολυδεύκης ὁ ἀντιγραφεὺς / Νεχούτης ὃς καὶ Εὔνομος Πατσεοῦτος οἰκίας …
> ἣν τέθεικεν Πατσεοῦς ὁ πατὴρ αὐτοῦ χαλκοῦ δραχμῶν Β, οὗ ἀλλαγὴ σ.

*(Year 52, Pachon 21. Paid to the bank in Krokodilon Polis over which Apollonis
presides, for the 10% sales tax, from Paniskos and Kephalon the tax-farmers …
signed by Polydeukes the checking-clerk: Nechoutes also called Eunomos son of
Patseous, for a house … which his father Patseous deposited, of bronze drachmas
2000, of which the exchange fee 200.)*

```jsonc
"entities": [
  {"start":   6, "end":  14, "label": "DATE_REF",     "text": "ἔτους νβ"},
  {"start":  15, "end":  23, "label": "DATE_REF",     "text": "Παχὼν κα"},
  {"start":  45, "end":  61, "label": "PLACE",        "text": "Κροκοδίλων πόλει"},
  {"start":  78, "end":  87, "label": "PERSON",       "text": "Ἀπολλώνις"},
  {"start":  88, "end": 105, "label": "TAX_TERM",     "text": "δεκάτης ἐνκυκλίου"},
  {"start": 127, "end": 135, "label": "PERSON",       "text": "Πανίσκου"},
  {"start": 140, "end": 149, "label": "PERSON",       "text": "Κεφάλωνος"},
  {"start": 150, "end": 157, "label": "OCCUPATION",   "text": "τελωνῶν"},
  {"start": 185, "end": 195, "label": "PERSON",       "text": "Πολυδεύκης"},
  {"start": 198, "end": 209, "label": "OCCUPATION",   "text": "ἀντιγραφεὺς"},
  {"start": 217, "end": 225, "label": "PERSON",       "text": "Νεχούτης"},
  {"start": 233, "end": 240, "label": "PERSON",       "text": "Εὔνομος"},
  {"start": 241, "end": 251, "label": "PERSON",       "text": "Πατσεοῦτος"},
  {"start": 252, "end": 258, "label": "COMMODITY",    "text": "οἰκίας"},
  {"start": 340, "end": 348, "label": "PERSON",       "text": "Πατσεοῦς"},
  {"start": 363, "end": 369, "label": "CURRENCY",     "text": "χαλκοῦ"},
  {"start": 370, "end": 377, "label": "CURRENCY",     "text": "δραχμῶν"},
  {"start": 378, "end": 379, "label": "MONEY_AMOUNT", "text": "Β"},
  {"start": 384, "end": 390, "label": "PRICE_TERM",   "text": "ἀλλαγὴ"},
  {"start": 391, "end": 392, "label": "MONEY_AMOUNT", "text": "σ"}
],
"relations": [
  {"head": 17, "tail": 16, "type": "HAS_CURRENCY"},   // Β  -> δραχμῶν
  {"head": 13, "tail": 17, "type": "HAS_PRICE"},      // οἰκίας -> Β
  {"head": 17, "tail":  4, "type": "CHARGED_UNDER"},  // Β  -> δεκάτης ἐνκυκλίου
  {"head": 19, "tail": 16, "type": "HAS_CURRENCY"}    // σ  -> δραχμῶν
]
```

The **baseline finds 8 of these 20** — the money, the dates, the two
occupations. Every `PERSON`, the `PLACE`, the `COMMODITY` and the `TAX_TERM`
are yours. That is the gap this work exists to close.

---

## 4. Rules that decide the ambiguous cases

1. **A date is one span, number included.** `ἔτους νβ`, not `ἔτους` + `νβ`.
   The number is what makes it a date.
2. **`MONEY_AMOUNT` vs `QUANTITY`** is decided by what the number is counted
   in. Governed by a currency → money. Otherwise → quantity.
3. **Adjectival metal is not currency.** `ποτήριον χαλκοῦν` = "a bronze cup" →
   the *cup* is a `COMMODITY`; `χαλκοῦν` is nothing. But `χαλκοῦ νομίσματος`
   ("in bronze coin") *is* `CURRENCY`. Test: does it say what an amount is
   reckoned in, or what an object is made of?
4. **Occupations that look like goods.** `χαλκεύς` (coppersmith),
   `σιτολόγος` (grain officer), `ἐλαιουργός` (oil-worker) are `OCCUPATION`,
   never `CURRENCY`/`COMMODITY`, despite sharing a stem.
5. **Names that look like occupations.** `Γεώργιος` is the name George;
   `γεωργός` is a farmer. Capitalisation distinguishes them — trust it.
6. **Lines bound transactions in accounts.** Don't relate a commodity on one
   line to a quantity on the next unless the syntax plainly runs over.
7. **Lost text.** Annotate what the edition reads, including restorations. If
   a numeral is entirely lost (`…`), do **not** invent a `QUANTITY` — annotate
   the `COMMODITY` and leave it unlinked.
8. **Totals.** `γίνονται`/`γίνεται` ("total") restates amounts already given.
   Annotate its entities, but flag the transaction as a summary so the
   database does not double-count.

**When a case is not covered here, do not guess silently — write it down.**
Section 5 of the guidelines is expected to grow from exactly these; the new
rules are as much a deliverable as the spans.

---

## 5. Working notes

- **`suggested_entities` is a machine guess and is often wrong.** Delete what
  is wrong rather than working around it. It is a time-saver, not an authority.
- **30 documents have `suggested_entities: null`.** That is deliberate: seeing
  suggestions anchors you to them, so the blind subset is the only honest basis
  for measuring how good the baseline actually is. Please annotate those first,
  while unanchored.
- **30 documents have `double_annotate: true`.** A second annotator does these
  independently — no discussion beforehand. Target Cohen's κ ≥ 0.80.
- Save output as `data/gold/annotated.jsonl` (same schema, `entities` and
  `relations` populated). `data/gold/` is tracked in git.
- Rough budget: ~89k characters, 150 documents. At a few minutes per document
  expect 8–15 hours for a first pass.
