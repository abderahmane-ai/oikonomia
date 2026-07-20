"""Longest-match lexicon matching, reporting spans in original offsets.

Matching runs over folded text (accents stripped, case folded) because that is
the only way a lexicon of reasonable size covers papyrological spelling. But
every span this module returns indexes the **original** string the caller passed
in, so downstream annotation, evidence pointers and model training data never
touch the folded form.

Matching is anchored to token boundaries. That is what keeps the truncated
abbreviation forms safe: ``δραχμ`` matches a standalone ``δραχμ`` but not the
first five characters of ``δραχμαι``, which is a different (full) form of the
same entry and must be matched as itself.
"""

from __future__ import annotations

from pydantic import BaseModel

from oikonomia.labeling.lexicon import Lexicon, LexiconEntry
from oikonomia.labeling.mine import tokenize
from oikonomia.labeling.normalize import NormalizedText, normalize
from oikonomia.schemas.spans import CharSpan


class LexiconMatch(BaseModel):
    """One lexicon hit, located in the original text."""

    entry_id: str
    category: str
    span: CharSpan
    text: str  # the original (accented) surface form that matched
    folded: str  # the folded form it matched as
    is_abbrev: bool


class Matcher:
    """Matches a :class:`Lexicon` against text.

    Build once and reuse: the form index is computed at construction.
    """

    def __init__(self, lexicon: Lexicon, *, include_abbrev: bool = True) -> None:
        self._index: dict[str, LexiconEntry] = {}
        self._abbrev: set[str] = set()
        for entry in lexicon.entries:
            for form in entry.forms:
                self._index[form] = entry
            if include_abbrev:
                for form in entry.abbrev_forms:
                    self._index[form] = entry
                    self._abbrev.add(form)

        # Longest-match is only meaningful across multi-token forms; a
        # single-token lexicon degenerates to a dict lookup. Computing the span
        # from the data keeps multi-word entries working if any are ever added.
        self._max_tokens = max(
            (len(form.split()) for form in self._index),
            default=1,
        )

    def match(self, text: str) -> list[LexiconMatch]:
        """Return all non-overlapping matches, leftmost-longest."""
        norm = normalize(text)
        tokens = tokenize(norm.text)
        matches: list[LexiconMatch] = []

        i = 0
        while i < len(tokens):
            hit = self._longest_at(tokens, i, norm, text)
            if hit is None:
                i += 1
                continue
            match, consumed = hit
            matches.append(match)
            i += consumed
        return matches

    def _longest_at(
        self,
        tokens: list[tuple[str, CharSpan]],
        i: int,
        norm: NormalizedText,
        text: str,
    ) -> tuple[LexiconMatch, int] | None:
        """Try the longest candidate starting at token ``i``."""
        for n in range(min(self._max_tokens, len(tokens) - i), 0, -1):
            window = tokens[i : i + n]
            candidate = " ".join(tok for tok, _ in window)
            entry = self._index.get(candidate)
            if entry is None:
                continue
            folded_span = CharSpan(start=window[0][1].start, end=window[-1][1].end)
            original = norm.to_original(folded_span)
            if original is None:
                continue
            return (
                LexiconMatch(
                    entry_id=entry.id,
                    category=entry.category,
                    span=original,
                    text=original.slice(text),
                    folded=candidate,
                    is_abbrev=candidate in self._abbrev,
                ),
                n,
            )
        return None
