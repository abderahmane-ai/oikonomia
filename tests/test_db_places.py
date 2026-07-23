"""Fixtures for the Pleiades place-name resolver (Phase 9)."""

from __future__ import annotations

import json

from oikonomia.db.places import place_names_from_blobs


def test_extracts_pleiades_names_first_wins() -> None:
    blobs = [
        json.dumps({"places": [{"pleiades_id": 786084, "name": "Pathyris", "level": "site"}]}),
        json.dumps({"places": [{"pleiades_id": 786084, "name": "Pathyris (again)"}]}),  # dup, ignored
        json.dumps({"places": [{"pleiades_id": 727122, "name": "Oxyrhynchos"}]}),
    ]
    assert place_names_from_blobs(blobs) == {786084: "Pathyris", 727122: "Oxyrhynchos"}


def test_skips_nome_level_without_pleiades_id_and_empties() -> None:
    blobs = [
        None,
        "",
        json.dumps({"places": [{"trismegistos_geo_id": 2849, "pleiades_id": None, "name": "Pathyrites"}]}),
        json.dumps({"places": []}),
        json.dumps({}),
    ]
    assert place_names_from_blobs(blobs) == {}
