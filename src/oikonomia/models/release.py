"""What a model release consists of, and whether one is ready to publish.

The Hub push itself is three lines of ``huggingface_hub``; everything that can
actually go wrong happens *before* it — an unverified licence lineage, a checkpoint
missing the file that makes it loadable, a card that never got written, the wrong
repo id. This module holds that pre-flight as pure, testable logic so the CLI is a
thin shell over it and the same checks run in a test as in a real push.

Deliberately laptop-first: the weights are pulled off the Modal volume once
(``modal volume get``) and published from here. Modal is for the GPU work — there
is nothing to gain by round-tripping a local folder and an auth token through a
container to upload files that are already on this disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from oikonomia.models.licensing import assert_releasable

# Every OIKONOMIA artifact descends from this chain — the encoder plus our own
# corpus and gold. The firewall re-verifies it before any upload.
LINEAGE: tuple[str, ...] = ("bowphs/GreBerta", "DDbDP", "oikonomia-gold")


class ReleaseSpec(NamedTuple):
    """One shippable artifact (model or dataset): where its files and card live."""

    name: str  # the public artifact name
    local_dir: str  # files, relative to the repo root
    card: str  # the card, relative to the repo root
    repo_id: str  # default Hub repo id
    required: tuple[str, ...]  # files without which the upload is broken
    extras: tuple[str, ...] = ()  # optional files copied in alongside
    repo_type: str = "model"  # "model" | "dataset"


GRAMMATEUS = ReleaseSpec(
    name="OIKONOMIA-Grammateus",
    local_dir="artifacts/models/grammateus",
    card="resources/release/GRAMMATEUS_CARD.md",
    repo_id="oikonomia/grammateus-grc",
    # A standard HF token-classification model: weights + config + tokenizer.
    required=("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"),
    extras=("data/processed/ner/labels.json",),
    repo_type="model",
)

HOMOLOGIA = ReleaseSpec(
    name="OIKONOMIA-Homologia",
    local_dir="artifacts/models/homologia",
    card="resources/release/HOMOLOGIA_CARD.md",
    repo_id="oikonomia/homologia-grc",
    # NOT a standard HF model: a custom span-pair head, so the state_dict plus the
    # config that `build_relation_head` reads back to rebuild the architecture.
    required=("config.json", "relation_head.pt"),
    repo_type="model",
)

OIKONOMIA_DB = ReleaseSpec(
    name="OIKONOMIA-DB",
    local_dir="data/processed/db",
    card="resources/release/OIKONOMIA_DB_CARD.md",
    repo_id="oikonomia/oikonomia-db",
    required=("monetary.parquet", "prices.parquet", "taxes.parquet", "persons.parquet", "principals.parquet", "autonomy.parquet"),
    repo_type="dataset",
)

MODELS: dict[str, ReleaseSpec] = {"grammateus": GRAMMATEUS, "homologia": HOMOLOGIA, "db": OIKONOMIA_DB}


class NotReadyError(RuntimeError):
    """Raised when a release is incomplete — checked before anything is uploaded."""


def check_ready(root: Path, spec: ReleaseSpec) -> list[Path]:
    """Verify a release is publishable and return the files that will be uploaded.

    Runs the licence firewall first (an NC or unvetted ancestor must block before
    we even look at the weights), then confirms the card exists and every required
    file is present in the local checkpoint. Raises :class:`NotReadyError` naming
    the *first* problem and how to fix it — a half-uploaded repo is worse than a
    refused push.
    """
    assert_releasable(LINEAGE)

    card = root / spec.card
    if not card.is_file():
        raise NotReadyError(f"model card missing: {spec.card}")

    ckpt = root / spec.local_dir
    if not ckpt.is_dir():
        raise NotReadyError(
            f"no local weights at {spec.local_dir} — pull them first:\n"
            f"  mkdir -p {spec.local_dir} && modal volume get oikonomia-ner "
            f"models/<b1|relation>/final {spec.local_dir}"
        )
    missing = [name for name in spec.required if not (ckpt / name).is_file()]
    if missing:
        raise NotReadyError(f"{spec.local_dir} is incomplete — missing {', '.join(missing)}")

    return sorted(p for p in ckpt.iterdir() if p.is_file())


def stage_card(root: Path, spec: ReleaseSpec) -> Path:
    """Copy the model card into the checkpoint as ``README.md`` (the Hub's front page).

    Returns the written path. Kept separate from :func:`check_ready` so a dry run
    inspects a release without touching a single byte on disk.
    """
    readme = root / spec.local_dir / "README.md"
    readme.write_text((root / spec.card).read_text(encoding="utf-8"), encoding="utf-8")
    return readme
