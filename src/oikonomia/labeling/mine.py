"""Mine candidate lexicon vocabulary from the corpus itself.

The rule this module exists to enforce: **lexicon entries are measured, never
recalled**. Writing out Greek currency and measure forms from memory produces
plausible-looking words that either do not occur in the papyri or occur in a
spelling no editor used, and the resulting recall failure is invisible — the
matcher simply finds nothing and reports no error.

So we invert it. Units and currencies are the words that sit next to numbers
("40 *drachmas*", "6 *artabas* of wheat"), so we harvest the tokens adjacent to
every ``<num>`` element in the corpus and rank them by how many *documents* they
occur in. What comes out is a frequency-ordered candidate list that a human then
curates into ``resources/lexicon/``; this module never writes a lexicon itself.

Counting is by document, not by occurrence: a single account listing one word
400 times should not outrank a word used once each in 400 documents.
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from typing import Any

import pandas as pd
from pydantic import BaseModel

from oikonomia.labeling.normalize import normalize
from oikonomia.schemas.spans import CharSpan

MINE_COLUMNS = ("document_json", "canonical_genres")

# Tokens shorter than this are almost always stray letters left by damaged text
# or single-letter numerals the parser did not tag; they swamp the ranking.
MIN_TOKEN_LEN = 2

# Folded articles and particles that sit between a name and its title
# ("Πολυδεύκης ὁ ἀντιγραφεύς"). Skipped rather than counted, so they do not
# consume the title slot or dominate the ranking.
GREEK_ARTICLES = frozenset(
    {"ο", "η", "το", "του", "τησ", "τω", "τη", "τον", "την", "οι", "αι", "των", "τοισ",
     "ταισ", "τουσ", "τασ", "τα", "και", "δε", "μεν", "ωσ", "υιοσ", "υιου"}
)


class TokenCandidate(BaseModel):
    """One mined candidate: a folded token seen adjacent to a numeral."""

    token: str
    n_docs: int
    n_occurrences: int
    n_left: int  # occurrences where the token precedes the numeral
    n_right: int  # occurrences where it follows
    example_forms: list[str]  # unfolded surface forms, for the human curator

    @property
    def right_ratio(self) -> float:
        """Share of occurrences following the numeral.

        Greek unit nouns overwhelmingly *follow* their numeral ("μ δραχμάς"),
        so a high ratio is weak evidence of a unit rather than, say, a verb.
        """
        total = self.n_left + self.n_right
        return round(self.n_right / total, 3) if total else 0.0


def is_greek_letter(ch: str) -> bool:
    """True for a Greek letter, ignoring the marks folding has already removed."""
    return unicodedata.category(ch).startswith("L") and (
        "Ͱ" <= ch <= "Ͽ" or "ἀ" <= ch <= "῿"
    )


def tokenize(folded: str) -> list[tuple[str, CharSpan]]:
    """Split folded text into Greek-letter tokens with their spans."""
    tokens: list[tuple[str, CharSpan]] = []
    start: int | None = None
    for i, ch in enumerate(folded):
        if is_greek_letter(ch):
            if start is None:
                start = i
        elif start is not None:
            tokens.append((folded[start:i], CharSpan(start=start, end=i)))
            start = None
    if start is not None:
        tokens.append((folded[start:], CharSpan(start=start, end=len(folded))))
    return tokens


def _line_bounds(doc: dict[str, Any], pos: int) -> tuple[int, int] | None:
    """The edited-view extent of the line containing ``pos``."""
    for line in doc["lines"]:
        span = line.get("edited")
        if span and span["start"] <= pos < span["end"]:
            return span["start"], span["end"]
    return None


def mine_document(doc: dict[str, Any], window: int = 2) -> Iterator[tuple[str, str, str]]:
    """Yield ``(folded_token, side, surface_form)`` around each numeral.

    Context is clipped to the numeral's own line. Lines are the papyrus's real
    units of layout, and in accounts and tax registers the entry on the next
    line is a different transaction entirely — reading across a line break
    would manufacture adjacencies that do not exist.
    """
    text = doc["edited_text"]
    if not text:
        return

    for numeral in doc["numerals"]:
        span = numeral.get("edited")
        if not span:  # numerals with no locatable text (lost, or value-only)
            continue
        bounds = _line_bounds(doc, span["start"])
        if bounds is None:
            continue
        lo, hi = bounds

        line_raw = text[lo:hi]
        norm = normalize(line_raw)
        tokens = tokenize(norm.text)

        # Locate the numeral inside the folded line to split left from right.
        num_start = normalize(text[lo : span["start"]]).text
        cut = len(num_start)

        before = [t for t in tokens if t[1].end <= cut]
        after = [t for t in tokens if t[1].start >= cut + len(normalize(numeral["text"]).text)]

        for tok, tok_span in before[-window:]:
            yield tok, "left", _surface(norm, tok_span, line_raw)
        for tok, tok_span in after[:window]:
            yield tok, "right", _surface(norm, tok_span, line_raw)


def _surface(norm: Any, span: CharSpan, line_raw: str) -> str:
    """Recover the original accented form behind a folded token."""
    original = norm.to_original(span)
    return original.slice(line_raw) if original else ""


def mine_batches(
    batches: Iterable[pd.DataFrame], window: int = 2, min_docs: int = 5
) -> list[TokenCandidate]:
    """Mine numeral-adjacent vocabulary across record batches.

    Returns candidates seen in at least ``min_docs`` documents, most frequent
    first.
    """
    doc_counts: Counter[str] = Counter()
    occ_counts: Counter[str] = Counter()
    left_counts: Counter[str] = Counter()
    right_counts: Counter[str] = Counter()
    forms: dict[str, Counter[str]] = {}

    for df in batches:
        for doc_json in df["document_json"]:
            doc = json.loads(doc_json)
            seen: set[str] = set()
            for token, side, surface in mine_document(doc, window=window):
                if len(token) < MIN_TOKEN_LEN:
                    continue
                occ_counts[token] += 1
                (left_counts if side == "left" else right_counts)[token] += 1
                if surface:
                    forms.setdefault(token, Counter())[surface] += 1
                seen.add(token)
            for token in seen:
                doc_counts[token] += 1

    candidates = [
        TokenCandidate(
            token=token,
            n_docs=n_docs,
            n_occurrences=occ_counts[token],
            n_left=left_counts[token],
            n_right=right_counts[token],
            example_forms=[f for f, _ in forms.get(token, Counter()).most_common(3)],
        )
        for token, n_docs in doc_counts.items()
        if n_docs >= min_docs
    ]
    candidates.sort(key=lambda c: (-c.n_docs, c.token))
    return candidates


TITLE_COLUMNS = ("document_json",)


def mine_title_positions(
    doc: dict[str, Any], window: int = 2
) -> Iterator[tuple[str, str]]:
    """Yield ``(folded_token, surface)`` for words following a personal name.

    Occupations and roles sit in *title position* — directly after a name
    (``Ἀπολλώνιος χαλκεύς``, ``Ἥρων Ἥρωνος ἐλαιουργός``, ``Πολυδεύκης ὁ
    ἀντιγραφεύς``) — and essentially never next to a numeral. Mining only
    numeral neighbourhoods therefore cannot find them, which is why
    ``τελωνῶν`` and ``ἀντιγραφεύς`` were missing from the occupation lexicon
    despite being common.

    Names are located by **capitalisation**, which the corpus marks and which
    GreBerta's tokenizer also preserves. Articles are skipped, so ``ὁ`` in
    ``Πολυδεύκης ὁ ἀντιγραφεύς`` does not consume the slot.
    """
    text = doc["edited_text"]
    if not text.strip():
        return

    for line in doc["lines"]:
        span = line.get("edited")
        if not span:
            continue
        raw = text[span["start"] : span["end"]]
        tokens = tokenize(raw)  # works on cased text: it splits on Greek letters

        for i, (tok, _) in enumerate(tokens):
            if not tok[:1].isupper():
                continue
            taken = 0
            for follower, follower_span in tokens[i + 1 :]:
                if follower[:1].isupper():
                    break  # a second name, not a title
                folded = normalize(follower).text
                if folded in GREEK_ARTICLES:
                    continue  # "ὁ", "τοῦ" … do not consume the slot
                if len(folded) >= MIN_TOKEN_LEN:
                    yield folded, follower_span.slice(raw)
                taken += 1
                if taken >= window:
                    break


def mine_titles(
    batches: Iterable[pd.DataFrame], window: int = 2, min_docs: int = 5
) -> list[TokenCandidate]:
    """Rank words appearing in title position across record batches."""
    doc_counts: Counter[str] = Counter()
    occ_counts: Counter[str] = Counter()
    forms: dict[str, Counter[str]] = {}

    for df in batches:
        for doc_json in df["document_json"]:
            doc = json.loads(doc_json)
            seen: set[str] = set()
            for token, surface in mine_title_positions(doc, window=window):
                occ_counts[token] += 1
                if surface:
                    forms.setdefault(token, Counter())[surface] += 1
                seen.add(token)
            for token in seen:
                doc_counts[token] += 1

    candidates = [
        TokenCandidate(
            token=token,
            n_docs=n_docs,
            n_occurrences=occ_counts[token],
            n_left=0,
            n_right=occ_counts[token],  # by construction, always after the name
            example_forms=[f for f, _ in forms.get(token, Counter()).most_common(3)],
        )
        for token, n_docs in doc_counts.items()
        if n_docs >= min_docs
    ]
    candidates.sort(key=lambda c: (-c.n_docs, c.token))
    return candidates
