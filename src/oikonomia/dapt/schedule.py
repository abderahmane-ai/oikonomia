"""Derive the training schedule from the actual shard size.

A step count copied from a paper is a trap. "Don't Stop Pretraining" runs DAPT
for ~12,500 steps, but its domain corpora are orders of magnitude larger than
this one. Our packed train shard is ~16,200 blocks — 8.3M tokens — so at batch
32 x accum 2 that same 12,500 steps is **49 epochs** over the same handful of
papyri. The job would look healthy the whole way and simply memorise the
training split.

So the schedule is computed from the shard, not asserted. Change the epoch
budget, or the batch size, and the step count follows.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from oikonomia.dapt.pack import META_SUFFIX


class Schedule(BaseModel):
    """A training schedule, with the arithmetic exposed for inspection."""

    n_blocks: int
    seq_len: int
    blocks_per_step: int
    steps_per_epoch: int
    epochs: float
    max_steps: int
    tokens_per_step: int
    total_tokens_seen: int
    corpus_tokens: int

    @property
    def effective_epochs(self) -> float:
        return round(self.max_steps / self.steps_per_epoch, 2) if self.steps_per_epoch else 0.0


def steps_for_epochs(
    n_blocks: int, batch_size: int, grad_accum: int, epochs: float
) -> int:
    """Optimizer steps needed to see the shard ``epochs`` times."""
    blocks_per_step = batch_size * grad_accum
    if blocks_per_step <= 0:
        msg = "batch_size and grad_accum must both be positive"
        raise ValueError(msg)
    steps_per_epoch = max(1, n_blocks // blocks_per_step)
    return max(1, round(steps_per_epoch * epochs))


def plan(
    shard: Path, *, batch_size: int, grad_accum: int, epochs: float, max_steps: int | None = None
) -> Schedule:
    """Build the schedule for a packed shard, reading its metadata sidecar."""
    meta = json.loads(shard.with_suffix(META_SUFFIX).read_text(encoding="utf-8"))
    n_blocks, seq_len = meta["n_blocks"], meta["seq_len"]

    blocks_per_step = batch_size * grad_accum
    steps_per_epoch = max(1, n_blocks // blocks_per_step)
    resolved = max_steps or steps_for_epochs(n_blocks, batch_size, grad_accum, epochs)

    return Schedule(
        n_blocks=n_blocks,
        seq_len=seq_len,
        blocks_per_step=blocks_per_step,
        steps_per_epoch=steps_per_epoch,
        epochs=epochs,
        max_steps=resolved,
        tokens_per_step=blocks_per_step * seq_len,
        total_tokens_seen=resolved * blocks_per_step * seq_len,
        corpus_tokens=n_blocks * seq_len,
    )
