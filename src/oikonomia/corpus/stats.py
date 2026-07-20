"""Corpus characterization: the §7 fact-ledger numbers, as running code.

Phase 1's ledger figures (markup density, date precision, place linkability,
genre-conditioned numeral density) were established by hand against samples of
the live corpus. This module recomputes them over the *whole* built table, so
they become a reproducible self-check rather than a claim: if reality drifts
from the ledger — because the corpus was repinned or a parser changed — the
numbers move and we find out.

Statistics accumulate over record batches rather than a materialised frame.
``document_json`` is by far the largest column (the parquet is ~280 MB, most of
it markup spans), and the corpus only grows; streaming keeps peak memory flat
and independent of corpus size.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
from pydantic import BaseModel, Field

from oikonomia.schemas.document import MarkupKind

# Every markup kind the parser can emit, taken from the enum rather than
# written out here: a hand-kept list silently reports 0.0 for any kind whose
# name it gets wrong, which reads as "absent from the corpus" instead of "not
# measured". Deriving it means a new MarkupKind is characterized automatically.
MARKUP_KINDS = tuple(k.value for k in MarkupKind)

# A dating this wide is effectively useless for a price series; the ledger
# tracks what fraction of the corpus falls in that bucket.
WIDE_SPAN_YEARS = 120

# Columns needed for the streaming pass. Naming them keeps `document_json` the
# only heavy column read, and lets the reader skip the rest of the table.
STATS_COLUMNS = (
    "has_hgv",
    "has_translation",
    "date_lo",
    "date_hi",
    "date_precision",
    "n_alt_dates",
    "place_tm",
    "place_pleiades",
    "canonical_genres",
    "n_numerals",
    "n_chars_edited",
    "parse_flags",
    "document_json",
)


class GenreStats(BaseModel):
    """Numeral density for one canonical genre.

    ``numerals_per_line`` is the ledger's discriminator between economic
    documents (tax registers, accounts, receipts) and prose (private letters).
    """

    genre: str
    n_docs: int
    n_lines: int
    n_numerals: int
    numerals_per_line: float


class CorpusStats(BaseModel):
    """Whole-corpus characterization. Rates are fractions of ``n_docs``."""

    n_docs: int

    # Coverage
    hgv_join_rate: float
    translation_rate: float
    empty_edited_text_rate: float

    # Dating
    date_machine_readable_rate: float = Field(
        description="Fraction of HGV-joined docs with a usable date interval."
    )
    date_exact_day_rate: float
    date_wide_span_rate: float = Field(
        description=f"Fraction of dated docs whose interval exceeds {WIDE_SPAN_YEARS} years."
    )
    date_alternative_rate: float

    # Places
    place_linkable_rate: float
    place_pleiades_rate: float

    # Markup presence: fraction of documents carrying >=1 span of each kind.
    markup_presence: dict[str, float]
    numeral_presence_rate: float = Field(
        description="Fraction of documents carrying >=1 <num> numeral. Numerals are "
        "parsed into their own table, not as MarkupKind spans."
    )

    # Text mass
    n_chars_edited: int
    n_numerals: int
    n_lines: int
    median_chars_edited: float

    genres: list[GenreStats]


class _Accumulator:
    """Running totals over record batches. ``update`` is order-independent."""

    def __init__(self) -> None:
        self.n_docs = 0
        self.n_hgv = 0
        self.n_translation = 0
        self.n_empty_text = 0
        self.n_date_readable = 0
        self.n_date_day = 0
        self.n_date_wide = 0
        self.n_date_alt = 0
        self.n_place_tm = 0
        self.n_place_pleiades = 0
        self.n_chars = 0
        self.n_numerals = 0
        self.n_lines = 0
        self.n_with_numerals = 0
        self.markup: dict[str, int] = dict.fromkeys(MARKUP_KINDS, 0)
        self.genre_docs: dict[str, int] = {}
        self.genre_lines: dict[str, int] = {}
        self.genre_numerals: dict[str, int] = {}
        # Exact median needs the full distribution; character counts are small
        # ints, so keeping them all costs ~0.5 MB at corpus scale.
        self._char_counts: list[int] = []

    def update(self, df: pd.DataFrame) -> None:
        self.n_docs += len(df)
        self.n_hgv += int(df["has_hgv"].sum())
        self.n_translation += int(df["has_translation"].sum())
        self.n_place_tm += int(df["place_tm"].notna().sum())
        self.n_place_pleiades += int(df["place_pleiades"].notna().sum())
        self.n_chars += int(df["n_chars_edited"].sum())
        self.n_numerals += int(df["n_numerals"].sum())
        self.n_date_alt += int((df["n_alt_dates"] > 0).sum())
        self.n_with_numerals += int((df["n_numerals"] > 0).sum())
        self._char_counts.extend(df["n_chars_edited"].tolist())

        self.n_empty_text += int(
            df["parse_flags"].map(lambda s: "empty_edited_text" in _loads_list(s)).sum()
        )

        # A date is machine-readable when the parser produced any bound at all.
        readable = df["date_lo"].notna() | df["date_hi"].notna()
        self.n_date_readable += int(readable.sum())
        self.n_date_day += int((df["date_precision"] == "day").sum())

        both = df["date_lo"].notna() & df["date_hi"].notna()
        self.n_date_wide += int(((df["date_hi"] - df["date_lo"]) > WIDE_SPAN_YEARS)[both].sum())

        # Per-document markup presence and line counts require the heavy column.
        for doc_json, genres_json, n_num in zip(
            df["document_json"], df["canonical_genres"], df["n_numerals"], strict=True
        ):
            doc = json.loads(doc_json)
            kinds = {m["kind"] for m in doc["markup"]}
            for kind in MARKUP_KINDS:
                if kind in kinds:
                    self.markup[kind] += 1

            n_lines = len(doc["lines"])
            self.n_lines += n_lines
            for genre in _loads_list(genres_json):
                self.genre_docs[genre] = self.genre_docs.get(genre, 0) + 1
                self.genre_lines[genre] = self.genre_lines.get(genre, 0) + n_lines
                self.genre_numerals[genre] = self.genre_numerals.get(genre, 0) + int(n_num)

    def finalize(self) -> CorpusStats:
        n = self.n_docs
        if n == 0:
            msg = "no documents to summarise — is processed/corpus.parquet empty?"
            raise ValueError(msg)

        dated = self.n_date_readable
        genres = [
            GenreStats(
                genre=g,
                n_docs=self.genre_docs[g],
                n_lines=self.genre_lines[g],
                n_numerals=self.genre_numerals[g],
                numerals_per_line=_rate(self.genre_numerals[g], self.genre_lines[g]),
            )
            for g in sorted(self.genre_docs, key=lambda g: -self.genre_docs[g])
        ]
        return CorpusStats(
            n_docs=n,
            hgv_join_rate=_rate(self.n_hgv, n),
            translation_rate=_rate(self.n_translation, n),
            empty_edited_text_rate=_rate(self.n_empty_text, n),
            # Dating rates are conditioned on the HGV join: a document with no
            # HGV record has no date to be readable or not, and folding those
            # into the denominator would understate the parser.
            date_machine_readable_rate=_rate(dated, self.n_hgv),
            date_exact_day_rate=_rate(self.n_date_day, dated),
            date_wide_span_rate=_rate(self.n_date_wide, dated),
            date_alternative_rate=_rate(self.n_date_alt, self.n_hgv),
            place_linkable_rate=_rate(self.n_place_tm, self.n_hgv),
            place_pleiades_rate=_rate(self.n_place_pleiades, self.n_hgv),
            markup_presence={k: _rate(v, n) for k, v in self.markup.items()},
            numeral_presence_rate=_rate(self.n_with_numerals, n),
            n_chars_edited=self.n_chars,
            n_numerals=self.n_numerals,
            n_lines=self.n_lines,
            median_chars_edited=float(pd.Series(self._char_counts).median()),
            genres=genres,
        )


def _loads_list(raw: Any) -> list[str]:
    """Parse a JSON-list column value, tolerating nulls."""
    if not raw:
        return []
    parsed = json.loads(raw)
    return list(parsed) if isinstance(parsed, list) else []


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def compute_stats(batches: Iterable[pd.DataFrame]) -> CorpusStats:
    """Accumulate corpus statistics over an iterable of record batches."""
    acc = _Accumulator()
    for df in batches:
        acc.update(df)
    return acc.finalize()


def iter_batches(parquet_path: Path, batch_size: int = 2000) -> Iterator[pd.DataFrame]:
    """Stream the corpus table as pandas frames, reading only needed columns."""
    parquet = pq.ParquetFile(parquet_path)
    for batch in parquet.iter_batches(batch_size=batch_size, columns=list(STATS_COLUMNS)):
        yield batch.to_pandas()


def corpus_stats(parquet_path: Path, batch_size: int = 2000) -> CorpusStats:
    """Compute whole-corpus statistics from the built parquet table."""
    if not parquet_path.is_file():
        msg = f"corpus table not found at {parquet_path}. Run `oik ingest build` first."
        raise FileNotFoundError(msg)
    return compute_stats(iter_batches(parquet_path, batch_size=batch_size))
