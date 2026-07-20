"""The text stream fed to domain-adaptive pretraining.

Two things here are load-bearing and easy to get quietly wrong.

**Train split only.** DAPT is unsupervised, so nothing stops it reading the
whole corpus — and nothing would complain if it did. But a model that has
language-modelled the test set has memorised the text it will later be scored
on, and every downstream number becomes meaningless. Phase 3 exists to prevent
exactly this, so the split filter is mandatory here, not optional: the loader
refuses to run without a split table.

**Case is preserved by default — and an earlier version of this module was
wrong about that.** It lowercased everything, on the reasoning that GreBerta's
vocabulary holds no uppercase Greek and capitals would therefore shatter into
byte fallback. That was inferred from reading the vocabulary file rather than
from tokenising anything, and testing it shows the opposite:

* ``Ἡλιοδώρου`` → ``[2213, 513, 50508]`` vs ``ἡλιοδώρου`` → ``[1342, 513,
  50508]``: distinct, and it decodes back to ``Ἡλιοδώρου`` with the capital.
* ``Γεώργιος`` and ``γεωργός`` tokenise to entirely different ids — the very
  name/occupation distinction the lexicon had to handle by exclusion.
* Keeping case costs **-0.59%** tokens over the corpus. It is *cheaper*.

So lowercasing threw away the strongest available cue for PERSON and PLACE, in
exchange for nothing. ByteLevel BPE composes capitals out of byte pieces
perfectly well; an absent uppercase *merge* is not an absent uppercase
*representation*.

``lowercase`` remains available because it is genuinely model-dependent: GreTa
folds case inside its own tokenizer normalizer (``{"type": "Lowercase"}``), so
for that backbone the flag changes nothing and the signal is unavailable no
matter what we feed. That is a property of GreTa, not of Ancient Greek models
in general.

Accents are kept in both cases. This is a lighter transform than
:func:`oikonomia.labeling.normalize.normalize`, which strips accents for
lexicon matching and would push text away from what the model was trained on.
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


def prepare_for_lm(text: str, *, lowercase: bool = False) -> str:
    """Whitespace-normalise for the language model; keep case unless asked.

    Deliberately *not* :func:`oikonomia.labeling.normalize.normalize`: that
    strips accents and folds final sigma, which is right for matching a lexicon
    and wrong for feeding a model trained on accented text.
    """
    cleaned = " ".join(text.split())
    return cleaned.lower() if lowercase else cleaned


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
    lowercase: bool = False,
) -> Iterator[str]:
    """Yield training text for one split, case preserved unless asked.

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
            cleaned = prepare_for_lm(str(text), lowercase=lowercase)
            if len(cleaned) < min_chars:
                skipped += 1
                continue
            kept += 1
            yield cleaned
    logger.info(f"dapt: yielded {kept} documents, skipped {skipped} short ones")


def dapt_shard_dir(processed_root: Path) -> Path:
    return processed_root / "dapt"
