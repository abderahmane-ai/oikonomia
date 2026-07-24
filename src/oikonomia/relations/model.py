"""The span-pair relation architecture, and a one-call loader for OIKONOMIA-Homologia.

Homologia is not a ``transformers`` ``AutoModel``: it is a custom head over a
GreBerta encoder, shipped as a torch ``state_dict`` plus a JSON config. This
module is its canonical definition — the architecture lives in the library, so
the published model stays loadable whether or not ``modal_app/`` exists.

Torch and transformers are imported lazily inside the functions: the rest of the
library must stay importable on a laptop with no ML stack.

    from oikonomia.relations.model import load_homologia

    model, cfg = load_homologia("ainouche-abderahmane/homologia")

Candidate construction (which pairs to score, and the direction features the head
expects) lives in :mod:`oikonomia.relations.encode` and
:mod:`oikonomia.relations.features`; :mod:`oikonomia.relations.infer` wires the
two together for inference over predicted entities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["CONFIG_FILE", "WEIGHTS_FILE", "build_relation_head", "load_homologia"]

CONFIG_FILE = "config.json"
WEIGHTS_FILE = "relation_head.pt"


def build_relation_head(
    *,
    backbone: str,
    n_entity_labels: int,
    n_rel_labels: int,
    type_dim: int = 64,
    feat_dim: int = 16,
    dropout: float = 0.2,
) -> Any:
    """Construct the span-pair relation head.

    The same architecture serves the k-fold CV, the all-gold save, and standalone
    inference on NER-predicted entities.

    Per candidate pair the classifier sees: head/tail max-pooled representations,
    the between-span context, a wide context reaching before the payer (where the
    direction verb sits), CLS, entity-type embeddings, and the three symbolic
    direction features.
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

        def encode(self, input_ids: Any, attention_mask: Any) -> tuple[Any, Any]:
            h = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
            return h, h[:, 0, :]  # token states, CLS

        def score_pairs(self, hb: Any, cls_b: Any, cands: Any) -> Any:
            """Logits ``[P, n_rel_labels]`` for one document's candidate pairs."""
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


def resolve_model_dir(source: str | Path, *, revision: str | None = None) -> Path:
    """Return a local directory holding the model files.

    A path that exists is used as-is; anything else is treated as a Hugging Face
    repo id and downloaded to the local hub cache.
    """
    path = Path(source)
    if path.is_dir():
        return path
    from huggingface_hub import snapshot_download

    return Path(
        snapshot_download(
            repo_id=str(source),
            revision=revision,
            allow_patterns=[CONFIG_FILE, WEIGHTS_FILE],
        )
    )


def load_config(model_dir: Path) -> dict[str, Any]:
    """Read and validate the shipped ``config.json``."""
    cfg_path = model_dir / CONFIG_FILE
    if not cfg_path.is_file():
        raise FileNotFoundError(f"no {CONFIG_FILE} in {model_dir}")
    cfg: dict[str, Any] = json.loads(cfg_path.read_text(encoding="utf-8"))
    missing = [k for k in ("reconstruct_backbone", "entity_labels", "relation_labels") if k not in cfg]
    if missing:
        raise ValueError(f"{cfg_path} is missing required key(s): {', '.join(missing)}")
    return cfg


def load_homologia(
    source: str | Path = "ainouche-abderahmane/homologia",
    *,
    device: str = "cpu",
    revision: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Load OIKONOMIA-Homologia from the Hub or a local directory.

    ``source`` is a Hugging Face repo id or a path to a directory containing
    ``config.json`` and ``relation_head.pt``. Returns the model in ``eval`` mode
    on ``device``, together with the config (label lists, ``seq_len``) that the
    candidate construction in :mod:`oikonomia.relations.infer` needs.

    The state dict is loaded ``strict=True``: a silently half-initialised model
    would score fluent nonsense.
    """
    import torch

    model_dir = resolve_model_dir(source, revision=revision)
    cfg = load_config(model_dir)
    weights = model_dir / WEIGHTS_FILE
    if not weights.is_file():
        raise FileNotFoundError(f"no {WEIGHTS_FILE} in {model_dir}")

    model = build_relation_head(
        backbone=cfg["reconstruct_backbone"],
        n_entity_labels=len(cfg["entity_labels"]),
        n_rel_labels=len(cfg["relation_labels"]),
        type_dim=cfg.get("type_dim", 64),
        feat_dim=cfg.get("feat_dim", 16),
        dropout=cfg.get("dropout", 0.2),
    )
    model.load_state_dict(torch.load(weights, map_location=device), strict=True)
    return model.to(device).eval(), cfg
