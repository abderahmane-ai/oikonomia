"""Tests for idp.data path conventions (verified against the live repo)."""

from __future__ import annotations

import pytest

from oikonomia.ingest import paths


def test_parse_stem_plain_and_suffixed() -> None:
    assert paths.parse_stem("100042") == (100042, "")
    assert paths.parse_stem("13a") == (13, "a")
    assert paths.parse_stem("263b") == (263, "b")


def test_parse_stem_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="Unrecognised"):
        paths.parse_stem("abc")


def test_ddbdp_bucket_is_id_over_1000() -> None:
    assert paths.ddbdp_relpath("100042") == "DDbDP/100/100042.xml"
    assert paths.ddbdp_relpath("13a") == "DDbDP/0/13a.xml"


def test_hgv_bucket_is_id_over_1000_plus_one() -> None:
    # The HGV asymmetry that would silently break the join if assumed equal.
    assert paths.hgv_meta_relpath("100042") == "HGV_meta_EpiDoc/HGV101/100042.xml"
    assert paths.hgv_meta_relpath("8754") == "HGV_meta_EpiDoc/HGV9/8754.xml"


def test_translation_paths() -> None:
    assert paths.translations_bucket(53) == "Translations/0"
    assert paths.translation_relpath(53, 1) == "Translations/0/53-1.xml"


def test_tm_from_ddbdp_path_roundtrip() -> None:
    assert paths.tm_from_ddbdp_path("DDbDP/100/100042.xml") == (100042, "")
    assert paths.tm_from_ddbdp_path("/abs/DDbDP/0/13a.xml") == (13, "a")


def test_tm_from_ddbdp_path_rejects_non_ddbdp() -> None:
    with pytest.raises(ValueError, match="Not a DDbDP"):
        paths.tm_from_ddbdp_path("HGV_meta_EpiDoc/HGV1/13.xml")
