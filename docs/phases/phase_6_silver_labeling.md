# Phase 6 — Weak / Silver Labeling Pipeline

### 🔶 Phase 6 — Weak/silver labeling (labeler built + validated; full train emission done)

#### ✅ Silver v2 — accuracy pass on the 115-doc all-human gold (2026-07-23)

A diagnose-then-fix pass, every change measured with `oik silver score`. **Entity
micro F1 (exact span): 0.585 → 0.667** (+0.082), no label regressed:

| label | before | after | fix |
|---|---|---|---|
| **AGE** | 0.000 | **0.970** | bug: `ἐτῶν N` was mislabeled DATE_REF (year-word); AGE rule only reclassified QUANTITY so it never fired. Now built from the `<num>` after ἐτῶν (gen. pl.), distinct from ἔτους/ἔτει regnal years. +133 AGE **and** −133 DATE_REF false positives. |
| **OCCUPATION** | 0.275 | **0.649** | +33 corpus-attested title entries (βοηθός, στρατηγός, νοτάριος, διάκονος, ἰατρός, ναύκληρος, ποιμήν …). Precision *rose* to 0.876. |
| **DATE_REF** | 0.386 | **0.518** | Καίσαρος/Αὐτοκράτορος/Σεβαστοῦ removed from the DATE_REF lexicon — gold's "ruler keeps titulature" rule tags them PERSON, so as DATE_REF they were 65 FPs. |
| **PERSON** | 0.683 | **0.715** | side-effect of the above — the titles now absorb into the ruler PERSON span. |
| **COMMODITY** | 0.444 | **0.554** | +property/land/animal entries (οἰκία, γῆ, ὄνος-not-ὄνομα, κάμηλος, πωμάριον, παράδεισος). |
| MONEY_AMOUNT | 0.650 | 0.652 | `_nearest` now reaches one line across for currency/unit (`νομισμάτιον\nἓν`), the EOL-currency/BOL-numeral split; also unblocks direction's amount. |

Also: payment-direction verbs widened (leases/orders — τελεσ, δωσ, δεδωκ, παρασχ,
μετρησ, διαστ, διαγραψ, εδεξ); direction still recall-bound (rule ceiling — it is
the Phase-8 model's job, not the silver's). `oik lexicon verify` 0 unattested;
ruff/mypy/408 tests green. **`silver.jsonl` must be re-emitted** (`oik silver
distmap` → `oik silver label`) and re-pushed for these gains to reach the model.

**Status: the silver labeler is built, scored against the gold, and run over the
whole train split.** `data/processed/silver.jsonl` (gitignored)
— **48,941 docs, 1,110,796 entities, 327,789 relations** (pre-v2; re-emit),
every span carrying a calibrated `confidence`. This is *training* material
(`provenance: silver`) — not gold, not the database.

**The scorer came first** (`labeling/score.py`, `oik silver score`): scores any
labeler against the gold per label, strict (exact span) and relaxed (overlap),
plus directed relations. It showed the Phase-2 baseline is *structurally blind*
to PERSON (30% of entities), PLACE, TRANSACTION, PERSON_ROLE, AGE — entity
recall 0.37, those five at 0.

**The labeler** (`labeling/silver.py`, `SilverLabeler`) is built *on top of*
the baseline — keeps the economic spans, adds LFs for the missing types, every
rule calibrated to a measured signal and stored in
`resources/silver/patterns.yaml`:
- **PERSON** — capitalisation (99.8% of gold persons are capital-initial),
  merged across filiation/alias particles (`Πτολεμαὶς Χαιρήμονος τοῦ Χαιρήμονος`
  is one span; bare `καί` splits co-parties; `ὃς καὶ` alias joins), minus
  standalone imperial titulature and calendar months.
- **PLACE** — admin-noun context (`κώμης X`, `X πόλεως/μερίδος/νομοῦ/κλήρου`) or
  a toponym gazetteer; the admin noun is part of the span.
- **TRANSACTION / PERSON_ROLE** — closed-class folded-stem prefixes, both
  lowercase-guarded (0/41 and 0/20 gold cases are capitalised); κύριος gated
  behind μετά/χωρίς; one TRANSACTION per document.
- **AGE** — a numeral next to ἐτῶν. **Relations** — the baseline's economic
  links plus PARTY_OF (roles + prep-marked names + the transaction's nearest
  name), DATED_TO, HAS_PRICE.

**Measured lift over the baseline** (65 gold docs, `model_draft` — agreement,
not truth):

| | baseline | silver |
|---|---|---|
| entity micro F1 exact | 0.412 | **0.598** |
| entity micro F1 relaxed | 0.470 | **0.723** |
| PERSON F1 (exact / relaxed) | 0 / 0 | **0.65 / 0.86** |
| PLACE F1 exact | 0 | **0.61** |
| relations micro F1 | 0.448 | ~0.45 |
