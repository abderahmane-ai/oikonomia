"""Layered, path-resolving configuration.

Configuration is assembled from YAML layers under ``configs/`` and frozen into a
typed :class:`Settings`. No module elsewhere constructs a ``Path`` literal for a
data location — they all read ``settings.paths.*`` — so the same code runs
unchanged locally (``paths.local.yaml``) and inside a Modal container
(``paths.modal.yaml``).

Layer order (lowest precedence first):

1. ``base.yaml``          — shared defaults
2. ``paths.<env>.yaml``   — environment-specific roots (local | modal)
3. dotted overrides       — e.g. ``ingest.idp_git_rev=abc123`` (highest)

All relative paths in the resolved config are interpreted against the repo root
and returned as absolute paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

Env = Literal["local", "modal"]


class Paths(BaseModel):
    """Resolved absolute paths for every data tier."""

    root: Path
    raw: Path
    interim: Path
    processed: Path
    gold: Path
    manifests: Path
    artifacts: Path
    resources: Path
    configs: Path

    def ensure_writable(self) -> None:
        """Create the tiers a run writes to (never touches ``raw``)."""
        for p in (self.interim, self.processed, self.manifests, self.artifacts):
            p.mkdir(parents=True, exist_ok=True)


class IngestConfig(BaseModel):
    """Corpus ingestion parameters. ``idp_git_rev`` is the corpus fingerprint."""

    idp_repo_url: str = "https://github.com/papyri/idp.data.git"
    # Pin an exact commit for reproducibility. Empty means "not yet pinned";
    # the sync stage refuses to run against an unpinned corpus.
    idp_git_rev: str = ""
    gap_placeholder: str = "…"  # single '…' per lacuna; quantity kept in span attrs
    drop_non_greek_langs: bool = True


class Settings(BaseModel):
    """The fully-resolved, typed configuration for a run."""

    env: Env
    seed: int = 20260719
    run_id: str = "default"
    paths: Paths
    ingest: IngestConfig = IngestConfig()


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------
def _repo_root() -> Path:
    """Repo root = two levels above this file (src/oikonomia/config.py)."""
    return Path(__file__).resolve().parents[2]


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _apply_dotted(cfg: dict[str, Any], dotted: str) -> None:
    """Apply one ``a.b.c=value`` override in place (RHS parsed as YAML)."""
    key, sep, raw = dotted.partition("=")
    if not sep:
        msg = f"Malformed override (expected key=value): {dotted!r}"
        raise ValueError(msg)
    node = cfg
    parts = key.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
        if not isinstance(node, dict):
            msg = f"Override path {key!r} traverses a non-mapping"
            raise ValueError(msg)
    node[parts[-1]] = yaml.safe_load(raw)  # so ints/bools/lists parse, not just strings


def _resolve_paths(root: Path, raw_paths: dict[str, Any]) -> Paths:
    """Turn a mapping of tier→relative-path into absolute :class:`Paths`."""

    def abspath(key: str, default: str) -> Path:
        p = Path(raw_paths.get(key, default))
        return p if p.is_absolute() else (root / p)

    return Paths(
        root=root,
        raw=abspath("raw", "data/raw"),
        interim=abspath("interim", "data/interim"),
        processed=abspath("processed", "data/processed"),
        gold=abspath("gold", "data/gold"),
        manifests=abspath("manifests", "data/.manifests"),
        artifacts=abspath("artifacts", "artifacts"),
        resources=abspath("resources", "resources"),
        configs=abspath("configs", "configs"),
    )


def load_settings(
    env: Env = "local",
    overrides: list[str] | None = None,
    *,
    configs_dir: Path | None = None,
) -> Settings:
    """Assemble and validate the configuration for ``env``.

    ``overrides`` is a list of ``key=value`` dotted strings applied after the
    YAML layers, e.g. ``["ingest.idp_git_rev=abc123", "seed=7"]``.
    """
    root = _repo_root()
    cdir = configs_dir or (root / "configs")

    cfg: dict[str, Any] = {}
    cfg = _deep_merge(cfg, _load_yaml(cdir / "base.yaml"))
    cfg = _deep_merge(cfg, _load_yaml(cdir / f"paths.{env}.yaml"))
    for dotted in overrides or []:
        _apply_dotted(cfg, dotted)

    raw_paths = cfg.pop("paths", {}) if isinstance(cfg.get("paths"), dict) else {}
    # base.yaml (or an override) may point the root elsewhere, e.g. a Volume mount.
    root = Path(raw_paths["root"]).resolve() if raw_paths.get("root") else root
    paths = _resolve_paths(root, raw_paths)

    return Settings(env=env, paths=paths, **cfg)
