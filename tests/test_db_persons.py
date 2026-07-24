"""Hand-computed fixtures for deterministic gender attribution (Phase 9).

Each case pins one rule against a real documentary frame, so the precision order
(guardian > nomen > kin > gazetteer > Egyptian prefix) and every guard (the
handoff, the metronymic exclusion, the masculine-inflection veto) is checked
without the corpus. Gender attribution feeds the women-as-principals finding, so
these are the semantics a wrong number would trace back to.
"""

from __future__ import annotations

from oikonomia.db.persons import classify_gender, first_name_token, has_guardian

# --- token cleanup -----------------------------------------------------------


def test_first_name_token_strips_leading_function_words() -> None:
    assert first_name_token("παρὰ Αὐρηλίου Ἄμμωνος") == "Αὐρηλίου"
    assert first_name_token("τῇ Ἀπολλωνίᾳ") == "Ἀπολλωνίᾳ"
    assert first_name_token("καὶ διὰ Θαήσιος") == "Θαήσιος"
    assert first_name_token("Πετεσοῦχος") == "Πετεσοῦχος"


# --- rule 1: guardian formula (only women transact μετὰ / χωρὶς κυρίου) -------


def test_guardian_formula_marks_female() -> None:
    g = classify_gender("Ταῆσις", after=" μετὰ κυρίου τοῦ ἀνδρός")
    assert g.gender == "female" and g.basis == "guardian"
    g2 = classify_gender("Ἀταρι", after=" χωρὶς κυρίου χρηματιζούσης")
    assert g2.gender == "female" and g2.basis == "guardian"


def test_guardian_handoff_does_not_leak_to_prior_coordinated_name() -> None:
    # "Γούνθου καὶ Αταρι χωρὶς κυρίου" — the guardian attaches to Atari, not to
    # the name introducing this window, so has_guardian must reject it here.
    after = " καὶ Αταρι χωρὶς κυρίου χρηματιζούσης"
    assert has_guardian(after) is False
    # ...but with no intervening καί it binds to this name:
    assert has_guardian(" χωρὶς κυρίου χρηματιζούσης") is True


# --- rule 2: Roman nomen (α-declension f, ο-declension m), across cases -------


def test_nomen_gender_by_declension_all_cases() -> None:
    for fem in ("Αὐρηλία", "Αὐρηλίας", "Αὐρηλίᾳ", "Αὐρηλίαν", "Ἰουλία", "Κλαυδία"):
        g = classify_gender(fem)
        assert g.gender == "female" and g.basis == "nomen", fem
    for masc in ("Αὐρήλιος", "Αὐρηλίου", "Αὐρηλίῳ", "Αὐρήλιον", "Φλαύιος"):
        g = classify_gender(masc)
        assert g.gender == "male" and g.basis == "nomen", masc


def test_nomen_genitive_plural_is_not_a_person() -> None:
    # Αὐρηλίων = "of the Aurelii", a group, not an individual — no gender.
    assert classify_gender("Αὐρηλίων").gender == "unknown"


# --- rule 3: kin nouns (θυγάτηρ f / υἱός m), with metronymic + handoff guards -


def test_daughter_and_son_nouns() -> None:
    assert classify_gender("Θεοφίλῃ", after=" τῇ θυγατρὶ Βίκτορος").gender == "female"
    assert classify_gender("Ἀβραάμ", after=" υἱὸς Εὐδαίμονος").gender == "male"


def test_metronymic_mother_is_not_a_female_signal_for_the_head_person() -> None:
    # "… Πατερμουθίου μητρὸς Ταεισᾶτος" names the person's MOTHER; without another
    # signal the head person's gender is unknown (μήτηρ is deliberately ignored).
    assert classify_gender("Ὧρος", after=" Πατερμουθίου μητρὸς Ταεισᾶτος").gender != "female"


def test_kin_handoff_guard_does_not_misgender_coordinated_relative() -> None:
    # "Σοήριος καὶ ὁ τούτου υἱὸς Πετενοῦφις" — the son is a co-ordinated OTHER
    # person; the υἱός must not attribute male to Soërios via the kin rule.
    g = classify_gender("Σοήριος", after=" καὶ ὁ τούτου υἱὸς Πετενοῦφις")
    assert g.basis != "kin"


# --- rule 4: Egyptian onomastic prefix (tꜣ- f / pꜣ- m) -----------------------


def test_egyptian_article_prefix() -> None:
    assert classify_gender("Ταύητος").gender == "female"  # Ta- (she of)
    assert classify_gender("Πετεσοῦχος").gender == "male"  # Pete- (he whom gave)
    assert classify_gender("Πατερμουθίου").gender == "male"  # Pa-


def test_egyptian_prefix_exclusions_block_greek_latin_collisions() -> None:
    # Ταυρῖνος (Taurinus, m) and Παῦλος (Paulus, m) start Τα-/Πα- but are not
    # Egyptian-article names; the exclusion list keeps them out of the fem/masc
    # prefix rule (they fall through to unknown, not to a wrong attribution).
    assert classify_gender("Ταυρῖνος").gender != "female"
    assert classify_gender("Παῦλος").basis != "egypt_prefix"


# --- rule 5: gazetteer + the masculine-inflection veto -----------------------


def test_gazetteer_greek_names() -> None:
    assert classify_gender("Ἰσιδώρα").gender == "female"
    assert classify_gender("Ἀπολλώνιος").gender == "male"


def test_gazetteer_female_stem_vetoed_on_masculine_inflection() -> None:
    # Δίδυμος (m) shares the Διδυμ- stem with Διδύμη (f); its masculine cases must
    # NOT read as female. The dative Διδύμῳ folds to -ω, the trap the veto closes.
    assert classify_gender("Δίδυμον").gender != "female"  # accusative -ον
    assert classify_gender("Διδύμῳ").gender != "female"  # dative -ῳ → folded -ω
    assert classify_gender("Θερμούθιος").gender != "female"  # -ιος masculine


def test_precision_order_guardian_beats_name_morphology() -> None:
    # A masculine-looking name with a guardian formula is still female (guardian
    # is first): the formula is decisive over the name's own morphology.
    g = classify_gender("Ἀθηνίου", after=" τῆς Ἀχιλλέως μετὰ κυρίου")
    assert g.gender == "female" and g.basis == "guardian"


def test_unknown_when_no_signal() -> None:
    assert classify_gender("Σαραπίωνος", after=" τοῦ καὶ Διδύμου").gender == "male"
    assert classify_gender("Κρονίων").gender == "male"
    assert classify_gender("").gender == "unknown"
