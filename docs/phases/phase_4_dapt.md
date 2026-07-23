# Phase 4 — Domain-Adaptive Pre-Training (DAPT)

### 🔶 Phase 4 — DAPT on Modal (built and priced; TRAINING RUN EXECUTED)

**Backbone changed from the original plan.** Primary is **B1 = GreBerta +
papyri DAPT**, not GreTa: encoder-only beats encoder-decoder on NER by ~15-17
F1, GreBerta is apache-2.0, half the size, 512 context, and T5's decoder would
be discarded anyway. koine-t5-omni is out on four counts (NC licence,
biblical-literary register, wrong architecture, 256-token truncation of ~25%
of documents).

#### The number that governs every other decision here

GreBerta is 110M params; the packed train shard is **8.3M tokens** — **0.075
tokens per parameter**. The DAPT literature used 2.1–8.1 **billion**-token
corpora: **250–1000x more**. Its recipe does not transfer, and this must be
checked before importing any published hyperparameter.

**There is no more in-domain data.** DCLP (literary papyri, already on disk,
14,842 files) parses 300/300 with the existing parser but yields only ~1.4M
tokens (+17%) and pulls the register *away* from documentary Greek — the same
objection that ruled out koine-t5-omni. Rejected unless the dev curve shows
genuine starvation.

#### What was decided, and why

1. **Epoch count is not guessed — the dev set ends the run.** Early stopping on
   held-out perplexity (`load_best_model_at_end`, `metric_for_best_model=
   eval_loss`, patience 5) with `max_steps` as a generous *ceiling* (4,048
   ≈ 16 epochs). The earlier "12,500 vs 2,024 steps" argument was the wrong
   argument: the dev curve knows the answer and we do not.
2. **LoRA is the default; full fine-tuning is the challenger.** At 0.075 tokens/param
   the binding constraint is *data, not capacity*, so "LoRA learns less and forgets
   less" costs nothing here — and koineformer adapted this same backbone family with
   LoRA r=16 on 1.5M tokens.
3. **It is decided by measurement, because measuring is cheap.** A full run is
   **15–45 min, ~$0.25–0.80** on an A10. `modal run modal_app/dapt.py::sweep`
   runs LoRA and full in parallel and reports dev perplexity for both.
4. **`hit_ceiling` in the sweep output is the data-starvation signal.** If a
   run is still improving when the ceiling stops it, raise the ceiling — and
   only then reconsider DCLP.
5. **seq_len is a live variable, not a default.** Median papyrus ≈ 74 tokens,
   so a 512-block packs ~7 unrelated documents and most attention is
   cross-document noise. 256 halves that and doubles the block count.

**Deliverables**
- `dapt/text.py` — train-split-only stream; **refuses to run without a split
  table**, since DAPT is unsupervised and would otherwise language-model the
  test set with nothing complaining. Lowercases (GreBerta's BPE merges are
  lowercase-only) while keeping accents (its vocabulary has them).
- `dapt/pack.py` — uint16 memmap blocks, packed not padded.
- `dapt/schedule.py` — derives steps from the shard.
- `dapt/stage.py` — packs **train and dev only**; no test shard is ever
  written, the cheapest possible guarantee it is not read.
- `modal_app/dapt.py` — A10, LoRA/full, early stopping, Volume checkpoints
  with retry+resume, `push` / `launch` / `sweep` entrypoints.
- `tests/test_architecture.py` — enforces §3: no heavy module-level imports in
  the library, and the library never imports `modal_app`.
- CLI `oik dapt {prepare,inspect}`. 190 tests total.

### 🔶 Phase 4b — DAPT run executed; full FT wins, prior FLIPPED

**The ledger's `LoRA wins or ties` prior was wrong for this stage and is now
retracted.** DAPT is *continued pretraining*, and for that regime the on-point
literature (Biderman 2405.09673) is that full FT beats low-rank adapters and the
gap does not close with rank; the `adapters ≈ full FT` results are all about the
downstream *fine-tune*, a different stage. Confirmed on GreBerta directly.

**Clean two-arm run** (`modal_app/dapt.py`, rewritten to two arms + per-arm LR):
`full` (full FT, lr 5e-5) vs `dora` (DoRA r=64, all-linear, rsLoRA, lr 1e-4) —
DoRA chosen as the *steelman* adapter (closest to full-FT geometry; beats LoRA
at all ranks). Both fresh from step 1, identical data, dev = the DAPT dev shard.
- **full: dev ppl 300 → 4.54, converged at the 16-epoch ceiling, NO
  overfitting** (dev loss never turned up; `hit_ceiling=1` but the curve is
  flat, i.e. converged not starved). Sharp phase transition ~step 1300→1700
  (ppl 70→6.7). Saved as `checkpoints/full/final` — **B1**, the papyri backbone.
- **dora: dev ppl ~415 → ~224, plateaued.** Learns, but ~50× behind full.

**Why the gap is that large (mechanistic, not just "adapters learn less"):**
full FT trains the **~40M token-embedding params (a third of the model)** plus
the LM head; the DoRA arm freezes them. Papyri's domain gap is heavily
*vocabulary/orthography* (onomastics, abbreviations, lacunae), so the embedding
remap is exactly the lever — and only full FT pulls it. At 125M params PEFT also
buys no memory (full FT fits the A10 trivially), so the adapter pays the compute
tax (DoRA materialises the merged weight per layer for its column-norm → ~2×
slower/step) without the benefit. **Verdict: full FT is the DAPT method.**
