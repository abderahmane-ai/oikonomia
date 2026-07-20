"""Tests for the pinned-revision corpus checkout.

These drive real ``git`` against a local origin repository rather than mocking
subprocess: the bugs this module actually shipped (an opaque error message, and
a checkout that could not recover from being interrupted) were both in how git
behaves, which a mock would have asserted right past.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from oikonomia.ingest.sync import corpus_dir, ensure_corpus


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture
def origin(tmp_path: Path) -> tuple[Path, str]:
    """A local repo standing in for papyri/idp.data. Returns (path, head_sha)."""
    repo = tmp_path / "origin"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "t@example.com", cwd=repo)
    _git("config", "user.name", "t", cwd=repo)

    (repo / "DDbDP").mkdir()
    (repo / "DDbDP" / "1.xml").write_text("<TEI/>")
    (repo / "Translations").mkdir()
    (repo / "Translations" / "1-1.xml").write_text("<TEI/>")
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "corpus", cwd=repo)
    return repo, _git("rev-parse", "HEAD", cwd=repo)


def test_refuses_unpinned_rev(tmp_path: Path) -> None:
    """An empty rev is a hard error: an unpinned corpus is irreproducible."""
    with pytest.raises(ValueError, match="not pinned"):
        ensure_corpus(tmp_path, "file:///nowhere", "")


def test_clones_and_checks_out_pinned_rev(tmp_path: Path, origin: tuple[Path, str]) -> None:
    repo, sha = origin
    resolved = ensure_corpus(tmp_path / "raw", str(repo), sha)

    assert resolved == sha
    target = corpus_dir(tmp_path / "raw")
    assert (target / "DDbDP" / "1.xml").read_text() == "<TEI/>"
    assert (target / "Translations" / "1-1.xml").exists()


def test_is_idempotent(tmp_path: Path, origin: tuple[Path, str]) -> None:
    """Re-running over a complete checkout is a no-op, not an error."""
    repo, sha = origin
    raw = tmp_path / "raw"
    assert ensure_corpus(raw, str(repo), sha) == sha
    assert ensure_corpus(raw, str(repo), sha) == sha
    assert (corpus_dir(raw) / "DDbDP" / "1.xml").exists()


def test_resumes_after_interrupted_checkout(tmp_path: Path, origin: tuple[Path, str]) -> None:
    """The real regression: a checkout killed partway must be recoverable.

    An interrupted checkout leaves the index emptied while the files it already
    wrote stay on disk as untracked. A plain ``git checkout <rev>`` then aborts
    with "untracked working tree files would be overwritten" on every retry.
    """
    repo, sha = origin
    raw = tmp_path / "raw"
    ensure_corpus(raw, str(repo), sha)
    target = corpus_dir(raw)

    # Reproduce the damaged state: index wiped, some files present-but-untracked,
    # others never written at all.
    _git("rm", "-q", "--cached", "-r", ".", cwd=target)
    (target / "Translations" / "1-1.xml").unlink()
    assert (target / "DDbDP" / "1.xml").exists()  # untracked leftover

    assert ensure_corpus(raw, str(repo), sha) == sha
    assert (target / "Translations" / "1-1.xml").read_text() == "<TEI/>"
    assert (target / "DDbDP" / "1.xml").read_text() == "<TEI/>"
    assert _git("status", "--porcelain", cwd=target) == ""


def test_restores_deleted_and_modified_files(tmp_path: Path, origin: tuple[Path, str]) -> None:
    """Raw data is immutable: local edits and deletions are undone, not kept."""
    repo, sha = origin
    raw = tmp_path / "raw"
    ensure_corpus(raw, str(repo), sha)
    target = corpus_dir(raw)

    (target / "DDbDP" / "1.xml").write_text("CLOBBERED")
    (target / "Translations" / "1-1.xml").unlink()

    ensure_corpus(raw, str(repo), sha)
    assert (target / "DDbDP" / "1.xml").read_text() == "<TEI/>"
    assert (target / "Translations" / "1-1.xml").exists()


def test_git_failure_surfaces_stderr(tmp_path: Path) -> None:
    """Failures must carry git's message, not just an exit status."""
    with pytest.raises(RuntimeError) as exc:
        ensure_corpus(tmp_path / "raw", str(tmp_path / "no-such-repo"), "deadbeef")
    assert "git" in str(exc.value)
    assert str(exc.value).strip() != ""
