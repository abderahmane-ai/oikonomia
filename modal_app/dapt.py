"""Domain-adaptive pretraining of GreBerta on documentary papyri (Modal, A10).

Two arms, each trained to its own best and compared on held-out MLM loss:

    full : full fine-tuning            LR 5e-5   — every weight moves.
    dora : DoRA, r=64, all-linear      LR 1e-4   — the strongest PEFT baseline.

Why exactly these two, and not a LoRA-scope sweep:

* GreBerta is **RoBERTa-base, ~125M params** (config.json: 12L / 768d / 12h /
  52k vocab / 512 ctx). At that size PEFT buys **no** memory — full FT fits an
  A10 with room to spare — so an adapter's only value here is *regularization*,
  never efficiency.
* DAPT is **continued pretraining**, i.e. injecting a new domain. For that
  regime the on-point evidence (Biderman et al. 2405.09673) is that full FT
  beats low-rank adapters and the gap does **not** close with rank; the
  "adapters equal full FT" results are all about the downstream *fine-tune*,
  a different stage. DoRA (2402.09353) is the adapter that comes closest to
  full-FT update geometry, so it is the one honest challenger — with rsLoRA
  scaling and all linear layers targeted, given full expressivity.
* **Each arm owns its learning rate.** A shared LR is what silently starved the
  adapters last run (5e-5 is right for full FT, ~10x too low for an adapter).

The final backbone is chosen **downstream on gold NER F1**, not on the
perplexity this file prints; here we only need each arm at its own optimum,
with early stopping on dev loss deciding the epoch count.

    modal run --detach modal_app/dapt.py::push       # upload shards, once
    modal run --detach modal_app/dapt.py::compare    # full vs dora, in parallel
    modal run --detach modal_app/dapt.py::launch --arm dora   # a single arm
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

APP_NAME = "oikonomia-dapt"
GPU = "A10"  # verified against modal.com/docs; "A10G" is no longer a valid name.
VOLUME_NAME = "oikonomia-dapt"
VOL_ROOT = "/vol"
SHARD_DIR = f"{VOL_ROOT}/shards"
CKPT_ROOT = f"{VOL_ROOT}/checkpoints"

LOCAL_SHARDS = Path(__file__).resolve().parents[1] / "data" / "processed" / "dapt"

# The two arms. Each is a full, self-contained recipe — same data, own optimizer
# settings. `compare` runs both; `launch --arm X` runs one.
ARMS: dict[str, dict[str, object]] = {
    "full": {"adapter": "full", "learning_rate": 5e-5},
    "dora": {"adapter": "dora", "learning_rate": 1e-4, "lora_r": 64, "lora_alpha": 16},
}

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch>=2.2",
        # 5.x renamed evaluation_strategy -> eval_strategy; pin the major so a
        # silent bump can't break the run on the GPU where it's expensive to find.
        "transformers>=5.0,<6",
        "accelerate>=0.33",
        "peft>=0.12",  # DoRA (use_dora) and rsLoRA (use_rslora) both need >=0.12.
        "numpy>=1.26",
    )
)
# No add_local_python_source: the remote functions read packed shards off the
# Volume and never import the `oikonomia` library, so nothing local ships. (That
# line also broke `modal run` from any interpreter without the package on path.)

app = modal.App(APP_NAME, image=image)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)


@app.function(volumes={VOL_ROOT: volume}, timeout=3600)
def upload_shards(shards: dict[str, bytes], metas: dict[str, str]) -> dict[str, int]:
    """Write packed shards into the Volume."""
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
    """Send locally built shards to the Volume."""
    if not LOCAL_SHARDS.is_dir():
        raise SystemExit(f"no shards at {LOCAL_SHARDS}. Run `oik dapt prepare` first.")
    shards = {p.name: p.read_bytes() for p in sorted(LOCAL_SHARDS.glob("*.bin"))}
    metas = {p.name: p.read_text(encoding="utf-8") for p in sorted(LOCAL_SHARDS.glob("*.json"))}
    if not shards:
        raise SystemExit(f"no .bin shards found in {LOCAL_SHARDS}")
    for name, size in upload_shards.remote(shards, metas).items():
        print(f"uploaded {name}: {size / 1e6:.1f} MB")


@app.function(volumes={VOL_ROOT: volume}, timeout=600)
def reset_checkpoints(names: list[str]) -> list[str]:
    """Delete each arm's checkpoint dir so a fresh comparison never resumes a
    previous run. Preemption resume is unaffected: Modal retries re-enter
    ``train`` (not this entrypoint), find the in-run checkpoints, and continue."""
    import shutil

    cleared = []
    for name in names:
        d = Path(f"{CKPT_ROOT}/{name}")
        if d.is_dir():
            shutil.rmtree(d)
            cleared.append(name)
    volume.commit()
    return cleared


@app.function(
    gpu=GPU,
    volumes={VOL_ROOT: volume},
    timeout=24 * 3600,
    retries=modal.Retries(max_retries=3, initial_delay=10.0),
)
def train(
    run_name: str,
    adapter: str = "full",  # "full" | "dora"
    learning_rate: float = 5e-5,
    model_name: str = "bowphs/GreBerta",
    lora_r: int = 64,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
    # A generous *ceiling* (~16 epochs); early stopping on dev loss decides the
    # real stopping point, so this number never has to be guessed correctly.
    max_steps: int = 4048,
    patience: int = 5,
    eval_every: int = 100,
    # Effective batch 64 (16 x 4). The MLM logits are batch*seq*52k floats; in
    # fp32 that transient alone is ~1.7 GB at bs=16, and a larger per-device
    # batch (plus full-FT activations) tips the A10 over its 22 GiB.
    per_device_batch_size: int = 16,
    grad_accum: int = 4,
    warmup_ratio: float = 0.06,
    mlm_probability: float = 0.15,
    seed: int = 17,
) -> dict[str, float | str]:
    """Continued MLM pretraining on the packed papyri shards. Returns dev metrics."""
    import math
    import os

    # Set before torch initializes its CUDA allocator: reduces fragmentation, the
    # difference between fitting and an edge-of-capacity OOM on the 22 GiB A10.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    import numpy as np
    import torch
    from torch.utils.data import Dataset
    from transformers import (
        AutoModelForMaskedLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        EarlyStoppingCallback,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )
    from transformers.trainer_callback import PrinterCallback, ProgressCallback

    class PackedShard(Dataset):
        """Fixed-length blocks, memory-mapped straight off the Volume."""

        def __init__(self, path: Path) -> None:
            meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            self.n = meta["n_blocks"]
            self.seq_len = meta["seq_len"]
            self.data = np.memmap(path, dtype=np.uint16, mode="r", shape=(self.n, self.seq_len))

        def __len__(self) -> int:
            return self.n

        def __getitem__(self, i: int) -> dict[str, torch.Tensor]:
            block = torch.from_numpy(self.data[i].astype(np.int64))
            return {"input_ids": block, "attention_mask": torch.ones_like(block)}

    class GapAwareCollator(DataCollatorForLanguageModeling):
        """MLM masking that never *targets* the lacuna marker "…".

        "…" is 6% of the token stream; masking it spends the budget predicting an
        editorial symbol that is trivial from its other half — near-zero loss and
        gradient, and it deflates the dev perplexity that model selection runs on.
        The markers stay in the input (they are real and appear at inference);
        they are only excluded from being prediction targets.
        """

        def __init__(self, *args, gap_ids: set[int] | None = None, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.gap_ids = gap_ids or set()

        def torch_mask_tokens(self, inputs, special_tokens_mask=None, offset_mapping=None):
            if self.gap_ids:
                is_gap = torch.zeros_like(inputs, dtype=torch.bool)
                for gid in self.gap_ids:
                    is_gap |= inputs == gid
                special_tokens_mask = (
                    is_gap if special_tokens_mask is None else special_tokens_mask.bool() | is_gap
                )
            return super().torch_mask_tokens(
                inputs, special_tokens_mask=special_tokens_mask, offset_mapping=offset_mapping
            )

    class ClearLogger(TrainerCallback):
        """One tagged line per event — the only thing that prints, so parallel
        arms sharing stdout stay one ``grep`` apart and eval lines carry ppl."""

        def on_log(self, args, state, control, logs=None, **kwargs):
            if not logs:
                return
            step = state.global_step
            if "loss" in logs:
                print(
                    f"[{run_name}] {step:>4}/{args.max_steps}  ep {logs.get('epoch', 0.0):5.2f}"
                    f"  loss {logs['loss']:7.4f}  lr {logs.get('learning_rate', 0.0):.1e}"
                    f"  grad {logs.get('grad_norm', 0.0):5.2f}",
                    flush=True,
                )
            if "eval_loss" in logs:
                el = logs["eval_loss"]
                best = state.best_metric
                tag = f"  best {best:.4f}" if best is not None else ""
                print(
                    f"[{run_name}] {step:>4}  EVAL  loss {el:7.4f}  ppl {math.exp(el):8.2f}{tag}",
                    flush=True,
                )

    torch.manual_seed(seed)
    shard_dir = Path(SHARD_DIR)
    train_ds = PackedShard(shard_dir / "train.bin")
    eval_ds = PackedShard(shard_dir / "dev.bin")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForMaskedLM.from_pretrained(model_name)

    if adapter == "dora":
        from peft import LoraConfig, TaskType, get_peft_model

        # Every linear layer in the encoder — QKV, attention output, and both FFN
        # projections — so the adapter has full expressivity. FEATURE_EXTRACTION
        # adapts the transformer and leaves the (tied) MLM head frozen to decode;
        # lm_head is excluded explicitly so no adapter lands on the embeddings.
        model = get_peft_model(
            model,
            LoraConfig(
                task_type=TaskType.FEATURE_EXTRACTION,
                r=lora_r,
                lora_alpha=lora_alpha,
                lora_dropout=lora_dropout,
                use_dora=True,
                use_rslora=True,  # scaling = alpha / sqrt(r): stable at high rank.
                target_modules=[
                    "query",
                    "key",
                    "value",
                    "attention.output.dense",
                    "intermediate.dense",
                    "output.dense",
                ],
                exclude_modules=["lm_head.dense", "lm_head.decoder"],
            ),
        )
        model.print_trainable_parameters()
    elif adapter != "full":
        raise ValueError(f"adapter must be 'full' or 'dora', got {adapter!r}")

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(
        f"[{run_name}] adapter={adapter} lr={learning_rate:.1e} "
        f"trainable={trainable / 1e6:.1f}M  train_blocks={len(train_ds)} "
        f"dev_blocks={len(eval_ds)}  seq_len={train_ds.seq_len}",
        flush=True,
    )

    ckpt_dir = f"{CKPT_ROOT}/{run_name}"
    args = TrainingArguments(
        output_dir=ckpt_dir,  # inside the Volume -> checkpointing is preemption-safe.
        max_steps=max_steps,
        per_device_train_batch_size=per_device_batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        warmup_steps=int(warmup_ratio * max_steps),  # warmup_ratio is deprecated in 5.x.
        lr_scheduler_type="linear",
        bf16=True,
        logging_steps=50,
        logging_first_step=True,
        eval_strategy="steps",
        eval_steps=eval_every,
        save_strategy="steps",
        save_steps=eval_every,
        save_total_limit=2,
        # Keep the best-by-dev-loss weights, not the last ones — this is what
        # turns "how many epochs?" into a measurement instead of a guess.
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to=[],
        disable_tqdm=True,
        seed=seed,
        dataloader_num_workers=2,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=GapAwareCollator(
            tokenizer=tokenizer,
            mlm=True,
            mlm_probability=mlm_probability,
            gap_ids=set(tokenizer("…", add_special_tokens=False)["input_ids"]),
        ),
        callbacks=[ClearLogger(), EarlyStoppingCallback(early_stopping_patience=patience)],
    )
    # Silence HF's default metric-dict printer; ClearLogger is the only voice.
    trainer.remove_callback(PrinterCallback)
    trainer.remove_callback(ProgressCallback)

    # Only ever true on a preemption retry (the entrypoint clears checkpoints for
    # a fresh comparison), so this resumes THIS run, never a previous one.
    ckpt_path = Path(ckpt_dir)
    resume = ckpt_path.is_dir() and any(p.name.startswith("checkpoint-") for p in ckpt_path.iterdir())
    trainer.train(resume_from_checkpoint=resume or None)

    loss = float(trainer.evaluate().get("eval_loss", float("nan")))
    stopped_at = int(trainer.state.global_step)

    final = f"{ckpt_dir}/final"
    trainer.save_model(final)
    tokenizer.save_pretrained(final)
    volume.commit()

    result = {
        "run": run_name,
        "adapter": adapter,
        "learning_rate": learning_rate,
        "eval_loss": loss,
        "perplexity": math.exp(loss),
        "stopped_at_step": stopped_at,
        "hit_ceiling": float(stopped_at >= max_steps),
        "trainable_params": trainable,
    }
    print(f"[{run_name}] RESULT {json.dumps(result)}", flush=True)
    return result


@app.local_entrypoint()
def launch(arm: str = "full", max_steps: int = 4048) -> None:
    """Train a single arm ("full" or "dora") with its own recipe."""
    if arm not in ARMS:
        raise SystemExit(f"arm must be one of {sorted(ARMS)}, got {arm!r}")
    reset_checkpoints.remote([arm])  # fresh start; retries still resume in-run.
    print(json.dumps(train.remote(run_name=arm, max_steps=max_steps, **ARMS[arm]), indent=2))


@app.local_entrypoint()
def compare() -> None:
    """Run full FT and DoRA in parallel and report dev perplexity for both.

    Whichever reaches the lower dev loss is the stronger DAPT backbone *by this
    proxy*; the arm actually shipped is decided downstream on gold NER F1.
    ``hit_ceiling`` flags an arm still improving when the ceiling stopped it —
    the signal to raise ``max_steps`` (or that the corpus is data-starved).
    """
    cleared = reset_checkpoints.remote(list(ARMS))
    print(f"fresh start — cleared checkpoints: {cleared or 'none'}")
    calls = {name: train.spawn(run_name=name, **cfg) for name, cfg in ARMS.items()}
    results = [call.get() for call in calls.values()]

    print("\n=== DAPT comparison (lower perplexity is better) ===")
    header = f"{'arm':6s} {'ppl':>9s} {'eval_loss':>10s} {'lr':>7s} {'stop@':>7s} {'trainable':>11s}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: x["eval_loss"]):
        flag = "  <- still improving" if r["hit_ceiling"] else ""
        print(
            f"{r['run']:6s} {r['perplexity']:9.2f} {r['eval_loss']:10.4f} "
            f"{r['learning_rate']:7.0e} {r['stopped_at_step']:7d} "
            f"{r['trainable_params'] / 1e6:9.1f}M{flag}"
        )
    best = min(results, key=lambda x: x["eval_loss"])
    print(f"\nlower dev loss: {best['run']}  (ppl {best['perplexity']:.2f})  "
          f"— confirm the real winner downstream on gold NER F1.")
