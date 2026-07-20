"""Fetch the idp.data corpus at a pinned git revision.

Reproducibility hinges on pinning: the repository is actively edited, so an
unpinned corpus makes every downstream number irreproducible. This module
refuses to proceed unless ``ingest.idp_git_rev`` is set, and it records the
resolved HEAD sha as the corpus fingerprint carried into every manifest.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from oikonomia.logging import get_logger

logger = get_logger(__name__)

CORPUS_DIRNAME = "idp.data"


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # git puts the actionable message on stderr; CalledProcessError's repr
        # shows only the exit status, which makes failures here unreadable.
        msg = (
            f"git {' '.join(args)} failed (exit {result.returncode})"
            f"\n{result.stderr.strip()}"
        )
        raise RuntimeError(msg)
    return result.stdout.strip()


def corpus_dir(raw_root: Path) -> Path:
    return raw_root / CORPUS_DIRNAME


def ensure_corpus(raw_root: Path, repo_url: str, git_rev: str) -> str:
    """Ensure the corpus is checked out at ``git_rev``; return the resolved sha.

    Clones on first use, otherwise fetches the target rev, then checks it out.
    Raises ``ValueError`` if ``git_rev`` is empty (unpinned corpus).
    """
    if not git_rev:
        msg = (
            "ingest.idp_git_rev is not pinned. Set an exact commit sha in "
            "configs/base.yaml or via --set ingest.idp_git_rev=<sha> before syncing."
        )
        raise ValueError(msg)

    target = corpus_dir(raw_root)
    target.parent.mkdir(parents=True, exist_ok=True)

    if not (target / ".git").is_dir():
        # Blobless partial clone: fetch commit/tree objects now, and only the
        # file blobs actually needed when we check out the pinned rev. Avoids
        # downloading every blob in the repo's multi-GB history.
        logger.info(f"cloning {repo_url} into {target} (blobless)")
        _git("clone", "--no-checkout", "--filter=blob:none", repo_url, str(target))

    logger.info(f"checking out corpus rev {git_rev}")
    _git("fetch", "origin", git_rev, cwd=target)

    # Two-step instead of a plain `checkout`, so an interrupted run is
    # recoverable. A checkout killed partway leaves the index wiped and the
    # already-written files untracked; `git checkout <rev>` then aborts with
    # "untracked working tree files would be overwritten" and no amount of
    # re-running clears it. `reset --mixed` rebuilds the index from the rev
    # without touching the working tree, and `checkout -- .` materialises only
    # the paths that are missing or altered. Both steps are no-ops once the
    # tree is complete, so this stays idempotent and resumes in place.
    _git("reset", "--mixed", git_rev, cwd=target)
    _git("checkout", "--", ".", cwd=target)
    resolved = _git("rev-parse", "HEAD", cwd=target)
    logger.info(f"corpus ready at {resolved}")
    return resolved
