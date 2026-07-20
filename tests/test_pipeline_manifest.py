"""Tests for stage freshness: skip when fresh, rerun on change/force."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from oikonomia.config import Settings, load_settings
from oikonomia.pipeline.manifest import upstream_key
from oikonomia.pipeline.stage import StageContext, run_stage


class _CountingStage:
    """A trivial stage that records how many times it actually ran."""

    name = "counting"
    version = "1"

    def __init__(self) -> None:
        self.runs = 0

    def inputs_key(self, s: Settings) -> str:
        return "static-input"

    def params(self, s: Settings) -> dict[str, Any]:
        return {"seed": s.seed}

    def outputs(self, s: Settings) -> list[Path]:
        return [s.paths.processed / "counting.txt"]

    def run(self, ctx: StageContext) -> dict[str, int]:
        self.runs += 1
        ctx.settings.paths.ensure_writable()
        (ctx.settings.paths.processed / "counting.txt").write_text("ok", encoding="utf-8")
        return {"runs": self.runs}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings("local", overrides=[f"paths.root={tmp_path}", "seed=1"])


def test_runs_then_skips_when_fresh(settings: Settings) -> None:
    stage = _CountingStage()
    run_stage(stage, settings)
    run_stage(stage, settings)
    assert stage.runs == 1  # second call skipped


def test_force_reruns(settings: Settings) -> None:
    stage = _CountingStage()
    run_stage(stage, settings)
    run_stage(stage, settings, force=True)
    assert stage.runs == 2


def test_param_change_reruns(tmp_path: Path) -> None:
    stage = _CountingStage()
    run_stage(stage, load_settings("local", overrides=[f"paths.root={tmp_path}", "seed=1"]))
    # A different seed changes params_hash → not fresh → reruns.
    run_stage(stage, load_settings("local", overrides=[f"paths.root={tmp_path}", "seed=2"]))
    assert stage.runs == 2


def test_deleted_output_reruns(settings: Settings) -> None:
    stage = _CountingStage()
    run_stage(stage, settings)
    (settings.paths.processed / "counting.txt").unlink()
    run_stage(stage, settings)
    assert stage.runs == 2  # missing output invalidates the manifest


class _DownstreamStage:
    """A stage that consumes ``counting``'s output, keyed on it via `upstream_key`."""

    name = "downstream"
    version = "1"

    def __init__(self) -> None:
        self.runs = 0

    def inputs_key(self, s: Settings) -> str:
        return upstream_key(s.paths.manifests, "counting")

    def params(self, s: Settings) -> dict[str, Any]:
        return {}

    def outputs(self, s: Settings) -> list[Path]:
        return [s.paths.processed / "downstream.txt"]

    def run(self, ctx: StageContext) -> dict[str, int]:
        self.runs += 1
        ctx.settings.paths.ensure_writable()
        (ctx.settings.paths.processed / "downstream.txt").write_text("ok", encoding="utf-8")
        return {"runs": self.runs}


def test_downstream_reruns_when_upstream_output_changes(settings: Settings) -> None:
    """The staleness bug this guards against was silent and corrupting.

    `build_splits` keyed on the pinned corpus rev, so when a parser fix rebuilt
    corpus.parquet from the *same* raw files it reported "skipped (fresh)" and
    the splits kept describing text that no longer existed.
    """
    up, down = _CountingStage(), _DownstreamStage()
    run_stage(up, settings)
    run_stage(down, settings)
    assert down.runs == 1

    # Upstream re-runs and writes different content (as a logic fix would).
    up.run = lambda ctx: (  # type: ignore[method-assign]
        (settings.paths.processed / "counting.txt").write_text("CHANGED", encoding="utf-8"),
        {"runs": 2},
    )[1]
    run_stage(up, settings, force=True)

    run_stage(down, settings)
    assert down.runs == 2, "downstream stayed 'fresh' over a rebuilt input"


def test_downstream_still_skips_when_upstream_is_unchanged(settings: Settings) -> None:
    up, down = _CountingStage(), _DownstreamStage()
    run_stage(up, settings)
    run_stage(down, settings)
    # Forcing upstream rewrites byte-identical content → downstream stays fresh.
    run_stage(up, settings, force=True)
    run_stage(down, settings)
    assert down.runs == 1
