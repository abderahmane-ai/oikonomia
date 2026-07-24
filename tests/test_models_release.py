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
        dest = ckpt / name
        dest.parent.mkdir(parents=True, exist_ok=True)  # some tables live under export/
        dest.write_text("x", encoding="utf-8")


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


def test_dataset_release_sees_files_in_subdirectories(tmp_path: Path) -> None:
    """`upload_folder` is recursive, so the gate must be too.

    The dataset keeps `documents` and `persons_distinct` under export/. A
    non-recursive listing skipped them: the pre-flight under-reported what was
    about to go public, and a push could ship a dataset missing two of the eight
    tables its card documents.
    """
    spec = MODELS["db"]
    _make_release(tmp_path, spec, files=spec.required)
    listed = {str(f.relative_to(tmp_path / spec.local_dir)) for f in check_ready(tmp_path, spec)}
    assert "export/documents.parquet" in listed
    assert "export/persons_distinct.parquet" in listed
    assert listed == set(spec.required)


def test_dataset_missing_an_export_table_blocks_the_push(tmp_path: Path) -> None:
    spec = MODELS["db"]
    _make_release(tmp_path, spec, files=tuple(f for f in spec.required if "persons_distinct" not in f))
    with pytest.raises(NotReadyError, match=re.escape("export/persons_distinct.parquet")):
        check_ready(tmp_path, spec)


def test_interpreter_and_editor_junk_never_reaches_the_hub(tmp_path: Path) -> None:
    """`upload_folder` has no default ignores, so anything sitting in a checkpoint
    directory becomes a file in a public repo. The pre-flight listing and the
    upload must exclude the same set, or the listing lies about what ships."""
    spec = HOMOLOGIA
    _make_release(tmp_path, spec, files=spec.required)
    ckpt = tmp_path / spec.local_dir
    for junk in ("__pycache__/modeling.cpython-312.pyc", ".DS_Store", "stray.pyc"):
        dest = ckpt / junk
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("junk", encoding="utf-8")

    listed = {str(f.relative_to(ckpt)) for f in check_ready(tmp_path, spec)}
    assert listed == set(spec.required), f"junk leaked into the upload listing: {listed - set(spec.required)}"


def test_ignore_patterns_are_shared_by_listing_and_upload() -> None:
    # The CLI passes these straight to `upload_folder`; if the two drifted, the
    # pre-flight would report one thing and the push would do another.
    from oikonomia.cli import release_cmd
    from oikonomia.models import release

    assert release_cmd.IGNORE_PATTERNS is release.IGNORE_PATTERNS
