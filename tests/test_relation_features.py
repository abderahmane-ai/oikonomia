"""Hand-computed fixtures for the neuro-symbolic direction features.

The Greek strings are tiny payment clauses with the payer/amount located by
substring search (so no offset is hand-typed), and the expected verb-class /
position / payer-marking are worked out from the Phase-5c rule the features
distil. This pins the direction signal without a model.
"""

from __future__ import annotations

from oikonomia.relations.features import (
    MARK_ARTICLE_PARA,
    MARK_DATIVE,
    MARK_OTHER,
    MARK_PARA,
    POS_BEFORE_HEAD,
    POS_NONE,
    VERB_GIVER,
    VERB_NONE,
    VERB_RECEIVER,
    PaymentLexicon,
    context_window,
    direction_features,
    fold,
)

LEX = PaymentLexicon(
    receiver=["απεχ", "εσχ", "εχειν"],
    giver=["διεγραψ", "δεδωκ"],
    impersonal=["τετακ"],
    dative_endings=["ι", "ωι", "ω"],
)


def _span(text: str, sub: str) -> tuple[int, int]:
    i = text.index(sub)
    return i, i + len(sub)


def test_fold_is_offset_stable_and_folds() -> None:
    text = "Ἀπέχω παρὰ Σαραπίωνος"
    folded = fold(text)
    assert len(folded) == len(text)  # every char maps to exactly one
    # lowercased, accents stripped, final sigma → medial sigma
    assert folded == "απεχω παρα σαραπιωνοσ"


def test_receiver_with_para_payer() -> None:
    # ἀπέχω (receiver) παρὰ X (payer) : the παρά-marked person is the payer.
    text = "ἀπέχω παρὰ Σαραπίωνος ἀργυρίου δραχμὰς"
    head = _span(text, "Σαραπίωνος")
    tail = _span(text, "δραχμὰς")
    f = direction_features(text, head, tail, LEX)
    assert f.verb_class == VERB_RECEIVER
    assert f.verb_pos == POS_BEFORE_HEAD  # ἀπέχω precedes the payer
    assert f.payer_mark == MARK_PARA


def test_giver_with_dative_payee_marking() -> None:
    # διέγραψεν X (payer, nom) Y-ι (payee, dative). Same amount, two candidates:
    text = "διέγραψεν Ἡρακλείδης Σαραπίωνι δραχμὰς"
    tail = _span(text, "δραχμὰς")
    payer = direction_features(text, _span(text, "Ἡρακλείδης"), tail, LEX)
    payee = direction_features(text, _span(text, "Σαραπίωνι"), tail, LEX)
    assert payer.verb_class == payee.verb_class == VERB_GIVER
    assert payer.payer_mark == MARK_OTHER  # nominative subject
    assert payee.payer_mark == MARK_DATIVE  # -ι ending — the dative payee


def test_article_para_is_agent_not_payer() -> None:
    # `ὁ παρὰ X` — X is an agent/official, never the payer (Phase-5c bug).
    text = "ὁ παρὰ Σαραπίωνος γεωργὸς ἔσχεν δραχμὰς"
    head = _span(text, "Σαραπίωνος")
    tail = _span(text, "δραχμὰς")
    f = direction_features(text, head, tail, LEX)
    assert f.payer_mark == MARK_ARTICLE_PARA


def test_no_verb_no_marking() -> None:
    text = "Σαραπίωνος δραχμὰς δέκα"  # a bare list line, no payment verb
    head = _span(text, "Σαραπίωνος")
    tail = _span(text, "δραχμὰς")
    f = direction_features(text, head, tail, LEX)
    assert f.verb_class == VERB_NONE
    assert f.verb_pos == POS_NONE
    assert f.payer_mark == MARK_OTHER  # -ος genitive, not a dative ending


def test_context_window_reaches_before_the_payer() -> None:
    # The window must start pad chars before the payer to catch a pre-head verb.
    text = "διέγραψεν Ἡρακλείδης δραχμὰς"
    head = _span(text, "Ἡρακλείδης")
    tail = _span(text, "δραχμὰς")
    lo, hi = context_window(head, tail, pad=40)
    assert lo == 0  # clamped to the start, before the verb
    assert hi == tail[1]
    assert text[lo:hi].startswith("διέγραψεν")  # the giver verb is inside the window
