# ADR 0001 — Keep both diplomatic and edited text views

**Status:** accepted (Phase 1)

## Context

DDbDP editions encode two readings of the same papyrus: what the editor thinks
it says (abbreviations expanded, lost text restored, spelling regularised) and
what is physically written. Measured on the corpus: `<expan>` appears in 65% of
documents, `<choice>/<reg>/<orig>` in 47%, `<supplied>` in 70%. Currency and
measure terms — the extraction targets — are frequently abbreviations resolved
only in the edited reading.

## Decision

The parser produces **both** views plus a bidirectional `OffsetMap`, rather than
committing to one. Every span (markup, numeral, future annotation) can be located
in whichever view it belongs to and mapped to the other where the character is
shared.

## Consequences

- Annotation and evaluation can be done, and reported, on either view without
  re-parsing or re-annotating.
- Slightly more memory and parser complexity; justified by the alternative.
- **The alternative was rejected because it is unrecoverable:** annotating gold
  against a single view and later needing the other would strand the entire gold
  set — the most expensive artifact in the project.

## Invariant

For every aligned segment, `edited[e0:e1] == diplomatic[d0:d1]`, asserted in
`tests/conftest.py::assert_document_invariants` and verified across 120 random
real documents (0 failures).
