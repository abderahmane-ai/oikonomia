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
        payment_receiver_stems=["εσχηκ", "απεχ", "εχειν"],
        payment_giver_stems=["μεμετρηκ", "διεγραψ"],
        payment_impersonal_stems=["τετακ"],
        dative_endings=["ωι", "ω", "αι", "ι"],
        official_stems=["αγορανομ"],
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


def test_age_numeral_after_etwn_is_age():
    # "(ὡς) ἐτῶν N" = "N years old"; the numeral is AGE, not the DATE_REF the
    # baseline would emit for the year-word ἐτῶν.
    ents = _label("ὡς ἐτῶν λη", numerals=[(8, 10)])
    assert ("λη", "AGE") in ents
    assert ("ἐτῶν λη", "DATE_REF") not in ents


def test_numeral_before_etwn_is_not_age():
    # "N ἐτῶν" (τεσσάρων ἐτῶν, "four years" — a lease term): the numeral precedes
    # ἐτῶν and must NOT be read as an age.
    ents = _label("τῶν δ ἐτῶν", numerals=[(4, 5)])
    assert ("δ", "AGE") not in ents


def test_party_of_links_preposition_introduced_person():
    lab = _labeler()
    text = "ὁμολογῶ παρὰ Πανίσκου"
    result = lab.label(text, [], [CharSpan(start=0, end=len(text))])
    labels = {e.label for e in result.entities}
    assert "TRANSACTION" in labels and "PERSON" in labels
    assert any(r.type == "PARTY_OF" for r in result.relations)


# --- Payment direction (PAID_BY / PAID_TO) ----------------------------------
# _direction_relations is tested directly with hand-built entities, because the
# amount spans (MONEY_AMOUNT/COMMODITY) it needs come from the lexicon/numeral
# machinery the rest of the pipeline owns; here the interest is the verb→role map.


def _direction(text: str, ents: list[tuple[str, str]]) -> set[tuple[str, str, str]]:
    """Run the direction labeler on hand-placed entities (label, substring)."""
    from oikonomia.labeling.silver import _tokens
    from oikonomia.labeling.weak_rules import WeakEntity

    entities = []
    for label, sub in ents:
        i = text.index(sub)
        entities.append(WeakEntity(label=label, span=CharSpan(start=i, end=i + len(sub)), text=sub))
    rels = _labeler()._direction_relations(entities, _tokens(text))
    return {(r.type, entities[r.head].text, entities[r.tail].text) for r in rels}


def test_receiver_verb_with_para_names_the_payer():
    # 'Ὧρος received from Didymos 100 dr' — subject is payee, παρά is payer.
    rels = _direction(
        "Ὧρος ἐσχηκέναι παρὰ Δίδυμος δραχμὰς ρ",
        [("PERSON", "Ὧρος"), ("PERSON", "Δίδυμος"), ("MONEY_AMOUNT", "ρ")],
    )
    assert ("PAID_BY", "Δίδυμος", "ρ") in rels
    assert ("PAID_TO", "Ὧρος", "ρ") in rels


def test_giver_verb_subject_is_payer_dative_is_payee():
    # 'Horos measured out to Didymos wheat' — subject pays, dative receives.
    rels = _direction(
        "μεμέτρηκεν Ὧρος Διδύμωι πυροῦ",
        [("PERSON", "Ὧρος"), ("PERSON", "Διδύμωι"), ("COMMODITY", "πυροῦ")],
    )
    assert ("PAID_BY", "Ὧρος", "πυροῦ") in rels
    assert ("PAID_TO", "Διδύμωι", "πυροῦ") in rels


def test_agent_of_para_is_not_the_payer():
    # 'ὁ παρὰ Σώσου' is Sosos' clerk (article before παρά), never the payer.
    rels = _direction(
        "Ὧρος ἐσχηκέναι δραχμὰς ρ ὁ παρὰ Σώσου",
        [("PERSON", "Ὧρος"), ("MONEY_AMOUNT", "ρ"), ("PERSON", "Σώσου")],
    )
    assert not any(t == "PAID_BY" and h == "Σώσου" for t, h, _ in rels)
    assert ("PAID_TO", "Ὧρος", "ρ") in rels


def test_official_after_para_name_is_excluded():
    # 'παρὰ Σώσου ἀγορανόμου' — the dating official, not a payer.
    rels = _direction(
        "ἀπέχειν δραχμὰς ρ παρὰ Σώσου ἀγορανόμου",
        [("MONEY_AMOUNT", "ρ"), ("PERSON", "Σώσου")],
    )
    assert not any(t == "PAID_BY" for t, _, _ in rels)


def test_no_amount_no_direction():
    # 'received the letter from Didymos' — no amount, so not a transfer.
    rels = _direction(
        "ἐσχηκέναι παρὰ Δίδυμος",
        [("PERSON", "Δίδυμος")],
    )
    assert rels == set()


def test_giver_dative_recipient_is_payee_not_payer():
    # 'he paid to Sekoundos (dative) 100 dr' — the dative name by the giver verb
    # is the PAYEE, and must never be taken as the payer.
    rels = _direction(
        "διέγραψε Σεκούνδῳ δραχμὰς ρ",
        [("PERSON", "Σεκούνδῳ"), ("MONEY_AMOUNT", "ρ")],
    )
    assert ("PAID_TO", "Σεκούνδῳ", "ρ") in rels
    assert not any(t == "PAID_BY" and h == "Σεκούνδῳ" for t, h, _ in rels)


def test_para_with_article_names_the_payer():
    # 'received from THE Julius' — an article between παρά and the name.
    rels = _direction(
        "Ὧρος ἐσχηκέναι παρὰ τοῦ Ἰουλίου δραχμὰς ρ",
        [("PERSON", "Ὧρος"), ("PERSON", "Ἰουλίου"), ("MONEY_AMOUNT", "ρ")],
    )
    assert ("PAID_BY", "Ἰουλίου", "ρ") in rels
    assert ("PAID_TO", "Ὧρος", "ρ") in rels


def test_paron_participle_is_not_the_para_preposition():
    # 'Ὧρος being present received 100 dr' — παρών is not παρά, so Ὧρος (before
    # the verb) is the payee, and there is no παρά-marked payer.
    rels = _direction(
        "Ὧρος παρὼν ἐσχηκέναι δραχμὰς ρ",
        [("PERSON", "Ὧρος"), ("MONEY_AMOUNT", "ρ")],
    )
    assert not any(t == "PAID_BY" for t, _, _ in rels)
    assert ("PAID_TO", "Ὧρος", "ρ") in rels


# --- Attribute apposition (HAS_OCCUPATION / HAS_AGE) -------------------------
# The rule is pure (tests/test_apposition.py owns its logic); here the interest is
# the labeler wiring — that WeakRelations come out with the right type and the
# type's provisional confidence, and that the AGE path works end-to-end from a
# numeral the labeler builds itself.


def _attribute(text: str, ents: list[tuple[str, str]]) -> set[tuple[str, str, str, float]]:
    """Run the attribute labeler on hand-placed entities (label, substring)."""
    from oikonomia.labeling.weak_rules import WeakEntity

    entities = []
    for label, sub in ents:
        i = text.index(sub)
        entities.append(WeakEntity(label=label, span=CharSpan(start=i, end=i + len(sub)), text=sub))
    rels = _labeler()._attribute_relations(entities)
    return {(r.type, entities[r.head].text, entities[r.tail].text, round(r.confidence, 3)) for r in rels}


def test_occupation_apposition_emits_has_occupation_with_confidence():
    from oikonomia.labeling.silver import RELATION_CONFIDENCE

    rels = _attribute(
        "Ἀρτεμίδωρος ἰατρός",
        [("PERSON", "Ἀρτεμίδωρος"), ("OCCUPATION", "ἰατρός")],
    )
    assert rels == {("HAS_OCCUPATION", "Ἀρτεμίδωρος", "ἰατρός", RELATION_CONFIDENCE["HAS_OCCUPATION"])}


def test_counted_occupation_gets_no_edge_through_the_labeler():
    # 'ἱερεῖς β' = 'priests: 2' — a headcount line; the guard drops it end-to-end.
    rels = _attribute(
        "Ἀπολλώνιος ἱερεῖς β",
        [("PERSON", "Ἀπολλώνιος"), ("OCCUPATION", "ἱερεῖς"), ("QUANTITY", "β")],
    )
    assert rels == set()


def test_age_links_to_preceding_person_end_to_end():
    # The labeler builds the AGE entity from the numeral after ἐτῶν itself; the
    # attribute rule then links it to the capitalised name before it.
    text = "Φιλουμένη ὡς ἐτῶν λη"
    i = text.index("λη")
    result = _labeler().label(
        text, [CharSpan(start=i, end=i + len("λη"))], [CharSpan(start=0, end=len(text))]
    )
    age_rels = [r for r in result.relations if r.type == "HAS_AGE"]
    assert len(age_rels) == 1
    r = age_rels[0]
    assert result.entities[r.head].text == "Φιλουμένη"
    assert result.entities[r.tail].label == "AGE"
