"""The published relation model must load from its own files alone.

Homologia ships as a state_dict plus a config rather than a `transformers`
`AutoModel`, so the loader is the whole reusability story: if it needs the repo
checked out, or silently tolerates a partial state dict, downstream users get
either nothing or fluent nonsense.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oikonomia.relations.model import (
    CONFIG_FILE,
    WEIGHTS_FILE,
    load_config,
    resolve_model_dir,
)

CONFIG = {
    "reconstruct_backbone": "bowphs/GreBerta",
    "entity_labels": ["PERSON", "AMOUNT"],
    "relation_labels": ["NO_RELATION", "PARTY_OF"],
    "relation_label2id": {"NO_RELATION": 0, "PARTY_OF": 1},
    "type_dim": 64,
    "feat_dim": 16,
    "dropout": 0.2,
    "seq_len": 512,
}


def _write(tmp_path: Path, cfg: dict[str, object] | None = CONFIG) -> Path:
    if cfg is not None:
        (tmp_path / CONFIG_FILE).write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def test_local_directory_is_used_as_is(tmp_path: Path) -> None:
    """A path that exists must never trigger a network call."""
    assert resolve_model_dir(_write(tmp_path)) == tmp_path


def test_config_round_trips(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path))
    assert cfg["relation_labels"] == ["NO_RELATION", "PARTY_OF"]
    assert cfg["reconstruct_backbone"] == "bowphs/GreBerta"


def test_missing_config_is_reported_with_its_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=CONFIG_FILE):
        load_config(_write(tmp_path, cfg=None))


@pytest.mark.parametrize("key", ["reconstruct_backbone", "entity_labels", "relation_labels"])
def test_config_missing_a_required_key_is_rejected(tmp_path: Path, key: str) -> None:
    """Each key is load-bearing: the backbone rebuilds the encoder, the label
    lists size the embedding and the classifier. A default would misbuild."""
    partial = {k: v for k, v in CONFIG.items() if k != key}
    with pytest.raises(ValueError, match=key):
        load_config(_write(tmp_path, cfg=partial))


# --- the full load needs the ML stack, which the laptop gate does not install.
# Gate per test, not at module level: that would skip the pure checks above too.

RELEASE_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "models" / "homologia"
needs_weights = pytest.mark.skipif(
    not RELEASE_DIR.is_dir(), reason="release weights not pulled down"
)


@needs_weights
def test_shipped_weights_load_strictly() -> None:
    """`strict=True` against the real shipped files — the check that a rename in
    the architecture would break silently."""
    pytest.importorskip("torch", reason="ML stack is Modal-only")
    from oikonomia.relations.model import load_homologia

    model, cfg = load_homologia(RELEASE_DIR)
    assert not model.training
    assert len(cfg["relation_labels"]) == model.mlp[-1].out_features


@needs_weights
def test_missing_weights_are_reported(tmp_path: Path) -> None:
    pytest.importorskip("torch", reason="ML stack is Modal-only")
    from oikonomia.relations.model import load_homologia

    with pytest.raises(FileNotFoundError, match=WEIGHTS_FILE):
        load_homologia(_write(tmp_path))
