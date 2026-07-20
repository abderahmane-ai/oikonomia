"""Tokenise and pack the DAPT stream into memory-mapped fixed-length blocks.

Done offline, on a laptop, so that the GPU never waits on CPU tokenisation.
The A10 costs money per hour; tokenising 37M characters inside the training
loop would leave it idle for a large fraction of that.

**Packing, not padding.** Documents are concatenated into one token stream with
a separator between them and then cut into equal ``seq_len`` blocks. Papyri are
short — median 267 characters — so a padded batch would be mostly ``<pad>``,
and the GPU would spend most of its FLOPs on nothing. Packed blocks are 100%
real tokens.

The cost of packing is that a block can span a document boundary, so the model
occasionally attends across two unrelated papyri. For masked language
modelling that is a well-accepted trade: the separator token marks the seam,
and the alternative wastes most of the compute budget.

**uint16 is exact here, not a gamble.** GreBerta's vocabulary is 52,000 < 65,536,
so every token id fits. That halves the shard on disk and in page cache versus
uint32. The writer checks the vocabulary size and refuses rather than
silently wrapping if a tokenizer ever exceeds it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from oikonomia.logging import get_logger

logger = get_logger(__name__)

UINT16_MAX = 65535
SHARD_SUFFIX = ".bin"
META_SUFFIX = ".json"


class TokenizerLike(Protocol):
    """The slice of a HF tokenizer this module needs.

    Typed structurally so the packing logic can be tested with a trivial fake,
    without importing ``transformers`` or downloading a model.
    """

    def __call__(self, text: str, **kwargs: Any) -> Any: ...


def load_tokenizer(model_name: str) -> Any:
    """Load a HF tokenizer, importing ``transformers`` lazily.

    The library must stay importable on a laptop with no ML stack, so the
    dependency is resolved at call time and reported with an actionable message
    rather than an ImportError from three frames down.
    """
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        msg = (
            "transformers is required to tokenise DAPT shards. "
            'Install the training extra: uv pip install -e ".[train]"'
        )
        raise ImportError(msg) from exc
    return AutoTokenizer.from_pretrained(model_name)


def encode_documents(
    texts: Iterable[str], tokenizer: TokenizerLike, sep_id: int
) -> Iterator[list[int]]:
    """Encode each document and append the separator that marks its end."""
    for text in texts:
        ids = tokenizer(text, add_special_tokens=False)["input_ids"]
        if ids:
            yield [*ids, sep_id]


def pack_blocks(
    token_lists: Iterable[list[int]],
    seq_len: int,
    *,
    bos_id: int | None = None,
    eos_id: int | None = None,
) -> Iterator[list[int]]:
    """Concatenate token lists and cut them into exact ``seq_len`` blocks.

    When ``bos_id``/``eos_id`` are given, each emitted block is framed as
    ``<s> … </s>`` and carries ``seq_len - 2`` content tokens. **This framing
    is not cosmetic.** RoBERTa is pretrained exclusively on sequences that open
    with ``<s>`` and close with ``</s>``; position 0 has never held anything
    else. Feeding raw packed streams puts every training example off
    distribution at exactly the position the model is most confident about, and
    nothing in the loss would report it — the run simply learns a little less.

    The trailing partial block is dropped. It is at most ``seq_len`` tokens out
    of millions, and keeping it would mean either padding (which packing exists
    to avoid) or a ragged array (which cannot be memory-mapped as a
    fixed-shape matrix).
    """
    if seq_len < 2:
        msg = f"seq_len must be at least 2, got {seq_len}"
        raise ValueError(msg)

    frame: tuple[int, int] | None = (
        (bos_id, eos_id) if bos_id is not None and eos_id is not None else None
    )
    content_len = seq_len - 2 if frame else seq_len
    if content_len < 1:
        msg = f"seq_len {seq_len} too small to hold framing tokens"
        raise ValueError(msg)

    buffer: list[int] = []
    for ids in token_lists:
        buffer.extend(ids)
        while len(buffer) >= content_len:
            chunk = buffer[:content_len]
            del buffer[:content_len]
            yield [frame[0], *chunk, frame[1]] if frame else chunk


def write_shard(
    blocks: Iterable[list[int]],
    path: Path,
    *,
    seq_len: int,
    vocab_size: int,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Write packed blocks to a flat uint16 file plus a JSON sidecar.

    Written temp-then-rename, and the metadata last, so an interrupted run
    never leaves a shard that looks complete.
    """
    if vocab_size > UINT16_MAX:
        msg = (
            f"vocabulary of {vocab_size} exceeds uint16 ({UINT16_MAX}); "
            "widen the shard dtype before using this tokenizer"
        )
        raise ValueError(msg)

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    n_blocks = 0
    with tmp.open("wb") as fh:
        for block in blocks:
            np.asarray(block, dtype=np.uint16).tofile(fh)
            n_blocks += 1
    tmp.replace(path)

    full_meta = {
        **meta,
        "n_blocks": n_blocks,
        "seq_len": seq_len,
        "n_tokens": n_blocks * seq_len,
        "dtype": "uint16",
        "vocab_size": vocab_size,
        "shard": path.name,
    }
    meta_path = path.with_suffix(META_SUFFIX)
    meta_tmp = meta_path.with_suffix(META_SUFFIX + ".tmp")
    meta_tmp.write_text(json.dumps(full_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_tmp.replace(meta_path)

    logger.info(f"dapt: wrote {n_blocks} blocks x {seq_len} tokens to {path}")
    return full_meta


def read_shard(path: Path) -> np.ndarray:
    """Memory-map a shard as an ``(n_blocks, seq_len)`` uint16 matrix."""
    meta = json.loads(path.with_suffix(META_SUFFIX).read_text(encoding="utf-8"))
    return np.memmap(
        path, dtype=np.uint16, mode="r", shape=(meta["n_blocks"], meta["seq_len"])
    )
