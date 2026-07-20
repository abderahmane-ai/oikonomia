"""Read/write pipeline manifests and decide stage freshness."""

from __future__ import annotations

from pathlib import Path

from oikonomia.hashing import sha256_file
from oikonomia.schemas.manifest import ArtifactFingerprint, StageManifest


def manifest_path(manifests_dir: Path, stage_name: str) -> Path:
    return manifests_dir / f"{stage_name}.json"


def read_manifest(path: Path) -> StageManifest | None:
    """Load a manifest, or ``None`` if it does not exist or is unreadable."""
    if not path.is_file():
        return None
    try:
        return StageManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # A corrupt manifest is treated as "no manifest": the stage re-runs.
        return None


def write_manifest(path: Path, manifest: StageManifest) -> None:
    """Write a manifest atomically (temp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)


def fingerprint_outputs(paths: list[Path], repo_root: Path) -> list[ArtifactFingerprint]:
    """Hash each existing output and record its repo-relative path and size."""
    prints: list[ArtifactFingerprint] = []
    for p in paths:
        if not p.is_file():
            continue
        rel = p.relative_to(repo_root).as_posix() if p.is_relative_to(repo_root) else str(p)
        prints.append(
            ArtifactFingerprint(path=rel, sha256=sha256_file(p), bytes=p.stat().st_size)
        )
    return prints


def outputs_match(manifest: StageManifest, repo_root: Path) -> bool:
    """True if every recorded output still exists with the recorded sha256."""
    if not manifest.outputs:
        return False
    for fp in manifest.outputs:
        p = repo_root / fp.path
        if not p.is_file() or sha256_file(p) != fp.sha256:
            return False
    return True


def is_fresh(existing: StageManifest | None, candidate_key: str, repo_root: Path) -> bool:
    """A stage is fresh iff its freshness key is unchanged and outputs are intact."""
    if existing is None:
        return False
    if existing.freshness_key() != candidate_key:
        return False
    return outputs_match(existing, repo_root)
