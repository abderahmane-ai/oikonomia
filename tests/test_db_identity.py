"""Hand-built fixtures for coreference-lite person collapse (DB packaging)."""

from __future__ import annotations

import unicodedata

import pandas as pd

from oikonomia.db.identity import collapse_to_persons, person_key


def test_person_key_normalizes_case_whitespace_and_unicode() -> None:
    # case + surrounding whitespace fold away
    assert person_key("Ἀπολλωνία", "Πτολεμαίου", 100) == person_key("ἀπολλωνία  ", " πτολεμαίου", 100.0)
    # a name typed in decomposed (NFD) form matches its composed form
    nfd = unicodedata.normalize("NFD", "Ταῆσις")
    assert person_key(nfd, None, None) == person_key("Ταῆσις", None, None)
    # missing father / place key on "" and never merge with specified ones
    _head, father, place = person_key("Ταῆσις", None, None)
    assert (father, place) == ("", "")
    assert person_key("Ταῆσις", "X", 5) != person_key("Ταῆσις", None, None)


def _frame() -> pd.DataFrame:
    # Apollonia daughter of Ptolemaios appears 3× (one a case variant); Thaesis
    # once; a homonymous Apollonia in a different nome once.
    return pd.DataFrame([
        {"head_text": "Ἀπολλωνία", "father_text": "Πτολεμαίου", "place_pleiades": 100, "gender": "female", "guardian": "with", "deal_type": "sale", "century": 2},
        {"head_text": "ἀπολλωνία", "father_text": "πτολεμαίου", "place_pleiades": 100, "gender": "female", "guardian": "without", "deal_type": "loan", "century": 1},
        {"head_text": "Ἀπολλωνία", "father_text": "Πτολεμαίου", "place_pleiades": 100, "gender": "unknown", "guardian": "none", "deal_type": "sale", "century": 3},
        {"head_text": "Ταῆσις", "father_text": "Ὥρου", "place_pleiades": 200, "gender": "female", "guardian": "with", "deal_type": "lease", "century": 2},
        {"head_text": "Ἀπολλωνία", "father_text": "Πτολεμαίου", "place_pleiades": 999, "gender": "female", "guardian": "with", "deal_type": "sale", "century": 2},
    ])


def test_collapse_folds_mentions_into_distinct_people() -> None:
    people = collapse_to_persons(_frame())
    # 5 mentions → 3 distinct (Apollonia@100, Thaesis@200, Apollonia@999)
    assert len(people) == 3
    assert people["n_mentions"].sum() == 5


def test_best_attested_person_aggregates_correctly() -> None:
    people = collapse_to_persons(_frame())
    top = people.iloc[0]  # sorted by n_mentions desc → Apollonia@100 (3 mentions)
    assert top["n_mentions"] == 3
    assert top["gender"] == "female"  # majority of attributed, ignoring the 'unknown'
    assert top["guardian"] == "without"  # a single χωρὶς attestation establishes autonomy
    assert set(top["deal_types"].split("|")) == {"sale", "loan"}
    assert top["first_century"] == 1  # earliest


def test_homonyms_in_different_places_stay_separate() -> None:
    people = collapse_to_persons(_frame())
    apoll = people[people["head_text"].str.casefold() == "ἀπολλωνία"]
    assert set(apoll["place_pleiades"]) == {100, 999}  # two distinct people, not merged


def test_distinct_count_never_exceeds_mentions() -> None:
    df = _frame()
    people = collapse_to_persons(df)
    assert len(people) <= len(df)


def test_empty_frame_yields_empty_person_table() -> None:
    out = collapse_to_persons(pd.DataFrame())
    assert out.empty and "n_mentions" in out.columns


def test_person_id_is_stable_and_tracks_the_key() -> None:
    """The shipped id must be a pure function of the identity key: same person →
    same id on every rebuild, different people → different ids."""
    from oikonomia.db.identity import person_id

    assert person_id("Ἀπολλωνία", "Πτολεμαίου", 100) == person_id("ἀπολλωνία  ", " πτολεμαίου", 100.0)
    assert person_id("Ταῆσις", "X", 5) != person_id("Ταῆσις", None, None)
    assert len(person_id("Ταῆσις", None, None)) == 16


def test_collapsed_table_carries_one_id_per_person() -> None:
    """`person_id` is the documented join key of persons_distinct — it must exist
    and be unique, or every join in the dataset card silently fans out."""
    df = pd.DataFrame({
        "head_text": ["Ταῆσις", "ταῆσις ", "Ἡρακλῆς"],
        "father_text": ["Πτολεμαίου", "πτολεμαίου", None],
        "place_pleiades": [100, 100.0, None],
        "gender": ["female", "female", "male"],
        "guardian": ["with", "without", "none"],
    })
    out = collapse_to_persons(df)
    assert next(iter(out.columns)) == "person_id"
    assert len(out) == 2
    assert out["person_id"].is_unique
