"""Hand-built tests for the silver labeler's added LFs (no corpus needed).

Patterns are constructed inline so each test isolates one rule from the YAML.
The matcher is empty, so the economic baseline contributes nothing and only the
PERSON/PLACE/TRANSACTION/PERSON_ROLE functions are under test.
"""

from __future__ import annotations

from oikonomia.labeling.lexicon import Lexicon
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.silver import Patterns, SilverLabeler, _derive_place_gazetteer
from oikonomia.schemas.spans import CharSpan


def _labeler(**overrides) -> SilverLabeler:
    patterns = Patterns(
        transaction_stems=["ομολογ", "μισθωσ"],
        role_stems=["γυναικ", "δουλ"],
        role_guarded_stems=["κυρι"],
        role_guard_determiners=["μετα", "χωρις"],
        role_determiners=["τησ", "του"],
        place_admin_stems=["κωμ", "πολε", "κληρου"],
        place_prepositions=["εν", "εισ"],
        place_gazetteer_stems=["αλεξανδρ"],
        name_bridge_articles=["του", "τησ"],
        name_bridge_junior=["νεωτερου"],
        name_alias_pronouns=["ο", "οσ"],
        titulature_stems=["σεβαστ", "αυτοκρατ", "καισ"],
        party_prepositions=["παρα"],
        age_marker_stems=["ετων"],
    )
    for k, v in overrides.items():
        setattr(patterns, k, v)
    return SilverLabeler(Matcher(Lexicon(entries=[])), patterns)


def _label(text: str, *, numerals=None, lines=None):
    lab = _labeler()
    nums = [CharSpan(start=a, end=b) for a, b in (numerals or [])]
    lns = lines if lines is not None else [CharSpan(start=0, end=len(text))]
    result = lab.label(text, nums, lns)
    return [(e.text, e.label) for e in result.entities]


def test_lone_capitalised_token_is_person():
    ents = _label("ἔγραψεν Ἀπολλώνιος")
    assert ("Ἀπολλώνιος", "PERSON") in ents


def test_filiation_with_article_is_one_person():
    ents = _label("Ὧρος τοῦ Πετεῦτος ἔδωκεν")
    persons = [t for t, lab in ents if lab == "PERSON"]
    assert persons == ["Ὧρος τοῦ Πετεῦτος"]


def test_bare_kai_splits_two_parties():
    ents = _label("Ἀπολλώνιος καὶ Δίδυμος")
    persons = {t for t, lab in ents if lab == "PERSON"}
    assert persons == {"Ἀπολλώνιος", "Δίδυμος"}


def test_alias_formula_is_one_person():
    ents = _label("Κιαλῆς ὃς καὶ Νεφερῶς ἔδωκεν")
    persons = [t for t, lab in ents if lab == "PERSON"]
    assert persons == ["Κιαλῆς ὃς καὶ Νεφερῶς"]


def test_standalone_titulature_is_not_a_person():
    ents = _label("ἔτους δεκάτου Αὐτοκράτορος Σεβαστοῦ")
    assert not [t for t, lab in ents if lab == "PERSON"]


def test_ruler_name_keeps_its_titulature():
    ents = _label("Ἁδριανοῦ Σεβαστοῦ ἔτους")
    persons = [t for t, lab in ents if lab == "PERSON"]
    assert persons == ["Ἁδριανοῦ Σεβαστοῦ"]


def test_place_from_following_admin_noun():
    ents = _label("ἀπὸ Ὀξυρύγχων πόλεως")
    assert ("Ὀξυρύγχων πόλεως", "PLACE") in ents


def test_place_from_preceding_admin_noun():
    ents = _label("ἐν κώμῃ Καρανίδι")
    places = [t for t, lab in ents if lab == "PLACE"]
    assert places == ["κώμῃ Καρανίδι"]


def test_kleros_parcel_is_place_including_kleros():
    ents = _label("ἐκ τοῦ Εἰρηναίου κλήρου")
    assert ("Εἰρηναίου κλήρου", "PLACE") in ents


def test_gazetteer_toponym_is_place_not_person():
    ents = _label("ἔγραψεν ἀπὸ Ἀλεξανδρείας")
    assert ("Ἀλεξανδρείας", "PLACE") in ents
    assert not [t for t, lab in ents if lab == "PERSON"]


def test_transaction_stem_lowercase_only():
    ents = _label("ὁμολογῶ ἔχειν")
    assert ("ὁμολογῶ", "TRANSACTION") in ents


def test_one_transaction_per_document():
    ents = _label("ὁμολογῶ καὶ ὁμολογοῦμεν")
    assert sum(1 for _, lab in ents if lab == "TRANSACTION") == 1


def test_guarded_role_only_in_guardian_formula():
    with_guard = _label("μετὰ κυρίου Ὥρου")
    assert ("μετὰ κυρίου", "PERSON_ROLE") in with_guard
    bare = _label("ὁ κύριος ἔγραψεν")  # 'lord', not a guardian
    assert not [t for t, lab in bare if lab == "PERSON_ROLE"]


def test_ordinary_role_with_determiner():
    ents = _label("τῆς γυναικὸς αὐτοῦ")
    assert ("τῆς γυναικὸς", "PERSON_ROLE") in ents


def test_place_gazetteer_derivation_excludes_ambiguous_forms():
    dist = {
        "ταλι": {"PLACE": 40, "PERSON": 1},       # toponym, almost never a person
        "ηρακλειδου": {"PLACE": 5, "PERSON": 95},  # eponymous — mostly a person
        "rare": {"PLACE": 2, "PERSON": 0},         # too few occurrences
    }
    gaz = _derive_place_gazetteer(dist, 5, 0.75, 0.15)
    assert "ταλι" in gaz
    assert "ηρακλειδου" not in gaz  # ambiguous name stays out
    assert "rare" not in gaz  # below min_count


def test_place_gazetteer_promotes_person_to_place():
    patterns = _labeler().p
    # "Ταλι" would default to PERSON (capitalised, no admin context); the
    # gazetteer promotes it because the corpus shows it is a toponym.
    lab = SilverLabeler(
        Matcher(Lexicon(entries=[])), patterns, label_dist={"ταλι": {"PLACE": 40, "PERSON": 1}}
    )
    text = "ἔγραψεν Ταλι"
    ents = [(e.text, e.label) for e in lab.label(text, [], [CharSpan(start=0, end=len(text))]).entities]
    assert ("Ταλι", "PLACE") in ents


def test_confidence_reflects_corpus_share():
    patterns = _labeler().p
    # Δίδυμος is person-dominant in the corpus table → stays PERSON, confidence
    # is its person share (9/10).
    lab = SilverLabeler(
        Matcher(Lexicon(entries=[])),
        patterns,
        label_dist={"διδυμοσ": {"PERSON": 9, "PLACE": 1}},
    )
    text = "ἔγραψεν Δίδυμος"
    ent = next(e for e in lab.label(text, [], [CharSpan(start=0, end=len(text))]).entities)
    assert ent.label == "PERSON"
    assert abs(ent.confidence - 0.9) < 1e-6


def test_confidence_unseen_form_gets_prior():
    from oikonomia.labeling.silver import UNSEEN_DIST_PRIOR

    lab = SilverLabeler(Matcher(Lexicon(entries=[])), _labeler().p, label_dist={})
    text = "ἔγραψεν Ἀπολλώνιος"
    ent = next(e for e in lab.label(text, [], [CharSpan(start=0, end=len(text))]).entities)
    assert ent.confidence == UNSEEN_DIST_PRIOR


def test_party_of_links_preposition_introduced_person():
    lab = _labeler()
    text = "ὁμολογῶ παρὰ Πανίσκου"
    result = lab.label(text, [], [CharSpan(start=0, end=len(text))])
    labels = {e.label for e in result.entities}
    assert "TRANSACTION" in labels and "PERSON" in labels
    assert any(r.type == "PARTY_OF" for r in result.relations)
