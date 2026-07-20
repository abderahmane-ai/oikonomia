"""Greek folding for lexicon matching, with an exact map back to the original.

Papyrological Greek is orthographically noisy: the same word appears with and
without accents, with breathings the editor supplied or omitted, with iota
subscript or adscript, capitalised or not, and with final or medial sigma. A
lexicon keyed on surface forms would need every variant enumerated, which is
exactly the hand-written-from-memory approach this project forbids. Instead we
fold both the lexicon and the text into one canonical shape and match there.

Folding is deliberately **lossy but reversible in position**: the folded text is
not invertible to the original string, but every folded character records which
original character produced it. That is what makes it safe — annotations and
extracted spans are always reported in *original* offsets, never folded ones, so
nothing downstream ever sees the folded form.

The folds, each of which collapses a distinction that is editorial rather than
lexical:

* combining marks are dropped (accents, breathings, diaeresis, iota subscript);
* case is folded;
* final sigma ``ς`` is folded to ``σ``, which Python's ``lower()`` does not do.
"""

from __future__ import annotations

import unicodedata

from pydantic import BaseModel, Field

from oikonomia.schemas.spans import CharSpan

FINAL_SIGMA = "ς"
SIGMA = "σ"


class NormalizedText(BaseModel):
    """Folded text plus the position map back to the string it came from.

    ``origin[i]`` is the index, in the original string, of the character that
    produced folded character ``i``. It is non-decreasing but may skip values
    (a dropped accent) and may repeat (one original character folding to
    several), so it is a map, not an offset delta.
    """

    text: str
    origin: list[int] = Field(default_factory=list)
    source_len: int

    def to_original(self, span: CharSpan) -> CharSpan | None:
        """Map a span in folded space back to the original string.

        Returns ``None`` for an out-of-range span. An empty span maps to the
        original position of the character that follows it.
        """
        if span.start > len(self.text) or span.end > len(self.text):
            return None
        if span.is_empty:
            at = self.origin[span.start] if span.start < len(self.origin) else self.source_len
            return CharSpan(start=at, end=at)
        start = self.origin[span.start]
        # Re-open on the *last covered* character, so a trailing dropped accent
        # in the original is included rather than silently truncating the word.
        end = self.origin[span.end - 1] + 1
        return CharSpan(start=start, end=end)


def fold_char(ch: str) -> str:
    """Fold a single character. May return ``""`` (a dropped combining mark)."""
    decomposed = unicodedata.normalize("NFD", ch)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower().replace(FINAL_SIGMA, SIGMA)


def normalize(text: str) -> NormalizedText:
    """Fold ``text`` for matching, recording each character's origin.

    Folding is done per original character rather than over the whole string:
    a whole-string ``NFD`` would make the folded length depend on how many
    combining marks each character decomposes into, and recovering the origin
    map from that is guesswork. Per character, the mapping is exact by
    construction.
    """
    chars: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        for folded in fold_char(ch):
            chars.append(folded)
            origin.append(i)
    return NormalizedText(text="".join(chars), origin=origin, source_len=len(text))
