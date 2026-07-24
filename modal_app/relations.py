"""Relation extraction, span-pair (SpERT-style), two-stage: silver → gold (Phase 8).

The entity model is validated (Phase 7b, strict 0.737). This asks the next
question: given the entities, can a model recover the *links* — which money
belongs to which commodity, who paid whom, what a payment was charged under —
better than the weak rules (PARTY_OF precision ≈ 0.28; direction recall ≈ 5%)?

Architecture (owner decision): **single encode per document**. Encode the doc
once with the DAPT'd backbone (B1); for each entity, max-pool its tokens and add
a learned type embedding; for each *type-admissible* ordered pair, classify from
`[rep_h ; rep_t ; between-span context ; CLS ; type_h ; type_t]`. The between-span
context is where the payment verb sits — the signal the rules cannot use to tell
`PAID_BY` from `PAID_TO`. Candidate generation is typed and range-pruned
(`oikonomia.relations.encode`), so most pairs never become examples and no gold
relation is lost.

Evaluation (owner decision): **oracle entities** — train and score given gold
entity spans, the clean RE number that isolates linking from NER errors and is
directly comparable to `oik relation score` (the nearest-pair baseline) and to
the silver relation labeler. End-to-end (B1-predicted entities → RE) is a later
follow-up for the deliverable number.

The measurement mirrors Phase 7b exactly: paired k-fold CV, silver-pretrain once,
then per fold score the held-out gold twice — **silver-only** and **silver→gold**
— pooled and scored with `oikonomia.labeling.score.build_report` (its `relations`
block, directed and endpoint-matched). Reuses the `oikonomia-ner` Volume's
`silver.jsonl` / `gold.jsonl` (pushed by `modal_app/ner.py::push`); only the
frozen relation schema is new.

    .venv/bin/modal run --detach modal_app/relations.py::push      # relation_labels.json
    .venv/bin/modal run --detach modal_app/relations.py::xval --backbone b1 --loss ce
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import modal


def _fingerprint(data: bytes) -> str:
    """Content fingerprint of a jsonl blob — printed on both push and train so a
    stale-data run is obvious at a glance (identical ``sha`` = identical bytes)."""
    sha = hashlib.sha256(data).hexdigest()[:12]
    docs = data.count(b"\n")
    rels = data.count(b'"type"')
    return f"sha={sha} docs={docs} rels={rels}"


APP_NAME = "oikonomia-relations"
GPU = "A10"
NER_VOLUME = "oikonomia-ner"  # shared with Phase 7: holds silver.jsonl / gold.jsonl
DAPT_VOLUME = "oikonomia-dapt"
VOL_ROOT = "/vol"
DAPT_ROOT = "/dapt"
DATA_DIR = f"{VOL_ROOT}/data"

REPO = Path(__file__).resolve().parents[1]
LABELS_LOCAL = REPO / "data" / "processed" / "relations" / "relation_labels.json"
SILVER_VOL = f"{DATA_DIR}/silver.jsonl"
GOLD_VOL = f"{DATA_DIR}/gold.jsonl"
LABELS_VOL = f"{DATA_DIR}/relation_labels.json"

DAPT_CKPT = f"{DAPT_ROOT}/checkpoints/full/final"
BACKBONES = {"b0": "bowphs/GreBerta", "b1": DAPT_CKPT}

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


@app.function(volumes={VOL_ROOT: ner_volume}, timeout=600)
def upload_labels(blob: bytes) -> dict[str, str]:
    out = Path(DATA_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "relation_labels.json").write_bytes(blob)
    ner_volume.commit()
    ner_volume.reload()
    have = {
        "relation_labels.json": (out / "relation_labels.json").is_file(),
        "silver.jsonl": Path(SILVER_VOL).is_file(),
        "gold.jsonl": Path(GOLD_VOL).is_file(),
    }
    fps: dict[str, str] = {"present": json.dumps(have)}
    if have["silver.jsonl"]:
        fps["silver.jsonl"] = _fingerprint(Path(SILVER_VOL).read_bytes())
    if have["gold.jsonl"]:
        fps["gold.jsonl"] = _fingerprint(Path(GOLD_VOL).read_bytes())
    return fps


@app.local_entrypoint()
def push() -> None:
    """Send the frozen relation schema to the Volume (silver/gold already there)."""
    if not LABELS_LOCAL.is_file():
        raise SystemExit(f"missing {LABELS_LOCAL} — run `oik relation prepare` first.")
    fps = upload_labels.remote(LABELS_LOCAL.read_bytes())
    print(f"[push] present on volume: {fps['present']}")
    for name in ("silver.jsonl", "gold.jsonl"):
        if name in fps:
            print(f"[push] volume {name}  {fps[name]}")
    have = json.loads(fps["present"])
    if not (have["silver.jsonl"] and have["gold.jsonl"]):
        raise SystemExit("[push] silver.jsonl/gold.jsonl absent — run modal_app/ner.py::push first.")
    print("[push] OK — silver.jsonl sha above must match `train`'s 'training on silver' line.")


@app.function(volumes={VOL_ROOT: ner_volume}, timeout=600)
def reset_models(names: list[str]) -> list[str]:
    return names  # xval saves no persistent model; nothing to clear (parity with ner.py).


# Where the shippable relation model lands on the (ner) Volume. It is NOT a
# standard HF model — a custom head over the encoder — so it is saved as a torch
# state_dict plus a JSON config that `build_relation_head` reads back.
RELATION_MODEL_DIR = f"{VOL_ROOT}/models/relation/final"


def build_relation_head(
    *,
    backbone: str,
    n_entity_labels: int,
    n_rel_labels: int,
    type_dim: int = 64,
    feat_dim: int = 16,
    dropout: float = 0.2,
):
    """Construct the span-pair relation head, reusable by training and inference.

    Extracted from the ``train`` closure so the *same* architecture builds the
    model for the k-fold CV, the all-gold save, and standalone inference on
    NER-predicted entities. Torch is imported lazily (module-level torch would
    break the local Modal dispatch, which has no ML stack).

    Per candidate pair the classifier sees: head/tail max-pooled reps, the
    between-span context, a WIDE context reaching before the payer (the direction
    verb), CLS, entity-type embeddings, and the 3 symbolic direction features.
    """
    import torch
    from torch import nn
    from transformers import AutoModel

    from oikonomia.relations.features import FEATURE_CARDINALITIES

    class RelationHead(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = AutoModel.from_pretrained(backbone)
            hsz = self.encoder.config.hidden_size
            self.type_emb = nn.Embedding(n_entity_labels, type_dim)
            self.feat_emb = nn.ModuleList(
                nn.Embedding(card, feat_dim) for card in FEATURE_CARDINALITIES
            )
            self.no_ctx = nn.Parameter(torch.zeros(hsz))
            self.mlp = nn.Sequential(
                nn.Dropout(dropout),
                nn.Linear(5 * hsz + 2 * type_dim + 3 * feat_dim, hsz),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(hsz, n_rel_labels),
            )

        def encode(self, input_ids, attention_mask):
            h = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
            return h, h[:, 0, :]  # token states, CLS

        def score_pairs(self, hb, cls_b, cands):
            """Logits [P, n_rel_labels] for one document's candidate pairs."""
            dev = hb.device
            reps_h, reps_t, ctxs, wides = [], [], [], []
            for c in cands:
                reps_h.append(hb[c.h0:c.h1].amax(0))
                reps_t.append(hb[c.t0:c.t1].amax(0))
                if c.h1 <= c.t0:  # head entirely left of tail
                    c0, c1 = c.h1, c.t0
                elif c.t1 <= c.h0:  # tail entirely left of head
                    c0, c1 = c.t1, c.h0
                else:  # overlapping token spans
                    c0, c1 = 0, 0
                ctxs.append(hb[c0:c1].amax(0) if c1 > c0 else self.no_ctx)
                wides.append(hb[c.w0:c.w1].amax(0) if c.w1 > c.w0 else self.no_ctx)
            rh, rt = torch.stack(reps_h), torch.stack(reps_t)
            cx, wx = torch.stack(ctxs), torch.stack(wides)
            th = self.type_emb(torch.tensor([c.htid for c in cands], device=dev))
            tt = self.type_emb(torch.tensor([c.ttid for c in cands], device=dev))
            fv = [
                self.feat_emb[0](torch.tensor([c.vc for c in cands], device=dev)),
                self.feat_emb[1](torch.tensor([c.vp for c in cands], device=dev)),
                self.feat_emb[2](torch.tensor([c.pm for c in cands], device=dev)),
            ]
            cls = cls_b.unsqueeze(0).expand(rh.size(0), -1)
            return self.mlp(torch.cat([rh, rt, cx, wx, cls, th, tt, *fv], dim=-1))

    return RelationHead()


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
    silver_lr: float = 3e-5,
    silver_max_steps: int = 2000,
    gold_lr: float = 3e-5,
    gold_epochs: int = 20,
    batch_docs: int = 8,
    k_folds: int = 5,
    seq_len: int = 512,
    type_dim: int = 64,
    feat_dim: int = 16,
    dropout: float = 0.2,
    min_confidence: float = 0.0,
    no_relation_weight: float = 1.0,
    constrain_decode: bool = True,
    payment_lex: dict[str, list[str]] | None = None,
    gce_q: float = 0.7,
    warmup_ratio: float = 0.06,
    seed: int = 17,
    save_final: bool = False,
) -> dict[str, object]:
    """Silver-pretrain the span-pair head (+ direction features), then k-fold gold FT.

    With ``save_final=True`` a model is additionally trained on **all** gold (no
    held-out fold), same recipe, and saved to ``RELATION_MODEL_DIR`` as a torch
    ``state_dict`` + a JSON config — the shippable RE model for standalone
    inference (``launch`` / ``infer``). The CV numbers above are the honest eval;
    this is the model those numbers describe, trained on everything.
    """
    import os
    from collections import namedtuple

    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    import torch
    import torch.nn.functional as F  # noqa: N812
    from transformers import AutoTokenizer, get_linear_schedule_with_warmup

    from oikonomia.labeling.score import build_report
    from oikonomia.relations.data import entities_of, read_ner_jsonl, relations_of
    from oikonomia.relations.decode import constrain
    from oikonomia.relations.encode import (
        NO_RELATION,
        admissible_mask,
        char_span_to_token_range,
        label_candidates,
        window_entities,
    )
    from oikonomia.relations.features import (
        PaymentLexicon,
        context_window,
        direction_features_from_folded,
        fold,
    )

    if backbone.startswith(DAPT_ROOT) and not Path(backbone).is_dir():
        raise SystemExit(f"{backbone} not found — let the DAPT run save full/final first.")
    if loss not in {"ce", "gce"}:
        raise ValueError(f"loss must be 'ce' or 'gce', got {loss!r}")

    # Latest committed push (a warm container keeps its start-of-life mount).
    ner_volume.reload()
    print(f"[{run_name}] training on silver  {_fingerprint(Path(SILVER_VOL).read_bytes())}", flush=True)

    schema = json.loads(Path(LABELS_VOL).read_text(encoding="utf-8"))
    rel_labels: list[str] = schema["relation_labels"]
    rel_label2id: dict[str, int] = schema["relation_label2id"]
    entity_labels: list[str] = schema["entity_labels"]
    ent2id = {lab: i for i, lab in enumerate(entity_labels)}
    no_rel_id = rel_label2id[NO_RELATION]
    device = "cuda"

    tokenizer = AutoTokenizer.from_pretrained(backbone, use_fast=True)
    lex = PaymentLexicon(**payment_lex) if payment_lex else PaymentLexicon()

    # A candidate carries: head/tail token ranges, a WIDE context token range
    # (pad-before-payer → amount-end, for the direction verb), entity type ids,
    # the 3 neuro-symbolic direction feature ids (verb-class, verb-position,
    # payer-marking), entity indices + labels (for masked decoding), the target,
    # and whether it trains (low-confidence silver positives are withheld).
    Cand = namedtuple(
        "Cand", "h t h0 h1 t0 t1 w0 w1 htid ttid vc vp pm hlab tlab label_id train_ok"
    )
    Doc = namedtuple("Doc", "input_ids attention_mask ents rels cands")

    def encode_doc(d: dict) -> Doc | None:
        text = str(d.get("text", ""))
        enc = tokenizer(text, truncation=True, max_length=seq_len, return_offsets_mapping=True)
        offsets = [tuple(o) for o in enc["offset_mapping"]]
        all_ents = entities_of(d)

        # Window to the (truncated) token span BEFORE candidate generation. The
        # model cannot see entities past 512 tokens, so this is both correct and
        # the bound that keeps the O(n²) pairing from exploding on the giant silver
        # registers (~45k entities). Gold docs fit whole, so nothing is dropped.
        ranges_all = [char_span_to_token_range(offsets, s, e) for s, e, _ in all_ents]
        ents, ranges, rels, old2new = window_entities(all_ents, relations_of(d), ranges_all)
        if not ents:
            return None
        conf = {}
        for r in d.get("relations") or []:
            h, t = int(r["head"]), int(r["tail"])
            if h in old2new and t in old2new:
                conf[(old2new[h], old2new[t], str(r["type"]))] = float(r.get("confidence", 1.0))

        folded = fold(text)
        cands: list = []
        for h, t, ty in label_candidates(ents, rels):
            rh, rt = ranges[h], ranges[t]  # both valid — every kept entity has a range
            hc, tc = (ents[h][0], ents[h][1]), (ents[t][0], ents[t][1])  # char spans
            wlo, whi = context_window(hc, tc)
            wr = char_span_to_token_range(offsets, wlo, whi) or (min(rh[0], rt[0]), max(rh[1], rt[1]))
            f = direction_features_from_folded(folded, hc, tc, lex)
            hlab, tlab = ents[h][2], ents[t][2]
            train_ok = not (ty != NO_RELATION and conf.get((h, t, ty), 1.0) < min_confidence)
            cands.append(Cand(h, t, rh[0], rh[1], rt[0], rt[1], wr[0], wr[1],
                              ent2id[hlab], ent2id[tlab], f.verb_class, f.verb_pos, f.payer_mark,
                              hlab, tlab, rel_label2id[ty], train_ok))
        if not cands:
            return None
        return Doc(enc["input_ids"], enc["attention_mask"], ents, rels, cands)

    silver_docs = [x for x in (encode_doc(d) for d in read_ner_jsonl(Path(SILVER_VOL))) if x]
    gold_docs = [x for x in (encode_doc(d) for d in read_ner_jsonl(Path(GOLD_VOL))) if x]
    print(f"[{run_name}] backbone={backbone} loss={loss} min_conf={min_confidence} "
          f"rel_labels={len(rel_labels)} ent_labels={len(entity_labels)} "
          f"silver_docs={len(silver_docs)} gold_docs={len(gold_docs)} k={k_folds}", flush=True)

    model = build_relation_head(
        backbone=backbone,
        n_entity_labels=len(entity_labels),
        n_rel_labels=len(rel_labels),
        type_dim=type_dim,
        feat_dim=feat_dim,
        dropout=dropout,
    ).to(device)
    pad_id = tokenizer.pad_token_id or 0

    def batched(exs, size, shuffle, generator=None):
        idx = (torch.randperm(len(exs), generator=generator).tolist() if shuffle
               else list(range(len(exs))))
        for i in range(0, len(idx), size):
            yield [exs[j] for j in idx[i:i + size]]

    def pad_batch(batch):
        maxlen = max(len(d.input_ids) for d in batch)
        ids = torch.full((len(batch), maxlen), pad_id, dtype=torch.long)
        am = torch.zeros((len(batch), maxlen), dtype=torch.long)
        for b, d in enumerate(batch):
            n = len(d.input_ids)
            ids[b, :n] = torch.tensor(d.input_ids)
            am[b, :n] = torch.tensor(d.attention_mask)
        return ids.to(device), am.to(device)

    ce_weight = torch.ones(len(rel_labels), device=device)
    ce_weight[no_rel_id] = no_relation_weight

    def step_loss(batch):
        ids, am = pad_batch(batch)
        h, cls = model.encode(ids, am)
        logits, targets = [], []
        for b, d in enumerate(batch):
            train_cands = [c for c in d.cands if c.train_ok]
            if not train_cands:
                continue
            logits.append(model.score_pairs(h[b], cls[b], train_cands))
            targets.extend(c.label_id for c in train_cands)
        if not logits:
            return None
        logit = torch.cat(logits, dim=0)
        target = torch.tensor(targets, device=device)
        if loss == "gce":
            py = F.softmax(logit, dim=-1).gather(1, target.unsqueeze(1)).squeeze(1).clamp_min(1e-7)
            return ((1.0 - py**gce_q) / gce_q).mean()
        return F.cross_entropy(logit, target, weight=ce_weight)

    def run(exs, *, lr, max_steps=None, epochs=None, tag, gen=None):
        model.train()
        n_batches = (len(exs) + batch_docs - 1) // batch_docs
        total = max_steps if max_steps is not None else epochs * max(1, n_batches)
        opt = torch.optim.AdamW(model.parameters(), lr=lr)
        sched = get_linear_schedule_with_warmup(opt, int(warmup_ratio * total), total)
        step = 0
        while step < total:
            for batch in batched(exs, batch_docs, shuffle=True, generator=gen):
                loss_val = step_loss(batch)
                if loss_val is not None:
                    opt.zero_grad()
                    loss_val.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step()
                    sched.step()
                    if tag and step % 100 == 0:
                        print(f"[{run_name}] {tag} {step:>4}/{total} loss "
                              f"{loss_val.item():6.3f}", flush=True)
                step += 1
                if step >= total:
                    break

    mask_cache: dict[tuple[str, str], torch.Tensor] = {}

    def mask_for(hlab, tlab):
        key = (hlab, tlab)
        if key not in mask_cache:
            mask_cache[key] = torch.tensor(admissible_mask(hlab, tlab), device=device)
        return mask_cache[key]

    @torch.no_grad()
    def predict(docs):
        """Per-doc decode → (gold_ents, gold_rels, gold_ents, pred_rels) tuples.

        Each candidate's winning admissible type carries its softmax probability;
        schema-constrained decoding then keeps the best tail per functional head.
        """
        model.eval()
        per_doc = []
        for d in docs:
            ids, am = pad_batch([d])
            h, cls = model.encode(ids, am)
            logits = model.score_pairs(h[0], cls[0], d.cands)  # [P, n]
            scored = []  # (h, t, type, score) for the non-NO_RELATION winners
            for k, c in enumerate(d.cands):
                masked = logits[k].masked_fill(~mask_for(c.hlab, c.tlab), float("-inf"))
                prob = torch.softmax(masked, dim=-1)
                lid = int(prob.argmax().item())
                if lid != no_rel_id:
                    scored.append((c.h, c.t, rel_labels[lid], float(prob[lid].item())))
            pred_rels = (
                constrain(scored) if constrain_decode else [(h, t, ty) for h, t, ty, _ in scored]
            )
            per_doc.append((d.ents, d.rels, d.ents, pred_rels))
        model.train()
        return per_doc

    def report(per_doc):
        return build_report(n_docs=len(per_doc), n_docs_scored=len(per_doc), per_doc=per_doc)

    # --- Silver stage (once) ---
    gen = torch.Generator().manual_seed(seed)
    run(silver_docs, lr=silver_lr, max_steps=silver_max_steps, tag="silver", gen=gen)
    silver_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    print(f"[{run_name}] silver done — starting {k_folds}-fold gold fine-tuning", flush=True)

    # --- Paired k-fold gold fine-tuning ---
    order = torch.randperm(len(gold_docs), generator=torch.Generator().manual_seed(seed)).tolist()
    folds = [order[i::k_folds] for i in range(k_folds)]
    so_pool, sg_pool = [], []
    for i, held in enumerate(folds):
        held_set = set(held)
        train_docs = [gold_docs[j] for j in range(len(gold_docs)) if j not in held_set]
        held_docs = [gold_docs[j] for j in held]
        model.load_state_dict(silver_state)
        so = predict(held_docs)  # silver-only
        run(train_docs, lr=gold_lr, epochs=gold_epochs, tag="")
        sg = predict(held_docs)  # silver→gold
        so_pool += so
        sg_pool += sg
        print(f"[{run_name}] fold {i + 1}/{k_folds} (n={len(held)}): "
              f"silver-only {report(so).relations.f1:.3f} → "
              f"silver+gold {report(sg).relations.f1:.3f}", flush=True)

    so_rep, sg_rep = report(so_pool), report(sg_pool)
    so_by = {r.label: r.f1 for r in so_rep.relations.by_type}
    sg_by = {r.label: r.f1 for r in sg_rep.relations.by_type}
    result: dict[str, object] = {
        "run": run_name, "backbone": backbone, "loss": loss, "min_confidence": min_confidence,
        "silver_only": {"f1": so_rep.relations.f1, "precision": so_rep.relations.precision,
                        "recall": so_rep.relations.recall, "by_type": so_by},
        "silver_gold": {"f1": sg_rep.relations.f1, "precision": sg_rep.relations.precision,
                        "recall": sg_rep.relations.recall, "by_type": sg_by},
        "delta_f1": round(sg_rep.relations.f1 - so_rep.relations.f1, 4),
    }

    print(f"\n[{run_name}] === RELATIONS ({k_folds}-fold CV, loss={loss}) ===", flush=True)
    print(f"[{run_name}] silver-only : F1 {so_rep.relations.f1:.3f}  "
          f"P {so_rep.relations.precision:.3f}  R {so_rep.relations.recall:.3f}")
    print(f"[{run_name}] silver→gold : F1 {sg_rep.relations.f1:.3f}  "
          f"P {sg_rep.relations.precision:.3f}  R {sg_rep.relations.recall:.3f}"
          f"   (Δ F1 {result['delta_f1']:+.3f})")
    for ty in sorted(set(so_by) | set(sg_by)):
        print(f"[{run_name}]   {ty:14} {so_by.get(ty, 0.0):.3f} → {sg_by.get(ty, 0.0):.3f}")
    print(f"[{run_name}] RESULT {json.dumps(result, ensure_ascii=False)}", flush=True)

    if save_final:
        # Retrain silver→ALL gold (no held-out fold), identical recipe, and persist
        # the custom model. The encoder weights live in the state_dict, so inference
        # rebuilds the architecture from the BASE backbone and loads these over it —
        # no DAPT volume needed at inference time.
        model.load_state_dict(silver_state)
        run(gold_docs, lr=gold_lr, epochs=gold_epochs, tag="final")
        out = Path(RELATION_MODEL_DIR)
        out.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), out / "relation_head.pt")
        cfg = {
            "reconstruct_backbone": BACKBONES["b0"],  # base arch; trained weights are in the state_dict
            "entity_labels": entity_labels,
            "relation_labels": rel_labels,
            "relation_label2id": rel_label2id,
            "type_dim": type_dim,
            "feat_dim": feat_dim,
            "dropout": dropout,
            "seq_len": seq_len,
        }
        (out / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        ner_volume.commit()
        result["saved_model"] = RELATION_MODEL_DIR
        print(f"[{run_name}] saved shippable RE model (all-gold) → {RELATION_MODEL_DIR}", flush=True)

    return result


@app.local_entrypoint()
def xval(
    backbone: str = "b1",
    loss: str = "ce",
    no_relation_weight: float = 1.0,
    min_confidence: float = 0.0,
    constrain_decode: bool = True,
) -> None:
    """Two-stage CV for one backbone+loss: silver-only vs silver→gold relations.

    ``no_relation_weight`` is the recall lever for the ~24:1 negative imbalance
    (positive candidate rate ≈ 0.04); ``min_confidence`` drops the low-confidence
    silver positives from the loss; ``constrain_decode`` applies the functional
    schema constraints at inference. The mined payment verb lexicon is shipped as
    features for the direction head (loaded here, since resources/ is not in the
    container image).
    """
    from oikonomia.relations.features import load_payment_lexicon

    if backbone not in BACKBONES:
        raise SystemExit(f"backbone must be one of {sorted(BACKBONES)}, got {backbone!r}")
    payment_lex = load_payment_lexicon(REPO / "resources").model_dump()
    run = f"{backbone}-{loss}"
    print(json.dumps(
        train.remote(
            run_name=run,
            backbone=BACKBONES[backbone],
            loss=loss,
            no_relation_weight=no_relation_weight,
            min_confidence=min_confidence,
            constrain_decode=constrain_decode,
            payment_lex=payment_lex,
        ),
        indent=2, ensure_ascii=False,
    ))


# --- (c) standalone RE inference on NER-predicted entities + (d) end-to-end eval

# The corpus-scale NER run's output on the shared Volume (keyed by stem == gold doc_id).
PRED_CORPUS_VOL = f"{VOL_ROOT}/predictions/ner_corpus.jsonl"


@app.function(gpu=GPU, volumes={VOL_ROOT: ner_volume}, timeout=3600)
def evaluate_e2e_remote(
    payment_lex: dict[str, list[str]] | None = None,
    constrain_decode: bool = True,
    seq_len: int = 512,
) -> dict[str, object]:
    """Run the saved RE model on the gold docs twice and score both vs gold.

    **oracle** = RE given the *gold* entity spans (comparable to ``xval``);
    **end-to-end** = RE given the *NER-predicted* entities (from the corpus run,
    joined by stem). Scoring maps predicted→gold entities by span overlap
    (:func:`score_relations`), so the gap between the two is exactly the
    entity-cascade cost. PARTY_OF is the headline the women step-8 finding rides on.
    """
    from collections import namedtuple

    import torch
    from transformers import AutoTokenizer

    from oikonomia.labeling.score import build_report
    from oikonomia.relations.data import entities_of, read_ner_jsonl, relations_of
    from oikonomia.relations.decode import constrain
    from oikonomia.relations.encode import (
        NO_RELATION,
        admissible_mask,
        char_span_to_token_range,
        label_candidates,
        window_entities,
    )
    from oikonomia.relations.features import (
        PaymentLexicon,
        context_window,
        direction_features_from_folded,
        fold,
    )

    ner_volume.reload()
    device = "cuda"
    if not Path(f"{RELATION_MODEL_DIR}/config.json").is_file():
        raise SystemExit(f"no saved RE model at {RELATION_MODEL_DIR} — run `launch` first.")
    cfg = json.loads(Path(f"{RELATION_MODEL_DIR}/config.json").read_text(encoding="utf-8"))
    model = build_relation_head(
        backbone=cfg["reconstruct_backbone"],
        n_entity_labels=len(cfg["entity_labels"]),
        n_rel_labels=len(cfg["relation_labels"]),
        type_dim=cfg["type_dim"],
        feat_dim=cfg["feat_dim"],
        dropout=cfg["dropout"],
    ).to(device)
    model.load_state_dict(torch.load(f"{RELATION_MODEL_DIR}/relation_head.pt", map_location=device))
    model.eval()

    rel_labels: list[str] = cfg["relation_labels"]
    rel_label2id: dict[str, int] = cfg["relation_label2id"]
    ent2id = {lab: i for i, lab in enumerate(cfg["entity_labels"])}
    no_rel_id = rel_label2id[NO_RELATION]
    tokenizer = AutoTokenizer.from_pretrained(cfg["reconstruct_backbone"], use_fast=True)
    lex = PaymentLexicon(**payment_lex) if payment_lex else PaymentLexicon()

    Cand = namedtuple("Cand", "h t h0 h1 t0 t1 w0 w1 htid ttid vc vp pm hlab tlab")

    def encode(text: str, entities: list):
        """(input_ids, attention_mask, kept_entities, cands) given a doc's entities."""
        enc = tokenizer(text, truncation=True, max_length=seq_len, return_offsets_mapping=True)
        offsets = [tuple(o) for o in enc["offset_mapping"]]
        ranges_all = [char_span_to_token_range(offsets, s, e) for s, e, _ in entities]
        ents, ranges, _, _ = window_entities(entities, [], ranges_all)
        if not ents:
            return None
        folded = fold(text)
        cands: list = []
        for h, t, _ in label_candidates(ents, []):  # no gold rels at inference
            rh, rt = ranges[h], ranges[t]
            hc, tc = (ents[h][0], ents[h][1]), (ents[t][0], ents[t][1])
            wlo, whi = context_window(hc, tc)
            wr = char_span_to_token_range(offsets, wlo, whi) or (min(rh[0], rt[0]), max(rh[1], rt[1]))
            f = direction_features_from_folded(folded, hc, tc, lex)
            hlab, tlab = ents[h][2], ents[t][2]
            cands.append(Cand(h, t, rh[0], rh[1], rt[0], rt[1], wr[0], wr[1],
                              ent2id[hlab], ent2id[tlab], f.verb_class, f.verb_pos, f.payer_mark,
                              hlab, tlab))
        if not cands:
            return None
        return enc["input_ids"], enc["attention_mask"], ents, cands

    mask_cache: dict[tuple[str, str], object] = {}

    def mask_for(hlab: str, tlab: str):
        key = (hlab, tlab)
        if key not in mask_cache:
            mask_cache[key] = torch.tensor(admissible_mask(hlab, tlab), device=device)
        return mask_cache[key]

    @torch.no_grad()
    def predict(text: str, entities: list):
        """(kept_entities, predicted_relations) for a doc given ITS entity spans."""
        enc = encode(text, entities)
        if enc is None:
            return [], []
        ids, am, ents, cands = enc
        h, cls = model.encode(torch.tensor([ids], device=device), torch.tensor([am], device=device))
        logits = model.score_pairs(h[0], cls[0], cands)
        scored = []
        for k, c in enumerate(cands):
            masked = logits[k].masked_fill(~mask_for(c.hlab, c.tlab), float("-inf"))
            prob = torch.softmax(masked, dim=-1)
            lid = int(prob.argmax().item())
            if lid != no_rel_id:
                scored.append((c.h, c.t, rel_labels[lid], float(prob[lid].item())))
        pred = constrain(scored) if constrain_decode else [(a, b, ty) for a, b, ty, _ in scored]
        return ents, pred

    gold_docs = read_ner_jsonl(Path(GOLD_VOL))
    if not Path(PRED_CORPUS_VOL).is_file():
        raise SystemExit(f"{PRED_CORPUS_VOL} absent — run modal_app/ner.py::infer first.")
    pred_by_id: dict[str, list] = {}
    for r in read_ner_jsonl(Path(PRED_CORPUS_VOL)):
        pred_by_id[str(r["stem"])] = [(e["start"], e["end"], e["label"]) for e in r.get("entities", [])]

    oracle_pd, e2e_pd = [], []
    n_missing = 0
    for d in gold_docs:
        text = str(d.get("text", ""))
        gold_ents, gold_rels = entities_of(d), relations_of(d)
        o_ents, o_rels = predict(text, gold_ents)  # oracle: RE on gold entities
        oracle_pd.append((gold_ents, gold_rels, o_ents, o_rels))
        pents = pred_by_id.get(str(d.get("doc_id")))
        if pents is None:
            n_missing += 1
            e2e_pd.append((gold_ents, gold_rels, [], []))
            continue
        p_ents, p_rels = predict(text, pents)  # end-to-end: RE on predicted entities
        e2e_pd.append((gold_ents, gold_rels, p_ents, p_rels))

    o_rep = build_report(n_docs=len(oracle_pd), n_docs_scored=len(oracle_pd), per_doc=oracle_pd)
    e_rep = build_report(n_docs=len(e2e_pd), n_docs_scored=len(e2e_pd), per_doc=e2e_pd)
    o_by = {r.label: r.f1 for r in o_rep.relations.by_type}
    e_by = {r.label: r.f1 for r in e_rep.relations.by_type}
    result: dict[str, object] = {
        "oracle": {"f1": o_rep.relations.f1, "precision": o_rep.relations.precision,
                   "recall": o_rep.relations.recall, "by_type": o_by},
        "end_to_end": {"f1": e_rep.relations.f1, "precision": e_rep.relations.precision,
                       "recall": e_rep.relations.recall, "by_type": e_by},
        "party_of_oracle": o_by.get("PARTY_OF", 0.0),
        "party_of_e2e": e_by.get("PARTY_OF", 0.0),
        "docs": len(gold_docs),
        "docs_missing_pred": n_missing,
    }
    print("\n[eval_e2e] === END-TO-END vs ORACLE (gold docs, saved RE model) ===", flush=True)
    print(f"[eval_e2e] relation F1  oracle {o_rep.relations.f1:.3f} → end-to-end {e_rep.relations.f1:.3f}")
    print(f"[eval_e2e] PARTY_OF F1   oracle {result['party_of_oracle']:.3f} → "
          f"end-to-end {result['party_of_e2e']:.3f}   ({n_missing} docs missing predictions)")
    for ty in sorted(set(o_by) | set(e_by)):
        print(f"[eval_e2e]   {ty:14} {o_by.get(ty, 0.0):.3f} → {e_by.get(ty, 0.0):.3f}")
    print(f"[eval_e2e] RESULT {json.dumps(result, ensure_ascii=False)}", flush=True)
    return result


@app.local_entrypoint()
def eval_e2e(constrain_decode: bool = True) -> None:
    """(c)+(d): run the saved RE model on the gold docs — oracle (gold entities) vs
    end-to-end (NER-predicted entities) — and report the drop, esp. PARTY_OF."""
    from oikonomia.relations.features import load_payment_lexicon

    payment_lex = load_payment_lexicon(REPO / "resources").model_dump()
    print(json.dumps(
        evaluate_e2e_remote.remote(payment_lex=payment_lex, constrain_decode=constrain_decode),
        indent=2, ensure_ascii=False,
    ))


@app.local_entrypoint()
def launch(backbone: str = "b1", loss: str = "ce") -> None:
    """Train the single shippable RE model on all gold and save it to the volume.

    Runs the same paired CV (the honest number) and then, with ``save_final``,
    trains silver→all-gold and persists the custom model to ``RELATION_MODEL_DIR``.
    That saved model is what ``infer`` loads to run RE on NER-predicted entities.
    """
    from oikonomia.relations.features import load_payment_lexicon

    if backbone not in BACKBONES:
        raise SystemExit(f"backbone must be one of {sorted(BACKBONES)}, got {backbone!r}")
    payment_lex = load_payment_lexicon(REPO / "resources").model_dump()
    print(json.dumps(
        train.remote(
            run_name=f"{backbone}-{loss}-release",
            backbone=BACKBONES[backbone],
            loss=loss,
            payment_lex=payment_lex,
            save_final=True,
        ),
        indent=2, ensure_ascii=False,
    ))
