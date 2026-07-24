"""Hand-computed fixtures for the corpus-bootstrapped name→gender gazetteer.

Checks the vote → build → apply loop without the corpus: only decisive/prefix
signals vote, the agreement + attestation thresholds gate an entry, and a built
gazetteer then genders a *bare* name that carries no local marker (the coverage
win), while the in-clause rules still win where they fire.
"""

from __future__ import annotations

from pathlib import Path

from oikonomia.db.name_gender import Votes, build_gazetteer, load_gazetteer, save_gazetteer
from oikonomia.db.persons import classify_gender, name_key


def test_name_key_folds_accents_and_takes_first_token() -> None:
    assert name_key("παρὰ Θαήσιος") == "Θαησιος"
    assert name_key("Πετεσοῦχος") == name_key("Πετεσουχος")


def test_only_decisive_and_prefix_bases_vote() -> None:
    v = Votes()
    v.add("Αὐρηλία", " ἡ καὶ")  # nomen → female vote
    v.add("Πετεσοῦχος", " τοῦ Ὥρου")  # egypt_prefix → male vote
    v.add("Σαραπίων", " τοῦ καὶ")  # gazetteer basis → must NOT vote (circular)
    tallies = {k: (nf, nm) for k, nf, nm in v.tallies()}
    assert tallies.get("Αυρηλια") == (1, 0)
    assert tallies.get("Πετεσουχος") == (0, 1)
    assert "Σαραπιων" not in tallies  # gazetteer votes are excluded


def test_build_applies_attestation_and_agreement_thresholds() -> None:
    v = Votes()
    for _ in range(4):
        v.add("Ταῆσις", " ἀπὸ κώμης")  # 4 female (egypt_prefix)
    v.add("Ἀμμώνιος", " τοῦ Διον")  # 1 male — below min_attest
    # a genuinely split form: 2 female, 2 male → fails agreement
    for _ in range(2):
        v.add("Ταῆσιν", " μετὰ κυρίου")  # female (guardian)
    v.add("Ταῆσιν", " υἱὸς Ὥρου")  # male (kin) — pollutes agreement
    v.add("Ταῆσιν", " υἱὸς Ὥρου")
    gaz = build_gazetteer(v, min_attest=3, min_agree=0.85)
    assert gaz.get("Ταησις") == "female"  # 4/4 kept
    assert "Αμμωνιος" not in gaz  # only 1 attestation
    assert "Ταησιν" not in gaz  # 2/4 female → below 0.85 agreement


def test_gazetteer_genders_a_bare_name_but_local_rules_still_win() -> None:
    # Ζώιλος carries no local marker and hits no rule → unknown on its own.
    assert classify_gender("Ζώιλος").gender == "unknown"
    # ...but the corpus gazetteer supplies it (the coverage win):
    g = classify_gender("Ζώιλος", after=" τοῦ Ἀπολλωνίου", gazetteer={"Ζωιλος": "male"})
    assert g.gender == "male" and g.basis == "corpus_name"
    # an in-clause guardian still outranks the gazetteer:
    g2 = classify_gender("Ἀπολλώνιος", after=" μετὰ κυρίου", gazetteer={"Απολλωνιος": "male"})
    assert g2.gender == "female" and g2.basis == "guardian"


def test_gazetteer_ignored_when_absent_and_roundtrips(tmp_path: Path) -> None:
    assert classify_gender("Ζώιλος").gender == "unknown"  # no gazetteer, no rule
    path = tmp_path / "name_gender.json"
    save_gazetteer({"Θαησιος": "female", "Ωρος": "male", "junk": "x"}, path)  # junk value dropped on load
    loaded = load_gazetteer(path)
    assert loaded == {"Θαησιος": "female", "Ωρος": "male"}
    assert load_gazetteer(tmp_path / "missing.json") == {}
