"""Reproducibility ledger: per-stage manifests and artifact fingerprints.

Every pipeline stage writes a :class:`StageManifest` recording exactly what
produced its outputs — the input fingerprints, a hash of the effective
parameters, the stage's code version, and the sha256 of each output. These
manifests are git-tracked (``data/.manifests/``) and are what makes a run
reproducible and a stale artifact detectable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ArtifactFingerprint(BaseModel):
    """Identity of a single artifact: its path and content hash."""

    path: str  # repo-relative
    sha256: str
    bytes: int = 0


class StageManifest(BaseModel):
    """The record one stage writes after a successful run."""

    stage: str
    version: str
    # Fingerprint of the stage's inputs. For raw-corpus stages this is the
    # pinned idp.data git rev, NOT 68k file digests (cheap and exact).
    inputs_key: str
    params_hash: str
    outputs: list[ArtifactFingerprint] = Field(default_factory=list)
    stats: dict[str, float | int | str] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def freshness_key(self) -> str:
        """The composite key that decides whether a stage may be skipped."""
        return f"{self.stage}@{self.version}|{self.inputs_key}|{self.params_hash}"
