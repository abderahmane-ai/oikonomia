"""``build_dapt_shards`` stage: corpus + splits → packed token shards.

Produces one shard per split so the training job can language-model the train
split and still report held-out perplexity on dev without ever touching test.
Test is deliberately **not** packed: nothing in Phase 4 has any business
reading it, and the cheapest way to guarantee that is not to produce the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from oikonomia.config import Settings
from oikonomia.dapt.pack import encode_documents, load_tokenizer, pack_blocks, write_shard
from oikonomia.dapt.text import dapt_shard_dir, iter_dapt_texts
from oikonomia.logging import get_logger
from oikonomia.pipeline.manifest import upstream_key
from oikonomia.pipeline.stage import StageContext

logger = get_logger(__name__)

# Test is absent by design — see the module docstring.
PACKED_SPLITS = ("train", "dev")


class BuildDaptShardsStage:
    """Tokenise and pack the DAPT corpus, offline and reproducibly."""

    name = "build_dapt_shards"
    # 3: preserve case. GreBerta distinguishes it, keeping it is *cheaper* in
    #    tokens, and it is the strongest PERSON/PLACE cue in the corpus.
    # 2: frame each block as <s> ... </s>. A raw packed stream is
    #    off-distribution for RoBERTa at position 0 and silently costs adaptation
    #    quality without showing up in the loss.
    version = "3"

    def inputs_key(self, s: Settings) -> str:
        # Shards are packed from the corpus table filtered by the split table,
        # so both upstream artifacts are inputs. See `upstream_key` for why the
        # corpus rev is not a sufficient fingerprint.
        return upstream_key(s.paths.manifests, "build_corpus", "build_splits")

    def params(self, s: Settings) -> dict[str, Any]:
        cfg = s.dapt
        return {
            "model_name": cfg.model_name,
            "seq_len": cfg.seq_len,
            "regime": cfg.regime,
            "min_chars": cfg.min_chars,
            "lowercase": cfg.lowercase,
        }

    def outputs(self, s: Settings) -> list[Path]:
        out = dapt_shard_dir(s.paths.processed)
        return [out / f"{split}.bin" for split in PACKED_SPLITS]

    def run(self, ctx: StageContext) -> dict[str, float | int | str]:
        s = ctx.settings
        s.paths.ensure_writable()
        cfg = s.dapt

        tokenizer = load_tokenizer(cfg.model_name)
        sep_id = tokenizer.sep_token_id
        if sep_id is None:
            sep_id = tokenizer.eos_token_id
        if sep_id is None:
            msg = f"tokenizer {cfg.model_name!r} defines neither sep nor eos token"
            raise ValueError(msg)

        out_dir = dapt_shard_dir(s.paths.processed)
        stats: dict[str, float | int | str] = {}
        for split in PACKED_SPLITS:
            texts = iter_dapt_texts(
                s,
                regime=cfg.regime,
                split=split,
                min_chars=cfg.min_chars,
                lowercase=cfg.lowercase,
            )
            blocks = pack_blocks(
                encode_documents(texts, tokenizer, sep_id),
                cfg.seq_len,
                bos_id=tokenizer.bos_token_id,
                eos_id=tokenizer.eos_token_id,
            )
            meta = write_shard(
                blocks,
                out_dir / f"{split}.bin",
                seq_len=cfg.seq_len,
                vocab_size=len(tokenizer),
                meta={
                    "split": split,
                    "regime": cfg.regime,
                    "model_name": cfg.model_name,
                    "corpus_rev": s.ingest.idp_git_rev,
                    "lowercased": cfg.lowercase,
                },
            )
            stats[f"{split}_blocks"] = meta["n_blocks"]
            stats[f"{split}_tokens"] = meta["n_tokens"]

        return stats
