"""Tests for layered configuration loading and path resolution."""

from __future__ import annotations

import pytest

from oikonomia.config import load_settings


def test_local_paths_are_absolute() -> None:
    s = load_settings("local")
    assert s.paths.root.is_absolute()
    assert s.paths.processed.is_absolute()
    # processed lives under the repo root's data/ tier.
    assert s.paths.processed == s.paths.root / "data" / "processed"


def test_dotted_override_applies_and_coerces() -> None:
    s = load_settings("local", overrides=["ingest.idp_git_rev=abc123", "seed=7"])
    assert s.ingest.idp_git_rev == "abc123"
    assert s.seed == 7  # coerced to int, not left as the string "7"


def test_modal_paths_use_volume_root() -> None:
    s = load_settings("modal")
    assert s.paths.root.as_posix() == "/vol/data"
    assert s.paths.processed.as_posix() == "/vol/data/processed"
    assert s.paths.artifacts.as_posix() == "/vol/ckpt"


def test_malformed_override_raises() -> None:
    with pytest.raises(ValueError, match="Malformed override"):
        load_settings("local", overrides=["not_a_kv_pair"])
