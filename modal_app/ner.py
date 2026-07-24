"""Entity NER, two-stage: silver-pretrain → fine-tune on gold (Phase 7).

Phase 7 showed DAPT (b1) beats no-DAPT (b0) but both plateau at the *silver*
ceiling (~0.59), because both only ever train on silver and never on the clean
gold. The fix from the weak+clean literature (NEEDLE 2106.08977; "Weaker Than
You Think" 2305.17442): use the small gold as a **final fine-tune stage**, not
just as eval — it corrects silver's systematic errors.

This file measures that, honestly, with paired k-fold cross-validation:

    silver-only : the silver-trained model scored on a held-out gold fold
    silver→gold : same model, then fine-tuned on that fold's gold-train,
                  scored on the same held-out fold

Per fold the two are measured on the *same* documents (paired), and per-doc
scores are pooled across folds into one micro-F1 each. The silver stage runs
once (the expensive part); the gold fine-tunes are cheap and run k times.

    loss = "ce"   baseline cross-entropy on silver          (step 1)
    loss = "gce"  generalized cross-entropy, noise-robust     (step 2, RoSTER)
    min_confidence>0  drops the low-confidence silver tail    (confidence filter)

Run with the project venv's modal (the container imports `oikonomia`):

    .venv/bin/modal run --detach modal_app/ner.py::push               # data, once
    .venv/bin/modal run --detach modal_app/ner.py::xval               # b1, ce
    .venv/bin/modal run --detach modal_app/ner.py::xval --loss gce    # step 2
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import modal


def _fingerprint(data: bytes) -> str:
    """Content fingerprint of a silver/gold jsonl blob.

    Printed by both ``push`` (what was uploaded) and ``train`` (what was read off
    the Volume) so a stale-data run is obvious at a glance instead of inferred:
    identical ``sha`` = identical bytes. ``age`` is a cheap canary for the
    Silver-v2 AGE fix — it is ~1.6k in the new silver and ~0 in the old.
    """
    sha = hashlib.sha256(data).hexdigest()[:12]
    docs = data.count(b"\n")
    age = data.count(b'"AGE"')
    return f"sha={sha} docs={docs} age={age}"

APP_NAME = "oikonomia-ner"
GPU = "A10"
NER_VOLUME = "oikonomia-ner"
DAPT_VOLUME = "oikonomia-dapt"
VOL_ROOT = "/vol"
DAPT_ROOT = "/dapt"
DATA_DIR = f"{VOL_ROOT}/data"
MODEL_ROOT = f"{VOL_ROOT}/models"

REPO = Path(__file__).resolve().parents[1]
LOCAL = {
    "silver.jsonl": REPO / "data" / "processed" / "silver.jsonl",
    "gold.jsonl": REPO / "data" / "gold" / "annotated.jsonl",
    "labels.json": REPO / "data" / "processed" / "ner" / "labels.json",
}

DAPT_CKPT = f"{DAPT_ROOT}/checkpoints/full/final"
BACKBONES = {"b0": "bowphs/GreBerta", "b1": DAPT_CKPT}
WATCH = ("PERSON", "PLACE", "MONEY_AMOUNT", "OCCUPATION")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch>=2.2",
        "transformers>=5.0,<6",
        "accelerate>=0.33",
        "numpy>=1.26",
        "pydantic>=2",
    )
    .add_local_python_source("oikonomia")
)

app = modal.App(APP_NAME, image=image)
ner_volume = modal.Volume.from_name(NER_VOLUME, create_if_missing=True)
dapt_volume = modal.Volume.from_name(DAPT_VOLUME, create_if_missing=True)


@app.function(volumes={VOL_ROOT: ner_volume}, timeout=1800)
def upload_data(blobs: dict[str, bytes]) -> dict[str, str]:
    out = Path(DATA_DIR)
    out.mkdir(parents=True, exist_ok=True)
    for name, blob in blobs.items():
        (out / name).write_bytes(blob)
    ner_volume.commit()
    ner_volume.reload()
    # Fingerprint the *committed* Volume file (not the in-memory blob) so the
    # print reflects exactly what a later ``train`` will read back.
    return {name: _fingerprint((out / name).read_bytes()) for name in blobs}


@app.local_entrypoint()
def push() -> None:
    """Send silver, gold and the frozen label schema to the Volume."""
    missing = [str(p) for p in LOCAL.values() if not p.is_file()]
    if missing:
        raise SystemExit(f"missing locally: {missing}\nrun `oik silver label` and `oik ner prepare`.")
    blobs = {name: p.read_bytes() for name, p in LOCAL.items()}
    print(f"[push] local  silver.jsonl  {_fingerprint(blobs['silver.jsonl'])}")
    volume_fp = upload_data.remote(blobs)
    for name, fp in volume_fp.items():
        print(f"[push] volume {name}  {fp}")
    if _fingerprint(blobs["silver.jsonl"]) != volume_fp["silver.jsonl"]:
        raise SystemExit("[push] FAILED: uploaded silver does not match local — retry the push.")
    print("[push] OK — the sha above must match `train`'s 'training on silver' line.")


@app.function(volumes={VOL_ROOT: ner_volume}, timeout=600)
def reset_models(names: list[str]) -> list[str]:
    import shutil

    cleared = []
    for name in names:
        d = Path(f"{MODEL_ROOT}/{name}")
        if d.is_dir():
            shutil.rmtree(d)
            cleared.append(name)
    ner_volume.commit()
    return cleared


@app.function(
    gpu=GPU,
    volumes={VOL_ROOT: ner_volume, DAPT_ROOT: dapt_volume},
    timeout=24 * 3600,
    retries=modal.Retries(max_retries=3, initial_delay=10.0),
)
def train(
    run_name: str,
    backbone: str,
    loss: str = "ce",  # "ce" | "gce"
    silver_lr: float = 5e-5,
    silver_max_steps: int = 2000,
    gold_lr: float = 3e-5,
    gold_epochs: int = 15,
    gold_batch: int = 8,
    k_folds: int = 5,
    per_device_batch_size: int = 32,
    seq_len: int = 512,
    min_confidence: float = 0.0,
    gce_q: float = 0.7,
    warmup_ratio: float = 0.06,
    seed: int = 17,
    save_final: bool = False,
) -> dict[str, object]:
    """Silver-pretrain (with `loss`), then paired k-fold gold fine-tuning.

    With ``save_final=True`` a final model is trained on **all** gold (not a held-out
    fold), same recipe, and saved to ``{MODEL_ROOT}/{run_name}/final`` — the single
    shippable checkpoint for the Hub release (see ``launch`` / ``push_to_hub``).
    """
    import os

    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    import torch
    import torch.nn.functional as F  # noqa: N812
    from torch.utils.data import Dataset
    from transformers import (
        AutoModelForTokenClassification,
        AutoTokenizer,
        DataCollatorForTokenClassification,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )
    from transformers.trainer_callback import PrinterCallback, ProgressCallback

    from oikonomia.labeling.score import build_report
    from oikonomia.ner.data import entities_of, read_ner_jsonl
    from oikonomia.ner.encode import align_bio, decode_spans, label_maps

    if backbone.startswith(DAPT_ROOT) and not Path(backbone).is_dir():
        raise SystemExit(f"{backbone} not found — let the DAPT run save full/final first.")
    if loss not in {"ce", "gce"}:
        raise ValueError(f"loss must be 'ce' or 'gce', got {loss!r}")

    # Fetch the latest committed push. Without this a warm/reused container keeps
    # its start-of-life Volume mount and silently trains on the *previous*
    # silver — the Silver-v2 push looked applied but the run used stale data.
    # The fingerprint below must match the `[push] volume silver.jsonl` line.
    ner_volume.reload()
    print(
        f"[{run_name}] training on silver  "
        f"{_fingerprint(Path(f'{DATA_DIR}/silver.jsonl').read_bytes())}",
        flush=True,
    )

    schema = json.loads(Path(f"{DATA_DIR}/labels.json").read_text(encoding="utf-8"))
    label_list: list[str] = schema["labels"]
    label2id, id2label = label_maps(label_list)
    device = "cuda"

    tokenizer = AutoTokenizer.from_pretrained(backbone, use_fast=True)
    collator = DataCollatorForTokenClassification(tokenizer)

    def encode(d):
        enc = tokenizer(d["text"], truncation=True, max_length=seq_len, return_offsets_mapping=True)
        offsets = [tuple(o) for o in enc["offset_mapping"]]
        row = {
            "input_ids": enc["input_ids"],
            "attention_mask": enc["attention_mask"],
            "labels": align_bio(offsets, entities_of(d, min_confidence=min_confidence), label2id),
        }
        return row, offsets, entities_of(d)  # gold spans use ALL entities

    silver_rows = [encode(d)[0] for d in read_ner_jsonl(Path(f"{DATA_DIR}/silver.jsonl"))]
    gold_docs = read_ner_jsonl(Path(f"{DATA_DIR}/gold.jsonl"))
    gold_rows, gold_offsets, gold_spans = [], [], []
    for d in gold_docs:
        r, off, sp = encode(d)
        gold_rows.append(r)
        gold_offsets.append(off)
        gold_spans.append(sp)

    class Rows(Dataset):
        def __init__(self, rows):
            self.rows = rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, i):
            return self.rows[i]

    class NoisyTrainer(Trainer):
        """Cross-entropy or noise-robust GCE over the non-ignored tokens."""

        def __init__(self, *a, loss_type="ce", q=0.7, **kw):
            super().__init__(*a, **kw)
            self.loss_type = loss_type
            self.q = q

        def compute_loss(self, model, inputs, return_outputs=False, **kw):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            logits = outputs.logits.view(-1, outputs.logits.size(-1))
            flat = labels.view(-1)
            keep = flat != -100
            logits, flat = logits[keep], flat[keep]
            if self.loss_type == "gce":
                py = F.softmax(logits, dim=-1).gather(1, flat.unsqueeze(1)).squeeze(1).clamp_min(1e-7)
                loss = ((1.0 - py**self.q) / self.q).mean()
            else:
                loss = F.cross_entropy(logits, flat)
            return (loss, outputs) if return_outputs else loss

    def predict(indices):
        """Per-doc forward → decoded spans, as (gold, [], pred, []) for build_report."""
        model.eval()
        per_doc = []
        with torch.no_grad():
            for j in indices:
                r = gold_rows[j]
                ids = torch.tensor([r["input_ids"]], device=device)
                am = torch.tensor([r["attention_mask"]], device=device)
                pred_ids = model(input_ids=ids, attention_mask=am).logits[0].argmax(-1).tolist()
                spans = decode_spans(pred_ids, gold_offsets[j], id2label)
                per_doc.append((gold_spans[j], [], spans, []))
        model.train()
        return per_doc

    def report(per_doc):
        return build_report(n_docs=len(per_doc), n_docs_scored=len(per_doc), per_doc=per_doc)

    def quiet_args(**kw):
        base = {
            "report_to": [], "disable_tqdm": True, "bf16": True, "seed": seed,
            "save_strategy": "no", "eval_strategy": "no", "logging_steps": 50,
            "dataloader_num_workers": 2, "warmup_ratio": warmup_ratio,
        }
        base.update(kw)
        return TrainingArguments(**base)

    print(
        f"[{run_name}] backbone={backbone} loss={loss} min_conf={min_confidence} "
        f"labels={len(label_list)} silver={len(silver_rows)} gold={len(gold_rows)} k={k_folds}",
        flush=True,
    )
    model = AutoModelForTokenClassification.from_pretrained(
        backbone, num_labels=len(label_list), id2label=id2label, label2id=label2id
    ).to(device)

    # --- Silver stage (once) ---
    class SilverLog(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and "loss" in logs:
                print(f"[{run_name}] silver {state.global_step:>4}/{args.max_steps} "
                      f"loss {logs['loss']:6.3f}", flush=True)

    silver = NoisyTrainer(
        model=model,
        args=quiet_args(
            output_dir="/tmp/silver", max_steps=silver_max_steps, learning_rate=silver_lr,
            per_device_train_batch_size=per_device_batch_size, lr_scheduler_type="linear",
        ),
        train_dataset=Rows(silver_rows),
        data_collator=collator,
        loss_type=loss,
        q=gce_q,
        callbacks=[SilverLog()],
    )
    silver.remove_callback(PrinterCallback)
    silver.remove_callback(ProgressCallback)
    silver.train()
    silver_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    print(f"[{run_name}] silver done — starting {k_folds}-fold gold fine-tuning", flush=True)

    # --- Paired k-fold gold fine-tuning ---
    rng = torch.Generator().manual_seed(seed)
    order = torch.randperm(len(gold_rows), generator=rng).tolist()
    folds = [order[i::k_folds] for i in range(k_folds)]  # round-robin, balanced sizes

    so_pool, sg_pool = [], []  # pooled per-doc for silver-only and silver→gold
    for i, held in enumerate(folds):
        train_idx = [j for j in range(len(gold_rows)) if j not in set(held)]
        model.load_state_dict(silver_state)
        so = predict(held)  # silver-only on the held-out fold
        gold = NoisyTrainer(
            model=model,
            args=quiet_args(
                output_dir=f"/tmp/gold{i}", num_train_epochs=gold_epochs, learning_rate=gold_lr,
                per_device_train_batch_size=gold_batch,
            ),
            train_dataset=Rows([gold_rows[j] for j in train_idx]),
            data_collator=collator,
            loss_type="ce",
        )
        gold.remove_callback(PrinterCallback)
        gold.remove_callback(ProgressCallback)
        gold.train()
        sg = predict(held)  # silver→gold on the same held-out fold
        so_pool += so
        sg_pool += sg
        print(f"[{run_name}] fold {i + 1}/{k_folds} (n={len(held)}): "
              f"silver-only {report(so).strict.f1:.3f} → silver+gold {report(sg).strict.f1:.3f}",
              flush=True)

    so_rep, sg_rep = report(so_pool), report(sg_pool)
    so_by = {r.label: r.f1 for r in so_rep.strict.by_label}
    sg_by = {r.label: r.f1 for r in sg_rep.strict.by_label}
    result: dict[str, object] = {
        "run": run_name, "backbone": backbone, "loss": loss, "min_confidence": min_confidence,
        "silver_only": {"strict_f1": so_rep.strict.f1, "relaxed_f1": so_rep.relaxed.f1, "by_label": so_by},
        "silver_gold": {"strict_f1": sg_rep.strict.f1, "relaxed_f1": sg_rep.relaxed.f1, "by_label": sg_by},
        "delta_strict_f1": round(sg_rep.strict.f1 - so_rep.strict.f1, 4),
    }

    print(f"\n[{run_name}] === TWO-STAGE ({k_folds}-fold CV, loss={loss}) ===", flush=True)
    print(f"[{run_name}] silver-only : strict {so_rep.strict.f1:.3f}  relaxed {so_rep.relaxed.f1:.3f}")
    print(f"[{run_name}] silver→gold : strict {sg_rep.strict.f1:.3f}  relaxed {sg_rep.relaxed.f1:.3f}"
          f"   (Δ strict {result['delta_strict_f1']:+.3f})")
    print(f"[{run_name}] per-label strict Δ: "
          + "  ".join(f"{w} {sg_by.get(w, 0) - so_by.get(w, 0):+.3f}" for w in WATCH))
    print(f"[{run_name}] RESULT {json.dumps(result, ensure_ascii=False)}", flush=True)

    if save_final:
        # The shippable artifact: retrain on ALL gold (no held-out fold), identical
        # recipe as the folds, and persist it. The CV numbers above are the honest
        # eval; this is the model those numbers describe, trained on everything.
        model.load_state_dict(silver_state)
        final = NoisyTrainer(
            model=model,
            args=quiet_args(
                output_dir="/tmp/final", num_train_epochs=gold_epochs,
                learning_rate=gold_lr, per_device_train_batch_size=gold_batch,
            ),
            train_dataset=Rows(gold_rows),
            data_collator=collator,
            loss_type="ce",
        )
        final.remove_callback(PrinterCallback)
        final.remove_callback(ProgressCallback)
        final.train()
        save_dir = f"{MODEL_ROOT}/{run_name}/final"
        model.save_pretrained(save_dir)
        tokenizer.save_pretrained(save_dir)
        ner_volume.commit()
        result["saved_model"] = save_dir
        print(f"[{run_name}] saved shippable model (all-gold) → {save_dir}", flush=True)

    return result


@app.local_entrypoint()
def xval(backbone: str = "b1", loss: str = "ce") -> None:
    """Two-stage CV for one backbone+loss: silver-only vs silver→gold on gold."""
    if backbone not in BACKBONES:
        raise SystemExit(f"backbone must be one of {sorted(BACKBONES)}, got {backbone!r}")
    run = f"{backbone}-{loss}"
    reset_models.remote([run])
    print(json.dumps(train.remote(run_name=run, backbone=BACKBONES[backbone], loss=loss), indent=2, ensure_ascii=False))


@app.function(gpu=GPU, volumes={VOL_ROOT: ner_volume, DAPT_ROOT: dapt_volume})
def predict_remote(text: str, labels_json: str, backbone: str = "b1") -> list[dict[str, object]]:
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    from oikonomia.ner.encode import decode_spans

    labels_data = json.loads(labels_json)
    labels = labels_data["labels"]
    id2label = dict(enumerate(labels))
    label2id = labels_data["label2id"]

    model_path = BACKBONES.get(backbone, backbone)
    possible_ckpts = [
        f"{MODEL_ROOT}/{backbone}/final",
        f"{MODEL_ROOT}/{backbone}-ce/final",
        f"{MODEL_ROOT}/b1-ce/final",
        model_path,
    ]
    ckpt_used = model_path
    for p in possible_ckpts:
        if Path(p).exists() and (Path(p) / "config.json").exists():
            ckpt_used = p
            break

    print(f"[{APP_NAME}] Loading TokenClassification checkpoint: {ckpt_used}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForTokenClassification.from_pretrained(
        ckpt_used, num_labels=len(labels), id2label=id2label, label2id=label2id
    ).to("cuda")

    model.eval()

    inputs = tokenizer(text, return_tensors="pt", return_offsets_mapping=True, truncation=True)
    offsets = inputs.pop("offset_mapping")[0].tolist()
    inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits[0]
        preds = logits.argmax(dim=-1).cpu().tolist()

    spans = decode_spans(preds, offsets, id2label)
    return [{"type": label, "text": text[s:e], "start": s, "end": e} for (s, e, label) in spans]


@app.local_entrypoint()
def predict(text: str = "Παχὼν κα τέτακται ἐπὶ τὴν ἐν Κροκοδίλων πόλει τράπεζαν χαλκοῦ δραχμῶν Β", backbone: str = "b1") -> None:
    """Run direct GPU inference on Modal for any ancient Greek text string."""
    print(f"\n[Modal GPU Inference] backbone={backbone}")
    print(f"Input text: \"{text}\"")
    labels_json = LOCAL["labels.json"].read_text(encoding="utf-8")
    spans = predict_remote.remote(text, labels_json=labels_json, backbone=backbone)
    print("\n=== EXTRACTED NAMED ENTITIES ===")
    if not spans:
        print("  (No entities found)")
    for s in spans:
        print(f"  [{s['type']:<14}] \"{s['text']}\" (char {s['start']}:{s['end']})")


# --- Hub release (deliverable #1): owner-run, needs auth ----------------------
#
# Two owner-run steps produce the public model (Claude cannot authenticate or
# publish). The eval numbers are the CV run's; `launch` trains the shipped weights
# on all gold; `push_to_hub` uploads them behind the licence firewall.
#
#   1. .venv/bin/modal run --detach modal_app/ner.py::launch           # → models/release/final
#   2. modal secret create huggingface HF_TOKEN=hf_xxx                 # once (a write token)
#   3. .venv/bin/modal run modal_app/ner.py::push_to_hub --repo-id <org>/oikonomia-ner
#
RELEASE_RUN = "release"
RELEASE_CKPT = f"{MODEL_ROOT}/{RELEASE_RUN}/final"
# The model's verified lineage — checked by the firewall before any upload.
RELEASE_LINEAGE = ["bowphs/GreBerta", "DDbDP", "oikonomia-gold"]


@app.local_entrypoint()
def launch(backbone: str = "b1") -> None:
    """Train the single shippable NER model on all gold and save it to the volume."""
    reset_models.remote([RELEASE_RUN])
    result = train.remote(
        run_name=RELEASE_RUN, backbone=BACKBONES[backbone], loss="ce", save_final=True
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


@app.function(volumes={VOL_ROOT: ner_volume}, secrets=[modal.Secret.from_name("huggingface")], timeout=1800)
def push_to_hub_remote(repo_id: str, checkpoint: str, model_card: str, labels_json: str, private: bool) -> str:
    """Upload a saved checkpoint to the Hub — gated by the licence firewall."""
    import os

    from huggingface_hub import HfApi

    from oikonomia.models.licensing import assert_releasable

    assert_releasable(RELEASE_LINEAGE)  # refuses NonCommercial / unverified lineage

    ckpt = Path(checkpoint)
    if not (ckpt / "config.json").exists():
        raise SystemExit(f"no saved model at {checkpoint} — run `launch` first.")
    (ckpt / "README.md").write_text(model_card, encoding="utf-8")
    (ckpt / "labels.json").write_text(labels_json, encoding="utf-8")

    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)
    api.upload_folder(repo_id=repo_id, folder_path=str(ckpt), repo_type="model")
    url = f"https://huggingface.co/{repo_id}"
    print(f"[{APP_NAME}] pushed {checkpoint} → {url} (private={private})", flush=True)
    return url


@app.local_entrypoint()
def push_to_hub(repo_id: str, checkpoint: str = RELEASE_CKPT, private: bool = True) -> None:
    """Publish the shipped NER model to the Hub (starts PRIVATE — flip to public on HF).

    Requires a Modal secret ``huggingface`` carrying an HF **write** token, and a
    checkpoint produced by ``launch``. Attaches the model card + labels; the licence
    firewall runs before any bytes leave.
    """
    card = (REPO / "resources" / "release" / "MODEL_CARD.md").read_text(encoding="utf-8")
    labels_json = LOCAL["labels.json"].read_text(encoding="utf-8")
    url = push_to_hub_remote.remote(
        repo_id=repo_id, checkpoint=checkpoint, model_card=card, labels_json=labels_json, private=private
    )
    print(f"\n✅ pushed → {url}\n   (private — make it public in the HF repo settings when ready)")


