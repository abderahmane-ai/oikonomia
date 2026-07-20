"""Stable hashing helpers used for reproducibility and cache freshness.

All hashes are sha256 hex digests. "Stable" means the same logical input yields
the same digest across processes and machines — so dict parameter hashes sort
keys before serialising.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1 << 20  # 1 MiB streaming read


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """sha256 of a file's contents, streamed so large artifacts stay off-heap."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def stable_params_hash(params: dict[str, Any]) -> str:
    """Hash a parameter dict deterministically (sorted keys, compact separators).

    Values must be JSON-serialisable. Non-serialisable values raise ``TypeError``
    at hashing time rather than silently producing a mismatching digest later.
    """
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))
