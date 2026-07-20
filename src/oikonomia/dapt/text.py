"""The text stream fed to domain-adaptive pretraining.

Two things here are load-bearing and easy to get quietly wrong.

**Train split only.** DAPT is unsupervised, so nothing stops it reading the
whole corpus — and nothing would complain if it did. But a model that has
language-modelled the test set has memorised the text it will later be scored
on, and every downstream number becomes meaningless. Phase 3 exists to prevent
exactly this, so the split filter is mandatory here, not optional: the loader
refuses to run without a split table.

**Case is folded, deliberately.** GreBerta's tokenizer is a ByteLevel BPE whose
merges are entirely lowercase — verified against its ``tokenizer.json``, whose
vocabulary contains no uppercase Greek. Uppercase input is therefore
*representable* (byte fallback) but out of distribution: a capitalised proper
name shatters into single-byte tokens. Since ~16% of corpus tokens are
capitalised, feeding raw text would fragment precisely the proper names we
care most about.

So the language model sees lowercase, matching what it was pretrained on. The
capitalisation signal is not discarded — it is carried separately as an
explicit feature for the Phase 7 tagger (ablation arm B2), where it can be
used properly instead of being mangled into byte soup.

Accents are **kept**. GreBerta's vocabulary contains accented lowercase forms,
so folding them away would push the text out of distribution in the other
direction. This is a lighter fold than
:func:`oikonomia.labeling.normalize.normalize`, which is for lexicon matching,
not for feeding a language model.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from oikonomia.config import Settings
from oikonomia.corpus.io import corpus_path, iter_batches
from oikonomia.logging import get_logger
from oikonomia.splits.build import OUTPUT_NAME as SPLITS_NAME

logger = get_logger(__name__)

TEXT_COLUMNS = ("stem", "edited_text")
VALID_REGIMES = ("split_random", "split_chronological")


def fold_for_lm(text: str) -> str:
    """Lowercase for the language model, keeping accents.

    Deliberately *not* :func:`oikonomia.labeling.normalize.normalize`: that
    strips accents and folds final sigma, which is right for matching a lexicon
    and wrong for feeding a model whose vocabulary contains accented forms.
    """
    return text.lower()


def load_split_ids(settings: Settings, regime: str, split: str) -> set[str]:
    """Document ids belonging to one split under one regime."""
    if regime not in VALID_REGIMES:
        msg = f"regime must be one of {VALID_REGIMES}, got {regime!r}"
        raise ValueError(msg)

    path = settings.paths.processed / SPLITS_NAME
    if not path.is_file():
        msg = (
            f"split table not found at {path}. DAPT must not read the whole "
            "corpus — run `oik splits build` first."
        )
        raise FileNotFoundError(msg)

    table = pd.read_parquet(path, columns=["doc_id", regime])
    ids = set(table.loc[table[regime] == split, "doc_id"].astype(str))
    if not ids:
        msg = f"no documents in split {split!r} under regime {regime!r}"
        raise ValueError(msg)
    return ids


def iter_dapt_texts(
    settings: Settings,
    *,
    regime: str = "split_random",
    split: str = "train",
    min_chars: int = 20,
) -> Iterator[str]:
    """Yield lowercased training text for one split.

    ``min_chars`` drops fragments too short to carry any language signal; they
    are mostly single-word scraps that would only add separator noise to the
    packed stream.
    """
    allowed = load_split_ids(settings, regime, split)
    logger.info(f"dapt: {len(allowed)} documents in {regime}={split}")

    kept = skipped = 0
    for df in iter_batches(corpus_path(settings.paths.processed), TEXT_COLUMNS):
        for stem, text in zip(df["stem"], df["edited_text"], strict=True):
            if str(stem) not in allowed:
                continue
            cleaned = " ".join(str(text).split())
            if len(cleaned) < min_chars:
                skipped += 1
                continue
            kept += 1
            yield fold_for_lm(cleaned)
    logger.info(f"dapt: yielded {kept} documents, skipped {skipped} short ones")


def dapt_shard_dir(processed_root: Path) -> Path:
    return processed_root / "dapt"
