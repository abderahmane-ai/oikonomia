"""Modal job: domain-adaptive pretraining of GreBerta on documentary papyri.

This module is orchestration only. Every decision about *what* data the model
sees was made offline in ``oikonomia.dapt`` and frozen into the packed shards;
here we upload those shards and run the training loop. Deleting this directory
must not break the library.

Run:
    modal run modal_app/dapt.py::upload_shards     # once, ~1 min
    modal run modal_app/dapt.py::train

Why full fine-tuning and not LoRA: LoRA's advantage is preserving the source
domain, and literary Classical Greek performance is not a deliverable here. We
want the weights to move. GreBerta is 0.1B parameters, so full fine-tuning fits
an A10 (24 GB) with room to spare.

Preemption: A10 capacity is reclaimable. Checkpoints go to a Volume, the
function declares retries, and training resumes from the last checkpoint, so a
reclaimed container costs minutes rather than the run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import modal

APP_NAME = "oikonomia-dapt"
# gpu="A10" — verified against modal.com/docs. "A10G" is no longer in the
# documented GPU list (T4, L4, A10, L40S, A100, H100, H200, B200, B300).
GPU = "A10"
VOLUME_NAME = "oikonomia-dapt"
VOL_ROOT = "/vol"
SHARD_DIR = f"{VOL_ROOT}/shards"
CKPT_DIR = f"{VOL_ROOT}/checkpoints"

LOCAL_SHARDS = Path(__file__).resolve().parents[1] / "data" / "processed" / "dapt"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch>=2.2",
        # Pinned to the major version whose Trainer API was verified against:
        # `evaluation_strategy` was removed in 5.x in favour of `eval_strategy`,
        # so a silent major bump would break the run on the GPU, not locally.
        "transformers>=5.0,<6",
        "accelerate>=0.33",
        "numpy>=1.26",
    )
    # Local source is added explicitly: automounting was removed in Modal >=1.0.
    .add_local_python_source("oikonomia")
)

app = modal.App(APP_NAME, image=image)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)


@app.function(volumes={VOL_ROOT: volume}, timeout=3600)
def upload_shards(shards: dict[str, bytes], metas: dict[str, str]) -> dict[str, int]:
    """Write packed shards into the Volume. Called with local file contents."""
    out = Path(SHARD_DIR)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, blob in shards.items():
        (out / name).write_bytes(blob)
        written[name] = len(blob)
    for name, text in metas.items():
        (out / name).write_text(text, encoding="utf-8")
    volume.commit()
    return written


@app.local_entrypoint()
def push() -> None:
    """Send the locally built shards to the Volume."""
    if not LOCAL_SHARDS.is_dir():
        msg = f"no shards at {LOCAL_SHARDS}. Run `oik dapt prepare` first."
        raise SystemExit(msg)
    shards = {p.name: p.read_bytes() for p in sorted(LOCAL_SHARDS.glob("*.bin"))}
    metas = {p.name: p.read_text(encoding="utf-8") for p in sorted(LOCAL_SHARDS.glob("*.json"))}
    if not shards:
        raise SystemExit(f"no .bin shards found in {LOCAL_SHARDS}")
    written = upload_shards.remote(shards, metas)
    for name, size in written.items():
        print(f"uploaded {name}: {size / 1e6:.1f} MB")


@app.local_entrypoint()
def launch(epochs: float = 8.0, max_steps: int = 0) -> None:
    """Compute the schedule from the packed shard, then start training.

    The step count is derived rather than passed by hand: 12,500 steps is the
    published DAPT setting, but on this corpus's 8.3M tokens that is ~49
    epochs. The job would look healthy and quietly memorise the train split.
    """
    from oikonomia.dapt.schedule import plan

    schedule = plan(
        LOCAL_SHARDS / "train.bin",
        batch_size=32,
        grad_accum=2,
        epochs=epochs,
        max_steps=max_steps or None,
    )
    print(
        f"corpus {schedule.corpus_tokens / 1e6:.1f}M tokens | "
        f"{schedule.steps_per_epoch} steps/epoch | "
        f"max_steps={schedule.max_steps} ({schedule.effective_epochs} epochs)"
    )
    result = train.remote(max_steps=schedule.max_steps)
    print(result)


@app.function(
    gpu=GPU,
    volumes={VOL_ROOT: volume},
    timeout=24 * 3600,
    # A10 capacity is preemptible; retry and resume rather than lose the run.
    retries=modal.Retries(max_retries=3, initial_delay=10.0),
)
def train(
    model_name: str = "bowphs/GreBerta",
    max_steps: int = 2024,  # ~8 epochs of the current shard; see schedule.py
    learning_rate: float = 5e-5,
    per_device_batch_size: int = 32,
    grad_accum: int = 2,
    warmup_ratio: float = 0.06,
    mlm_probability: float = 0.15,
    seed: int = 17,
) -> dict[str, float]:
    """Continue masked-language-model pretraining on the packed papyri shards."""
    import numpy as np
    import torch
    from torch.utils.data import Dataset
    from transformers import (
        AutoModelForMaskedLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    class PackedShard(Dataset):
        """Fixed-length blocks, memory-mapped straight off the Volume.

        No tokenisation, no padding, no collation cost beyond masking: the
        shards were built to be consumed exactly as they lie on disk.
        """

        def __init__(self, path: Path) -> None:
            meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            self.n = meta["n_blocks"]
            self.seq_len = meta["seq_len"]
            self.data = np.memmap(
                path, dtype=np.uint16, mode="r", shape=(self.n, self.seq_len)
            )

        def __len__(self) -> int:
            return self.n

        def __getitem__(self, i: int) -> dict[str, torch.Tensor]:
            # int64 cast is required by the embedding lookup; uint16 on disk is
            # purely a storage decision.
            block = torch.from_numpy(self.data[i].astype(np.int64))
            return {"input_ids": block, "attention_mask": torch.ones_like(block)}

    torch.manual_seed(seed)
    shard_dir = Path(SHARD_DIR)
    train_ds = PackedShard(shard_dir / "train.bin")
    eval_ds = PackedShard(shard_dir / "dev.bin")
    print(f"train blocks={len(train_ds)}  dev blocks={len(eval_ds)}  seq_len={train_ds.seq_len}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForMaskedLM.from_pretrained(model_name)

    args = TrainingArguments(
        # output_dir lives inside the Volume, so HF checkpointing is what makes
        # the job preemption-safe; background commits persist it automatically.
        output_dir=CKPT_DIR,
        max_steps=max_steps,
        per_device_train_batch_size=per_device_batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        lr_scheduler_type="linear",
        bf16=True,
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=500,
        save_steps=500,
        save_total_limit=3,
        report_to=[],
        seed=seed,
        dataloader_num_workers=2,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=DataCollatorForLanguageModeling(
            tokenizer=tokenizer, mlm=True, mlm_probability=mlm_probability
        ),
    )

    resume = os.path.isdir(CKPT_DIR) and any(
        p.startswith("checkpoint-") for p in os.listdir(CKPT_DIR)
    )
    trainer.train(resume_from_checkpoint=resume or None)

    metrics = trainer.evaluate()
    final = f"{CKPT_DIR}/final"
    trainer.save_model(final)
    tokenizer.save_pretrained(final)
    volume.commit()

    loss = float(metrics.get("eval_loss", float("nan")))
    print(f"dev loss={loss:.4f}  perplexity={float(np.exp(loss)):.2f}")
    return {"eval_loss": loss, "perplexity": float(np.exp(loss))}
