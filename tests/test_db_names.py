"""Hand-computed fixtures for the PERSON-blob splitter.

The blobs here are real corpus PERSON spans (from `ner_corpus.jsonl`); the head,
filiation and boundary flags are worked out by hand, so a regression in the
name-structure logic is caught without a model. Offsets are checked to slice the
document text exactly, since kinship and gender both trace back to them.
"""

from __future__ import annotations

from oikonomia.db.names import parse_person_name


def test_bare_juxtaposition_name_and_father() -> None:
    # The dominant case: "Agathinos [son] of Philoxenos", no connective word.
    pn = parse_person_name("Ἀγαθῖνος Φιλοξένου")
    assert pn.head is not None and pn.head.text == "Ἀγαθῖνος"
    assert [p.text for p in pn.patronymics] == ["Φιλοξένου"]
    assert pn.father is not None and pn.father.text == "Φιλοξένου"
    assert pn.metronymic is None and pn.alias is None


def test_single_name_has_no_father() -> None:
    pn = parse_person_name("Ἀγαθῖνος")
    assert pn.head is not None and pn.head.text == "Ἀγαθῖνος"
    assert pn.patronymics == []
    assert pn.father is None


def test_father_and_grandfather_chain() -> None:
    pn = parse_person_name("Ὧρος Πετεσούχου Ἁρπαήσιος")
    assert pn.head is not None and pn.head.text == "Ὧρος"
    assert [p.text for p in pn.patronymics] == ["Πετεσούχου", "Ἁρπαήσιος"]
    assert pn.father is not None and pn.father.text == "Πετεσούχου"


def test_status_word_is_not_filiation() -> None:
    # "Panereus son of Gounsis, a Persian" — Πέρσης is a status word, not the father.
    pn = parse_person_name("Πανερεῦς Γούνσιος Πέρσης")
    assert pn.head is not None and pn.head.text == "Πανερεῦς"
    assert [p.text for p in pn.patronymics] == ["Γούνσιος"]
    assert pn.status == ["Πέρσης"]


def test_feminine_ethnic_is_flagged() -> None:
    # Περσίνη ("Persian woman") is a female cue, and never filiation.
    pn = parse_person_name("Τοτοέους Περσίναι")
    assert pn.head is not None and pn.head.text == "Τοτοέους"
    assert pn.patronymics == []
    assert "fem_ethnic" in pn.flags


def test_article_before_patronymic_is_skipped() -> None:
    # "Takmeis of-the Patous" — τῆς is an article introducing the father.
    pn = parse_person_name("Τακμήιτος τῆς Πατοῦτος")
    assert pn.head is not None and pn.head.text == "Τακμήιτος"
    assert [p.text for p in pn.patronymics] == ["Πατοῦτος"]


def test_metronymic_is_the_mother_not_the_head() -> None:
    pn = parse_person_name("Ὧρος μητρὸς Ταῆτος")
    assert pn.head is not None and pn.head.text == "Ὧρος"
    assert pn.patronymics == []  # no father named
    assert pn.metronymic is not None and pn.metronymic.text == "Ταῆτος"


def test_metro_root_name_is_not_a_mother_word() -> None:
    # Μητρόδωρος shares the μητρ- root but is a NAME, not "mother of"; as the
    # father it must stay a patronymic, not be eaten as a metronymic marker.
    pn = parse_person_name("Ὧρος Μητροδώρου")
    assert pn.head is not None and pn.head.text == "Ὧρος"
    assert [p.text for p in pn.patronymics] == ["Μητροδώρου"]
    assert pn.metronymic is None


def test_alias_ho_kai() -> None:
    # "Horos, also called Apollonios" — one person, two names.
    pn = parse_person_name("Ὧρος ὁ καὶ Ἀπολλώνιος")
    assert pn.head is not None and pn.head.text == "Ὧρος"
    assert pn.alias is not None and pn.alias.text == "Ἀπολλώνιος"
    assert pn.patronymics == []
    assert "has_kai" in pn.flags


def test_guardian_in_blob_stops_filiation() -> None:
    # μετὰ κυρίου Ὥρου → Ὥρου is the guardian, a different person, not the father.
    pn = parse_person_name("Ταῆσις μετὰ κυρίου Ὥρου")
    assert pn.head is not None and pn.head.text == "Ταῆσις"
    assert pn.patronymics == []  # the guardian is NOT counted as filiation
    assert "guardian_in_blob" in pn.flags


def test_royal_dating_formula_is_flagged() -> None:
    # A mis-tagged regnal formula, not a person+patronymic.
    pn = parse_person_name("Φιλομήτορος Σωτῆρος")
    assert "royal_formula" in pn.flags


def test_offsets_slice_the_document_exactly() -> None:
    # With a base offset, every element indexes the source document directly.
    doc = "ἔτους ιδ ἀπέδοτο Ἀγαθῖνος Φιλοξένου δραχμῶν"
    base = doc.index("Ἀγαθῖνος")
    blob = "Ἀγαθῖνος Φιλοξένου"
    pn = parse_person_name(blob, base=base)
    assert pn.head is not None
    assert doc[pn.head.start : pn.head.end] == "Ἀγαθῖνος"
    assert pn.father is not None
    assert doc[pn.father.start : pn.father.end] == "Φιλοξένου"


def test_line_break_inside_blob_splits_tokens() -> None:
    # PERSON blobs can straddle a line break; \n is whitespace, so tokens split.
    pn = parse_person_name("Σενενοῦπις Φίβιος\nΠερσίνη")
    assert pn.head is not None and pn.head.text == "Σενενοῦπις"
    assert [p.text for p in pn.patronymics] == ["Φίβιος"]
    assert "fem_ethnic" in pn.flags


def test_empty_or_punctuation_only_is_headless() -> None:
    assert parse_person_name("").head is None
    assert parse_person_name("  ,  ").head is None
