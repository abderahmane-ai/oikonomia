"""The licence firewall must fail-closed. These fix the one release-blocking rule:
no NonCommercial ancestor is ever publishable, and an unknown lineage is refused
rather than trusted.
"""

from __future__ import annotations

import pytest

from oikonomia.models.licensing import LicenceError, assert_releasable, is_noncommercial


def test_grebertan_lineage_is_releasable() -> None:
    # B1 = GreBerta (apache-2.0) + our DDbDP/gold data → clean, no exception.
    assert assert_releasable(["bowphs/GreBerta", "DDbDP", "oikonomia-gold"]) is None


def test_noncommercial_ancestor_is_refused() -> None:
    with pytest.raises(LicenceError, match="NonCommercial"):
        assert_releasable(["bowphs/koine-t5"])
    with pytest.raises(LicenceError, match="NonCommercial"):
        assert_releasable(["bowphs/GreBerta", "bowphs/koine-t5-omni"])  # NC anywhere blocks


def test_unknown_ancestor_fails_closed() -> None:
    # An un-vetted id must block the push, not slip through.
    with pytest.raises(LicenceError, match="allowlist"):
        assert_releasable(["some/unvetted-model"])


def test_empty_lineage_fails_closed() -> None:
    with pytest.raises(LicenceError):
        assert_releasable([])


def test_sharealike_ancestor_is_allowed() -> None:
    # koineformer is CC-BY-SA (ShareAlike, commercial-OK) — releasable.
    assert assert_releasable(["bowphs/koineformer"]) is None


def test_is_noncommercial_detects_nc_terms() -> None:
    assert is_noncommercial("cc-by-nc-sa-4.0")
    assert is_noncommercial("CC-BY-NC-4.0")
    assert not is_noncommercial("apache-2.0")
    assert not is_noncommercial("cc-by-sa-4.0")
