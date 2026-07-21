"""Modal job: domain-adaptive pretraining of GreBerta on documentary papyri.

Orchestration only. What data the model sees was decided offline in
``oikonomia.dapt`` and frozen into packed shards. Deleting this directory must
not break the library.

    modal run modal_app/dapt.py::push      # upload shards, once
    modal run modal_app/dapt.py::sweep     # decide adapter + length empirically
    modal run modal_app/dapt.py::launch    # single run with chosen settings

## The regime we are actually in

GreBerta is 110M parameters. The packed train shard is **8.3M tokens** — 0.075
tokens per parameter. The DAPT literature ("Don't Stop Pretraining") used
2.1–8.1 *billion*-token domain corpora, i.e. **250–1000x more**. Its recipe —
full fine-tuning for 12,500 steps — does not transfer here, and applying it
unchanged would train for ~49 epochs and memorise the train split.

There is no more in-domain data to find. DCLP (literary papyri, already on
disk) parses cleanly but adds only ~1.4M tokens (+17%) and pulls the register
*away* from documentary Greek, which is the same objection that ruled out
koine-t5-omni. Not worth it unless the dev curve shows genuine data starvation.

## What follows from that

**1. Do not guess the epoch count — let the dev set end the run.** Early
stopping on held-out perplexity with a generous ceiling removes the question
entirely. The earlier "12,500 vs 2,024 steps" argument was the wrong argument:
whichever number is right, the dev curve knows it and we do not.

**2. Do not argue LoRA vs full fine-tuning — measure it.** A whole run is
~15-45 minutes and well under a dollar on an A10, so a two-point sweep costs
less than the time spent reasoning about it.

The *prior*, stated so it is falsifiable: **LoRA should win or tie.** At 0.075
tokens/param the binding constraint is data, not capacity, and "LoRA learns
less and forgets less" is only a cost when there is enough data to learn more
from. Direct in-domain evidence agrees — koineformer adapted this very
backbone family with LoRA r=16 on 1.5M tokens. So LoRA is the default and full
fine-tuning is the challenger, which is the reverse of this file's first draft.

**3. Sequence length is a real variable here, not a default.** The median
papyrus is ~74 tokens, so a 512-token block packs ~7 unrelated documents and
most attention is cross-document noise. 256 halves that and doubles the number
of blocks. Cheap to test; included in the sweep.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

APP_NAME = "oikonomia-dapt"
# gpu="A10" — verified against modal.com/docs. "A10G" is no longer in the
# documented GPU list (T4, L4, A10, L40S, A100, H100, H200, B200, B300).
GPU = "A10"
VOLUME_NAME = "oikonomia-dapt"
VOL_ROOT = "/vol"
SHARD_DIR = f"{VOL_ROOT}/shards"
CKPT_ROOT = f"{VOL_ROOT}/checkpoints"

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
        "peft>=0.12",
        "numpy>=1.26",
    )
    # Local source is added explicitly: automounting was removed in Modal >=1.0.
    .add_local_python_source("oikonomia")
)

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


@app.function(
    gpu=GPU,
    volumes={VOL_ROOT: volume},
    timeout=24 * 3600,
    # A10 capacity is preemptible; retry and resume rather than lose the run.
    retries=modal.Retries(max_retries=3, initial_delay=10.0),
)
def train(
    run_name: str = "b1-lora",
    model_name: str = "bowphs/GreBerta",
    adapter: str = "lora",  # "lora" | "full"
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_scope: str = "attn+ffn",  # "attn+ffn" | "attn"
    # A *ceiling*, not a target: early stopping on dev loss ends the run. Set
    # generously (~16 epochs) so the dev curve, not this number, decides.
    max_steps: int = 4048,
    patience: int = 5,
    eval_every: int = 100,
    learning_rate: float = 5e-5,
    per_device_batch_size: int = 32,
    grad_accum: int = 2,
    warmup_ratio: float = 0.06,
    mlm_probability: float = 0.15,
    seed: int = 17,
) -> dict[str, float | str]:
    """Continued MLM pretraining on the packed papyri shards.

    Returns dev loss/perplexity so runs in a sweep are directly comparable.
    """
    import math

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
            # int64 for the embedding lookup; uint16 on disk is storage only.
            block = torch.from_numpy(self.data[i].astype(np.int64))
            return {"input_ids": block, "attention_mask": torch.ones_like(block)}

    class GapAwareCollator(DataCollatorForLanguageModeling):
        """MLM masking that never targets the lacuna placeholder.

        The gap marker "…" is 1.16% of corpus *characters* but tokenises to two
        byte pieces, making it **6.0% of the token stream**. Left alone, ~6% of
        the masking budget is spent predicting an editorial symbol that is
        trivially predictable from its other half — near-zero loss, near-zero
        gradient. Worse, those easy targets deflate dev perplexity, and dev
        perplexity is what early stopping and model selection run on.

        The markers stay in the *input*: they are real, they appear at
        inference, and deleting them would splice text across a lacuna and
        manufacture adjacencies that never existed. They are only excluded from
        being prediction targets.
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
                    is_gap
                    if special_tokens_mask is None
                    else special_tokens_mask.bool() | is_gap
                )
            return super().torch_mask_tokens(
                inputs, special_tokens_mask=special_tokens_mask, offset_mapping=offset_mapping
            )

    class ClearLogger(TrainerCallback):
        """One tagged line per log/eval event, with perplexity.

        The three sweep arms share one stdout, and the Trainer's default printer
        emits untagged metric dicts under tqdm bars — unreadable interleaved.
        Every line here is prefixed with ``run_name`` so a single arm is one
        ``grep`` away, and eval events carry perplexity (exp of the loss), the
        number the sweep actually selects on.
        """

        def on_log(self, args, state, control, logs=None, **kwargs):
            if not logs:
                return
            step = state.global_step
            if "loss" in logs:
                print(
                    f"[{run_name}] step {step:>4}/{args.max_steps} "
                    f"ep {logs.get('epoch', 0.0):5.2f} | train_loss {logs['loss']:7.4f} "
                    f"| lr {logs.get('learning_rate', 0.0):.2e} "
                    f"| grad {logs.get('grad_norm', 0.0):5.2f}",
                    flush=True,
                )
            if "eval_loss" in logs:
                el = logs["eval_loss"]
                best = state.best_metric
                best_str = f" | best {best:.4f}" if best is not None else ""
                print(
                    f"[{run_name}] step {step:>4} | EVAL loss {el:7.4f} "
                    f"| ppl {math.exp(el):8.3f}{best_str}",
                    flush=True,
                )

    torch.manual_seed(seed)
    shard_dir = Path(SHARD_DIR)
    train_ds = PackedShard(shard_dir / "train.bin")
    eval_ds = PackedShard(shard_dir / "dev.bin")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForMaskedLM.from_pretrained(model_name)

    if adapter == "lora":
        from peft import LoraConfig, TaskType, get_peft_model

        # PEFT matches target_modules by *suffix* ("it is checked if the name
        # of the module ends with any of the passed strings"). A bare "dense"
        # therefore also captures lm_head.dense, which is not part of the
        # encoder and is tied to the embeddings — so every name here is
        # qualified enough to exclude it.
        #
        # Default is attention + FFN, not attention alone. DAPT's job is to
        # absorb domain content, and the feed-forward blocks are where lexical
        # and factual associations live; the literature reports MLP-only
        # matching or beating all-linear, and attention-only is the
        # conservative choice rather than the apt one here. At r=16 this is
        # still ~1% of the model, far from an overfitting risk on 8.3M tokens.
        scopes = {
            "attn": ["query", "key", "value"],
            "attn+ffn": [
                "query",
                "key",
                "value",
                "attention.output.dense",
                "intermediate.dense",
                "output.dense",
            ],
        }
        if lora_scope not in scopes:
            raise ValueError(f"lora_scope must be one of {sorted(scopes)}, got {lora_scope!r}")

        model = get_peft_model(
            model,
            LoraConfig(
                # PEFT has no masked-LM task type; FEATURE_EXTRACTION adapts
                # the encoder and leaves the LM head frozen. That head is tied
                # to the input embeddings, so training it would mean training
                # the embedding matrix — a much larger change than "LoRA".
                # Adaptation therefore happens in the encoder and the frozen
                # head decodes it, which is what we want for a tagger backbone.
                task_type=TaskType.FEATURE_EXTRACTION,
                r=lora_r,
                lora_alpha=lora_alpha,
                lora_dropout=0.1,
                target_modules=scopes[lora_scope],
                exclude_modules=["lm_head.dense", "lm_head.decoder"],
            ),
        )
        model.print_trainable_parameters()
    elif adapter != "full":
        raise ValueError(f"adapter must be 'lora' or 'full', got {adapter!r}")

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(
        f"[{run_name}] adapter={adapter} trainable={trainable / 1e6:.1f}M "
        f"train_blocks={len(train_ds)} dev_blocks={len(eval_ds)} seq_len={train_ds.seq_len}"
    )

    ckpt_dir = f"{CKPT_ROOT}/{run_name}"
    args = TrainingArguments(
        # Inside the Volume, so HF checkpointing is what makes the job
        # preemption-safe; background commits persist it automatically.
        output_dir=ckpt_dir,
        max_steps=max_steps,
        per_device_train_batch_size=per_device_batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        lr_scheduler_type="linear",
        bf16=True,
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=eval_every,
        save_strategy="steps",
        save_steps=eval_every,
        save_total_limit=2,
        # The three settings that turn "how many epochs?" from a guess into a
        # measurement: keep the best-by-dev-loss weights, not the last ones.
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to=[],
        # Our ClearLogger prints the metrics; the tqdm bars only interleave
        # noise across the three parallel arms sharing one stdout.
        disable_tqdm=True,
        logging_first_step=True,
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
        callbacks=[
            ClearLogger(),
            EarlyStoppingCallback(early_stopping_patience=patience),
        ],
    )

    ckpt_path = Path(ckpt_dir)
    resume = ckpt_path.is_dir() and any(
        p.name.startswith("checkpoint-") for p in ckpt_path.iterdir()
    )
    trainer.train(resume_from_checkpoint=resume or None)

    metrics = trainer.evaluate()
    loss = float(metrics.get("eval_loss", float("nan")))
    stopped_at = int(trainer.state.global_step)

    final = f"{ckpt_dir}/final"
    trainer.save_model(final)
    tokenizer.save_pretrained(final)
    volume.commit()

    result = {
        "run": run_name,
        "adapter": adapter,
        "lora_scope": lora_scope if adapter == "lora" else "-",
        "eval_loss": loss,
        "perplexity": math.exp(loss),
        "stopped_at_step": stopped_at,
        "hit_ceiling": float(stopped_at >= max_steps),
        "trainable_params": trainable,
    }
    print(f"[{run_name}] {json.dumps(result)}")
    return result


@app.local_entrypoint()
def launch(run_name: str = "b1-lora", adapter: str = "lora", max_steps: int = 4048) -> None:
    """One run with chosen settings."""
    print(json.dumps(train.remote(run_name=run_name, adapter=adapter, max_steps=max_steps), indent=2))


@app.local_entrypoint()
def sweep() -> None:
    """Decide adapter empirically instead of by argument.

    Two runs, in parallel, well under a dollar. Whichever reaches the lower dev
    perplexity is the primary arm; ``hit_ceiling`` tells you whether either was
    still improving when the ceiling stopped it, which is the signal that the
    corpus is data-starved rather than capacity-starved.
    """
    configs = [
        {"run_name": "b1-lora-attn-ffn", "adapter": "lora", "lora_scope": "attn+ffn"},
        {"run_name": "b1-lora-attn", "adapter": "lora", "lora_scope": "attn"},
        {"run_name": "b1-full", "adapter": "full"},
    ]
    # spawn(), not map(): map/starmap take positional arguments only, so they
    # cannot vary keyword arguments across invocations. spawn returns a
    # FunctionCall to collect later, which is what gives parallelism here.
    calls = [train.spawn(**cfg) for cfg in configs]
    results = [call.get() for call in calls]

    print("\n=== DAPT sweep results (lower perplexity is better) ===")
    header = f"{'run':22s} {'ppl':>9s} {'eval_loss':>10s} {'stop@':>7s} {'trainable':>10s}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: x["eval_loss"]):
        flag = "  <- still improving (raise ceiling)" if r["hit_ceiling"] else ""
        print(
            f"{r['run']:22s} {r['perplexity']:9.3f} {r['eval_loss']:10.4f} "
            f"{r['stopped_at_step']:7d} {r['trainable_params'] / 1e6:9.1f}M{flag}"
        )
    best = min(results, key=lambda x: x["eval_loss"])
    print(f"\nwinner: {best['run']}  (perplexity {best['perplexity']:.3f}, "
          f"eval_loss {best['eval_loss']:.4f})")
