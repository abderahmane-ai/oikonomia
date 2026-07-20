"""Measure lexicon coverage against the corpus, before trusting it.

A lexicon that misses half the units fails silently — the matcher simply
returns fewer spans and reports no error — so coverage has to be measured
explicitly rather than assumed from the fact that the file looks full.

There is no gold annotation yet (that is Phase 5), so the honest proxy is
**numeral attachment**: what share of ``<num>`` elements have a UNIT or
CURRENCY term on the same line? Every numeral in a tax receipt or account
denominates *something*, so a numeral with no unit nearby is either a lexicon
gap, a date, or a regnal year. This is a lower bound on recall, not recall
itself, and it is reported as such.

The same measurement runs against either text view, which is what settles
whether to match on the edited or the diplomatic text.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.mine import MIN_TOKEN_LEN, tokenize
from oikonomia.labeling.normalize import normalize

EVAL_COLUMNS = ("document_json", "canonical_genres")

# Categories that denominate a number. COMMODITY and TAX_TERM say *what* a
# payment is for, not what unit it is counted in, so they do not count as
# attachment on their own.
DENOMINATING = ("UNIT", "CURRENCY")

# A numeral on a line carrying date vocabulary is a year, a month day or an
# indiction — not an unmeasured quantity. Separating these out is what turns the
# unattached remainder from "unexplained" into a real gap list.
DATING = ("DATE_REF",)


class GenreCoverage(BaseModel):
    genre: str
    n_numerals: int
    n_attached: int
    attachment_rate: float


class CoverageReport(BaseModel):
    """Lexicon coverage over the corpus, for one text view."""

    view: str
    n_docs: int
    n_numerals: int
    n_numerals_attached: int = Field(
        description="Numerals with a UNIT or CURRENCY match on the same line."
    )
    attachment_rate: float
    n_numerals_dated: int = Field(
        description="Unattached numerals on a line carrying DATE_REF vocabulary."
    )
    dated_rate: float
    unexplained_rate: float = Field(
        description="Numerals with neither a unit nor a date term on their line."
    )
    n_docs_with_match: int
    doc_match_rate: float
    matches_by_category: dict[str, int]
    abbrev_match_share: float = Field(
        description="Share of matches that came from a truncated abbreviation form."
    )
    top_unmatched_neighbours: list[tuple[str, int]] = Field(
        default_factory=list,
        description="Frequent tokens next to unattached numerals — the gap list.",
    )
    by_genre: list[GenreCoverage] = Field(default_factory=list)


def _spans_for_view(
    doc: dict[str, Any], view: str
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    text = doc["edited_text"] if view == "edited" else doc["diplomatic_text"]
    return text, doc["numerals"], doc["lines"]


def evaluate_coverage(
    batches: Iterable[pd.DataFrame],
    matcher: Matcher,
    view: str = "edited",
    top_gaps: int = 40,
) -> CoverageReport:
    """Measure numeral attachment across record batches for one view."""
    n_docs = n_numerals = n_attached = n_docs_with_match = 0
    n_dated = 0
    by_category: Counter[str] = Counter()
    n_abbrev = n_matches = 0
    gaps: Counter[str] = Counter()
    genre_totals: Counter[str] = Counter()
    genre_attached: Counter[str] = Counter()

    for df in batches:
        for doc_json, genres_json in zip(df["document_json"], df["canonical_genres"], strict=True):
            doc = json.loads(doc_json)
            text, numerals, lines = _spans_for_view(doc, view)
            n_docs += 1
            if not text:
                continue

            genres = json.loads(genres_json) if genres_json else []
            doc_matched = False

            # Match once per line, then ask which numerals fall on a line that
            # carried a denominating term. Matching per numeral would re-scan
            # the same line for every numeral on it.
            line_has_unit: dict[tuple[int, int], bool] = {}
            line_has_date: dict[tuple[int, int], bool] = {}
            line_tokens: dict[tuple[int, int], list[str]] = {}
            for line in lines:
                span = line.get(view)
                if not span:
                    continue
                key = (span["start"], span["end"])
                line_text = text[span["start"] : span["end"]]
                hits = matcher.match(line_text)
                for hit in hits:
                    by_category[hit.category] += 1
                    n_matches += 1
                    if hit.is_abbrev:
                        n_abbrev += 1
                    doc_matched = True
                line_has_unit[key] = any(h.category in DENOMINATING for h in hits)
                line_has_date[key] = any(h.category in DATING for h in hits)
                if not line_has_unit[key] and not line_has_date[key]:
                    covered = {h.folded for h in hits}
                    line_tokens[key] = [
                        t
                        for t, _ in tokenize(normalize(line_text).text)
                        if len(t) >= MIN_TOKEN_LEN and t not in covered
                    ]

            for numeral in numerals:
                span = numeral.get(view)
                if not span:
                    continue
                n_numerals += 1
                located = next(
                    (k for k in line_has_unit if k[0] <= span["start"] < k[1]),
                    None,
                )
                if located is None:
                    continue
                if line_has_unit[located]:
                    n_attached += 1
                    for g in genres:
                        genre_attached[g] += 1
                elif line_has_date[located]:
                    n_dated += 1
                else:
                    gaps.update(line_tokens.get(located, []))
                for g in genres:
                    genre_totals[g] += 1

            if doc_matched:
                n_docs_with_match += 1

    by_genre = [
        GenreCoverage(
            genre=g,
            n_numerals=total,
            n_attached=genre_attached[g],
            attachment_rate=round(genre_attached[g] / total, 4) if total else 0.0,
        )
        for g, total in genre_totals.most_common()
    ]

    return CoverageReport(
        view=view,
        n_docs=n_docs,
        n_numerals=n_numerals,
        n_numerals_attached=n_attached,
        attachment_rate=round(n_attached / n_numerals, 4) if n_numerals else 0.0,
        n_numerals_dated=n_dated,
        dated_rate=round(n_dated / n_numerals, 4) if n_numerals else 0.0,
        unexplained_rate=(
            round((n_numerals - n_attached - n_dated) / n_numerals, 4) if n_numerals else 0.0
        ),
        n_docs_with_match=n_docs_with_match,
        doc_match_rate=round(n_docs_with_match / n_docs, 4) if n_docs else 0.0,
        matches_by_category=dict(by_category.most_common()),
        abbrev_match_share=round(n_abbrev / n_matches, 4) if n_matches else 0.0,
        top_unmatched_neighbours=gaps.most_common(top_gaps),
        by_genre=by_genre,
    )
