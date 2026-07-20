"""The single source of truth for idp.data file-path conventions.

All three sub-corpora bucket files by the numeric part of the Trismegistos (TM)
id, but with *different* rules — a fact verified empirically against the live
repository, not assumed:

* **DDbDP**    ``DDbDP/{id // 1000}/{stem}.xml``          (bucket = id // 1000)
* **HGV meta** ``HGV_meta_EpiDoc/HGV{id // 1000 + 1}/{stem}.xml``  (bucket + 1, "HGV" prefix)
* **Translations** ``Translations/{id // 1000}/{id}-{seq}.xml``   (one per translation)

Some DDbDP stems carry a letter suffix (``13a``, ``263b``) marking a sub-document
of one TM id; bucketing uses the numeric part while the filename keeps the
suffix. This module is the *only* place these rules live — everything else joins
by calling here.
"""

from __future__ import annotations

import re

DDBDP_DIR = "DDbDP"
HGV_META_DIR = "HGV_meta_EpiDoc"
TRANSLATIONS_DIR = "Translations"

_STEM = re.compile(r"^(\d+)([a-z]*)$")
_DDBDP_PATH = re.compile(rf"{DDBDP_DIR}/\d+/(\d+)([a-z]*)\.xml$")


def parse_stem(stem: str) -> tuple[int, str]:
    """Split a filename stem into ``(numeric_id, letter_suffix)``.

    ``"100042" -> (100042, "")``; ``"13a" -> (13, "a")``. Raises ``ValueError``
    on a stem that is not ``digits`` optionally followed by lowercase letters.
    """
    m = _STEM.match(stem)
    if not m:
        msg = f"Unrecognised idp.data stem: {stem!r}"
        raise ValueError(msg)
    return int(m.group(1)), m.group(2)


def ddbdp_relpath(stem: str) -> str:
    """Repo-relative path to a DDbDP edition file for ``stem``."""
    numeric, _ = parse_stem(stem)
    return f"{DDBDP_DIR}/{numeric // 1000}/{stem}.xml"


def hgv_meta_relpath(stem: str) -> str:
    """Repo-relative path to the HGV metadata file for ``stem``.

    Note the bucket is ``id // 1000 + 1`` with an ``HGV`` prefix — different from
    DDbDP. TM 100042 → ``HGV_meta_EpiDoc/HGV101/100042.xml``.
    """
    numeric, _ = parse_stem(stem)
    return f"{HGV_META_DIR}/HGV{numeric // 1000 + 1}/{stem}.xml"


def translations_bucket(tm_id: int) -> str:
    """Repo-relative directory holding a TM id's translations."""
    return f"{TRANSLATIONS_DIR}/{tm_id // 1000}"


def translation_relpath(tm_id: int, seq: int = 1) -> str:
    """Repo-relative path to the ``seq``-th translation of ``tm_id``.

    Translations are named ``{tm}-{seq}.xml`` (e.g. ``Translations/0/53-1.xml``).
    A document may have several; enumerate the bucket directory to find them all.
    """
    return f"{translations_bucket(tm_id)}/{tm_id}-{seq}.xml"


def tm_from_ddbdp_path(path: str) -> tuple[int, str]:
    """Extract ``(numeric_id, suffix)`` from a DDbDP file path.

    Accepts absolute or relative paths ending in the canonical DDbDP layout.
    Raises ``ValueError`` if the path is not a DDbDP edition file.
    """
    m = _DDBDP_PATH.search(path.replace("\\", "/"))
    if not m:
        msg = f"Not a DDbDP edition path: {path!r}"
        raise ValueError(msg)
    return int(m.group(1)), m.group(2)
