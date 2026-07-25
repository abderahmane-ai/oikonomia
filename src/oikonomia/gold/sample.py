"""Select and export the documents to be annotated by hand.

Gold annotation is the project's scarcest resource — every span is a human
minute — so *which* documents get annotated determines what the models can
learn and what the evaluation can honestly claim. Four rules govern the choice.

**1. Train split only.** Annotating a dev or test document contaminates the set
it belongs to, permanently and invisibly. The sampler refuses any other split.

**2. One document per group.** Phase 3 found 399 near-duplicate clusters and
618 documents sharing a TM id. Annotating two members of the same group
spends the budget twice on the same text and, worse, inflates agreement.

**3. Stratify by genre, spread over time.** The corpus is 25% receipts; a
proportional sample would spend the whole budget on them and the model would
never see a lease. Strata are capped so no genre dominates, and within a genre
documents are spread across date buckets rather than clustered in the 2nd
century where the mass is.

**4. Keep some prose.** Economic documents are numeral-dense, but sampling only
those teaches PERSON and PLACE nothing about how they appear in letters and
petitions. A fixed share of the sample is deliberately low-numeral.

Length is bounded on both sides: below ~120 characters a document carries too
little to annotate, and above ~1,600 a single document eats an hour and
skews the budget.
"""

from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from oikonomia.config import Settings
from oikonomia.corpus.io import corpus_path, iter_batches
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.weak_rules import label_document
from oikonomia.logging import get_logger
from oikonomia.schemas.spans import CharSpan
from oikonomia.splits.build import OUTPUT_NAME as SPLITS_NAME

logger = get_logger(__name__)

SAMPLE_COLUMNS = ("stem", "edited_text", "document_json", "n_numerals")
OUTPUT_NAME = "to_annotate.jsonl"

MIN_CHARS = 120
MAX_CHARS = 1600

# The corpus is not uniformly Greek: idp.data carries Latin documents and a few
# bilingual ones. A Latin ostracon is a valid papyrus and a useless annotation
# target for a Greek extraction model, so it is filtered rather than shipped to
# an annotator who would have to skip it.
MIN_GREEK_RATIO = 0.9

# Share of characters that are the lacuna placeholder. Median damage in the
# corpus is 4.8%, but past ~10% a document is more gap than text and annotating
# it costs full attention for a handful of spans.
MAX_GAP_RATIO = 0.10
GAP_CHAR = "…"

# Genres worth spending the budget on, most economically informative first.
# "other" collects everything else, including documents with no genre at all.
TARGET_GENRES = (
    "receipt",
    "account",
    "list",
    "lease",
    "contract",
    "loan",
    "sale",
    "petition",
    "letter_private",
    "order",
    "register",
    "other",
)

# Share of the sample deliberately drawn from low-numeral documents, so PERSON
# and PLACE are seen in prose and not only in accounting lines.
PROSE_SHARE = 0.20
PROSE_MAX_NUMERALS = 2


class AnnotationDoc(BaseModel):
    """One document as handed to the annotator."""

    doc_id: str
    text: str
    meta: dict[str, Any]
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    suggested_entities: list[dict[str, Any]] | None = None
    double_annotate: bool = False


def _bucket(genre: str) -> str:
    return genre if genre in TARGET_GENRES else "other"


def greek_ratio(text: str) -> float:
    """Share of alphabetic characters that are Greek."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if "GREEK" in unicodedata.name(c, "")) / len(letters)


def gap_ratio(text: str) -> float:
    """Share of characters that are the lacuna placeholder."""
    return text.count(GAP_CHAR) / len(text) if text else 0.0


def is_annotatable(text: str) -> bool:
    """Whether a document is worth an annotator's time."""
    return (
        MIN_CHARS <= len(text) <= MAX_CHARS
        and greek_ratio(text) >= MIN_GREEK_RATIO
        and gap_ratio(text) <= MAX_GAP_RATIO
    )


def select(
    rows: list[dict[str, Any]],
    *,
    n: int,
    seed: int,
    prose_share: float = PROSE_SHARE,
) -> list[dict[str, Any]]:
    """Choose ``n`` documents, capped per genre and spread over date buckets.

    ``rows`` must already be filtered to the train split, deduplicated by group
    and bounded by length — this function only decides the mix.
    """
    rng = random.Random(seed)

    prose_target = int(n * prose_share)
    dense = [r for r in rows if r["n_numerals"] > PROSE_MAX_NUMERALS]
    prose = [r for r in rows if r["n_numerals"] <= PROSE_MAX_NUMERALS]

    def spread(pool: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
        """Round-robin over genres, and within a genre over date buckets."""
        by_genre: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for r in pool:
            by_genre.setdefault(_bucket(r["genre"]), {}).setdefault(
                r["date_bucket"], []
            ).append(r)
        # Sorted iteration, not dict order. Sorting each list is not enough on
        # its own: `rng` is a single stream, so if the *order in which lists are
        # shuffled* depends on dict insertion order — which follows the order
        # rows arrived from parquet — each list draws different randomness and
        # the sample silently stops being reproducible.
        for genre in sorted(by_genre):
            for bucket in sorted(by_genre[genre]):
                by_genre[genre][bucket].sort(key=lambda r: r["doc_id"])
                rng.shuffle(by_genre[genre][bucket])

        picked: list[dict[str, Any]] = []
        genres = sorted(by_genre)
        while len(picked) < quota and genres:
            for genre in list(genres):
                buckets = [b for b in sorted(by_genre[genre]) if by_genre[genre][b]]
                if not buckets:
                    genres.remove(genre)
                    continue
                # Rotate date buckets so a genre's picks are not all one era.
                bucket = buckets[len(picked) % len(buckets)]
                picked.append(by_genre[genre][bucket].pop())
                if len(picked) >= quota:
                    break
        return picked

    chosen = spread(prose, prose_target) + spread(dense, n - prose_target)
    chosen.sort(key=lambda r: r["doc_id"])
    return chosen[:n]


def build_sample(
    settings: Settings,
    *,
    n: int = 150,
    seed: int = 17,
    iaa_n: int = 30,
    blind_n: int = 30,
    suggest: bool = True,
    matcher: Matcher | None = None,
) -> list[AnnotationDoc]:
    """Assemble the annotation batch.

    ``iaa_n`` documents are flagged for double annotation (agreement).
    ``blind_n`` documents carry **no** baseline suggestions: pre-annotation
    speeds work but anchors the annotator to the baseline's decisions, which
    would inflate any later baseline-vs-gold comparison. The blind subset is
    the only honest ground for that comparison.
    """
    splits_path = settings.paths.processed / SPLITS_NAME
    if not splits_path.is_file():
        msg = (
            f"split table not found at {splits_path}. Gold must be drawn from "
            "the train split only — run `oik splits build` first."
        )
        raise FileNotFoundError(msg)

    splits = pd.read_parquet(
        splits_path,
        columns=["doc_id", "split_random", "genre", "date_bucket", "date_mid", "group_id"],
    )
    train = splits[splits.split_random == "train"]
    # Rule 2: one document per group, so near-duplicates cannot both be drawn.
    train = train.sort_values("doc_id").drop_duplicates(subset="group_id", keep="first")
    meta_by_id = {str(r.doc_id): r for r in train.itertuples(index=False)}
    logger.info(f"gold: {len(meta_by_id)} candidate documents (train split, one per group)")

    rows: list[dict[str, Any]] = []
    for df in iter_batches(corpus_path(settings.paths.processed), SAMPLE_COLUMNS):
        for row in df.itertuples(index=False):
            doc_id = str(row.stem)
            meta = meta_by_id.get(doc_id)
            if meta is None:
                continue
            # Used verbatim. The parser already emits canonical whitespace, and
            # re-collapsing it here would shift every character offset — the
            # annotator's spans would then no longer index the same string as
            # the stored `edited_text`, `OffsetMap`, markup and numeral spans.
            text = str(row.edited_text)
            if not is_annotatable(text):
                continue
            rows.append(
                {
                    "doc_id": doc_id,
                    "text": text,
                    "document_json": row.document_json,
                    "n_numerals": int(row.n_numerals),
                    "genre": str(meta.genre),
                    "date_bucket": str(meta.date_bucket),
                    "date_mid": None if pd.isna(meta.date_mid) else float(meta.date_mid),
                }
            )
    logger.info(f"gold: {len(rows)} pass the length filter")

    chosen = select(rows, n=n, seed=seed)
    rng = random.Random(seed + 1)
    order = sorted(r["doc_id"] for r in chosen)
    rng.shuffle(order)
    iaa_ids, blind_ids = set(order[:iaa_n]), set(order[iaa_n : iaa_n + blind_n])

    docs: list[AnnotationDoc] = []
    for r in chosen:
        suggested = None
        if suggest and matcher is not None and r["doc_id"] not in blind_ids:
            parsed = json.loads(r["document_json"])
            # Suggestions are computed on the *whitespace-collapsed* text the
            # annotator sees, so offsets line up with their tool exactly.
            result = label_document(
                r["text"],
                [],  # numerals are re-found by the matcher on the collapsed text
                [CharSpan(start=0, end=len(r["text"]))],
                matcher,
            )
            del parsed
            suggested = [
                {"start": e.span.start, "end": e.span.end, "label": e.label, "text": e.text}
                for e in result.entities
            ]
        docs.append(
            AnnotationDoc(
                doc_id=r["doc_id"],
                text=r["text"],
                meta={
                    "genre": r["genre"],
                    "date_bucket": r["date_bucket"],
                    "date_mid": r["date_mid"],
                    "n_chars": len(r["text"]),
                    "split": "train",
                    "regime": "split_random",
                    "corpus_rev": settings.ingest.idp_git_rev,
                },
                suggested_entities=suggested,
                double_annotate=r["doc_id"] in iaa_ids,
            )
        )
    return docs


def write_jsonl(docs: list[AnnotationDoc], path: Path) -> None:
    """Write the batch, temp-then-rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for doc in docs:
            fh.write(json.dumps(doc.model_dump(), ensure_ascii=False) + "\n")
    tmp.replace(path)
    logger.info(f"gold: wrote {len(docs)} documents to {path}")
