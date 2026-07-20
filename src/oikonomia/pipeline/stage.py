"""The deterministic, resumable stage runner.

A :class:`Stage` is a unit of pipeline work (ingest, weak-label, split, …). It
declares its inputs (as a cheap *key*, not a file scan), its parameters, and its
outputs. :func:`run_stage` computes a freshness key from those plus the stage's
``version`` and skips the stage when a matching manifest with intact outputs
already exists — so re-running the pipeline is cheap.

Two things to know:

* **Inputs are a key, not a scan.** The raw corpus is ~2.8 GB; hashing every
  file each run would dominate wall-clock. Ingest stages return the pinned
  idp.data git rev as their ``inputs_key`` — cheap and exactly correct.
* **Bump ``version`` when you change a stage's logic.** Freshness is
  ``version + inputs_key + params``; a code change with the same inputs/params
  won't re-run on its own. During development, just pass ``--force``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from oikonomia.config import Settings
from oikonomia.hashing import stable_params_hash
from oikonomia.logging import get_logger
from oikonomia.pipeline.manifest import (
    fingerprint_outputs,
    is_fresh,
    manifest_path,
    read_manifest,
    write_manifest,
)
from oikonomia.schemas.manifest import StageManifest

logger = get_logger(__name__)


@dataclass
class StageContext:
    """Everything a stage needs at run time."""

    settings: Settings
    force: bool = False


@runtime_checkable
class Stage(Protocol):
    """The contract every pipeline stage implements."""

    name: str
    version: str  # bump when the stage's logic changes

    def inputs_key(self, s: Settings) -> str:
        """A cheap, exact fingerprint of the stage's inputs (e.g. a git rev)."""
        ...

    def params(self, s: Settings) -> dict[str, Any]:
        """The effective parameters that affect the stage's output."""
        ...

    def outputs(self, s: Settings) -> list[Path]:
        """Absolute paths this stage writes."""
        ...

    def run(self, ctx: StageContext) -> dict[str, float | int | str]:
        """Do the work; write outputs atomically; return summary stats."""
        ...


def _freshness_key(stage: Stage, s: Settings) -> str:
    return StageManifest(
        stage=stage.name,
        version=stage.version,
        inputs_key=stage.inputs_key(s),
        params_hash=stable_params_hash(stage.params(s)),
    ).freshness_key()


def run_stage(stage: Stage, settings: Settings, *, force: bool = False) -> StageManifest:
    """Run ``stage`` unless a fresh manifest with intact outputs already exists.

    Returns the manifest describing the (new or existing) outputs.
    """
    mpath = manifest_path(settings.paths.manifests, stage.name)
    existing = read_manifest(mpath)
    key = _freshness_key(stage, settings)

    if not force and is_fresh(existing, key, settings.paths.root):
        logger.info(f"stage '{stage.name}': skipped (fresh)")
        assert existing is not None  # is_fresh guarantees this
        return existing

    logger.info(f"stage '{stage.name}': running (force={force})")
    stats = stage.run(StageContext(settings=settings, force=force))

    outs = fingerprint_outputs(stage.outputs(settings), settings.paths.root)
    manifest = StageManifest(
        stage=stage.name,
        version=stage.version,
        inputs_key=stage.inputs_key(settings),
        params_hash=stable_params_hash(stage.params(settings)),
        outputs=outs,
        stats=stats,
    )
    write_manifest(mpath, manifest)
    logger.info(f"stage '{stage.name}': done ({len(outs)} outputs)")
    return manifest
