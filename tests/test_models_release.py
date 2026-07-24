"""A release must refuse to go out broken — these fix what "broken" means.

The upload itself is three lines of `huggingface_hub`; every failure worth
preventing happens before it. A half-uploaded Hub repo (weights but no config, or
a config with no weights) is worse than a refused push: it looks published and
loads for nobody. So `check_ready` is the gate, and it runs the licence firewall
*first* — an NC-tainted lineage must block before we even stat the weights.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from oikonomia.models.licensing import LicenceError
from oikonomia.models.release import (
    GRAMMATEUS,
    HOMOLOGIA,
    MODELS,
    NotReadyError,
    ReleaseSpec,
    check_ready,
    stage_card,
)

REPO = Path(__file__).resolve().parents[1]


def _make_release(root: Path, spec: ReleaseSpec, *, files: tuple[str, ...]) -> None:
    """Lay out a fake release tree: a card plus the named checkpoint files."""
    card = root / spec.card
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("---\nlicense: apache-2.0\n---\n# card\n", encoding="utf-8")
    ckpt = root / spec.local_dir
    ckpt.mkdir(parents=True, exist_ok=True)
    for name in files:
        (ckpt / name).write_text("x", encoding="utf-8")


def test_complete_release_lists_its_upload(tmp_path: Path) -> None:
    _make_release(tmp_path, HOMOLOGIA, files=HOMOLOGIA.required)
    files = check_ready(tmp_path, HOMOLOGIA)
    assert [f.name for f in files] == sorted(HOMOLOGIA.required)


def test_missing_weights_are_named_not_guessed(tmp_path: Path) -> None:
    # config.json present, the actual weights absent — the exact half-release that
    # would otherwise upload as a broken repo.
    _make_release(tmp_path, HOMOLOGIA, files=("config.json",))
    with pytest.raises(NotReadyError, match=re.escape("relation_head.pt")):
        check_ready(tmp_path, HOMOLOGIA)


def test_missing_checkpoint_directory_explains_the_fix(tmp_path: Path) -> None:
    card = tmp_path / GRAMMATEUS.card
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("# card\n", encoding="utf-8")
    with pytest.raises(NotReadyError, match="modal volume get"):
        check_ready(tmp_path, GRAMMATEUS)


def test_missing_card_blocks_the_push(tmp_path: Path) -> None:
    ckpt = tmp_path / HOMOLOGIA.local_dir
    ckpt.mkdir(parents=True)
    for name in HOMOLOGIA.required:
        (ckpt / name).write_text("x", encoding="utf-8")
    with pytest.raises(NotReadyError, match="card"):
        check_ready(tmp_path, HOMOLOGIA)


def test_licence_firewall_runs_before_anything_else(tmp_path: Path) -> None:
    # A tainted lineage must raise LicenceError even when nothing else exists —
    # proving the firewall is not merely the last check before upload.
    tainted = HOMOLOGIA._replace(local_dir="nope", card="nope.md")
    import oikonomia.models.release as rel

    original = rel.LINEAGE
    rel.LINEAGE = ("bowphs/koine-t5",)  # CC-BY-NC-SA
    try:
        with pytest.raises(LicenceError, match="NonCommercial"):
            check_ready(tmp_path, tainted)
    finally:
        rel.LINEAGE = original


def test_stage_card_becomes_the_repo_readme(tmp_path: Path) -> None:
    _make_release(tmp_path, HOMOLOGIA, files=HOMOLOGIA.required)
    readme = stage_card(tmp_path, HOMOLOGIA)
    assert readme.name == "README.md"
    assert readme.read_text(encoding="utf-8") == (tmp_path / HOMOLOGIA.card).read_text(encoding="utf-8")


@pytest.mark.parametrize("key", sorted(MODELS))
def test_shipped_specs_point_at_real_cards(key: str) -> None:
    # The specs are the source of truth for what gets published; their cards must
    # exist in this repository, not just in someone's memory.
    assert (REPO / MODELS[key].card).is_file()
    assert MODELS[key].repo_id.count("/") == 1
