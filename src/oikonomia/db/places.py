"""Resolve Pleiades place ids to human names, for the regional cut of a finding.

The fact table carries ``place_pleiades`` (a numeric id); the readable name and its
administrative level (site / nome) live in the corpus's ``hgv_json``. This scans
that once into a ``{pleiades_id: name}`` lookup so a finding can group by *Pathyris*
rather than *786084*. Site-level ids (the ones the fact table uses) resolve to the
settlement; the nome level is kept separately for a regional roll-up.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from oikonomia.corpus.io import corpus_path, iter_batches


def place_names_from_blobs(blobs: Iterable[str | None]) -> dict[int, str]:
    """Extract ``{pleiades_id: name}`` from HGV ``hgv_json`` strings (first wins)."""
    names: dict[int, str] = {}
    for blob in blobs:
        if not isinstance(blob, str) or not blob:  # skip NaN/None cells
            continue
        for place in json.loads(blob).get("places") or []:
            pid, name = place.get("pleiades_id"), place.get("name")
            if pid is not None and name and int(pid) not in names:
                names[int(pid)] = str(name)
    return names


def load_place_names(processed_root: Path) -> dict[int, str]:
    """Map each Pleiades id in the corpus to its place name (from HGV metadata)."""
    names: dict[int, str] = {}
    for frame in iter_batches(corpus_path(processed_root), ["hgv_json"]):
        for pid, name in place_names_from_blobs(frame["hgv_json"]).items():
            names.setdefault(pid, name)
    return names
