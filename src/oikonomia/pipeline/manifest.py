"""Read/write pipeline manifests and decide stage freshness."""

from __future__ import annotations

from pathlib import Path

from oikonomia.hashing import sha256_bytes, sha256_file
from oikonomia.schemas.manifest import ArtifactFingerprint, StageManifest


def upstream_key(manifests_dir: Path, *stage_names: str) -> str:
    """Fingerprint upstream stages' outputs, for use as a downstream ``inputs_key``.

    A downstream stage whose ``inputs_key`` is the pinned corpus rev cannot see
    a change in the *code* that produced its actual input. When the EpiDoc
    parser was fixed to honour ``<lb break="no"/>``, ``build_corpus`` re-ran and
    rewrote ``corpus.parquet`` — and ``build_splits`` then reported "skipped
    (fresh)" over text that no longer existed. The corpus rev had not changed,
    and nothing else in the key had.

    Keying on the upstream outputs' sha256s closes that: a rebuilt input is a
    changed input. Stays cheap — the hashes are already in the manifest, so
    nothing is re-read.

    A missing upstream manifest yields a sentinel rather than an error, so the
    downstream stage re-runs (and then fails loudly on the absent file) instead
    of silently treating "no upstream" as fresh.
    """
    parts: list[str] = []
    for name in stage_names:
        m = read_manifest(manifest_path(manifests_dir, name))
        if m is None:
            parts.append(f"{name}@MISSING")
            continue
        outs = ",".join(f"{o.path}:{o.sha256}" for o in m.outputs)
        parts.append(f"{name}@{sha256_bytes(outs.encode())[:16]}")
    return "|".join(parts)


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
