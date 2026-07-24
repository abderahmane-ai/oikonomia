"""Hand-built fixtures for the pure half of corpus-scale RE inference (step 8).

No model and no tokenizer: :func:`build_window_candidates` is fed a hand-written
per-token offset list (bos … content … eos), so the candidate construction, the
global-vs-window index bookkeeping and the out-of-window drop are all checked
deterministically. :func:`merge_scored` is checked on synthetic scored edges.
"""

from __future__ import annotations

from oikonomia.relations.encode import ENDPOINT_LABELS
from oikonomia.relations.features import PaymentLexicon, fold
from oikonomia.relations.infer import (
    build_window_candidates,
    merge_scored,
)

# "μίσθωσις Ταῆσις πρὸς Ἀπολλώνιον δραχμὰς κ"
#  0        9      16   21         32      40
TEXT = "μίσθωσις Ταῆσις πρὸς Ἀπολλώνιον δραχμὰς κ"
ENTS = [
    (0, 8, "TRANSACTION"),  # 0
    (9, 15, "PERSON"),  # 1  Ταῆσις
    (21, 31, "PERSON"),  # 2  Ἀπολλώνιον
    (32, 41, "MONEY_AMOUNT"),  # 3  "δραχμὰς κ"
]
# One token per word, wrapped in the two special-token (0,0) slots the model adds.
#           bos    μίσθ    Ταῆσις  πρὸς     Ἀπολλ    δραχμ    κ       eos
FULL_OFFS = [(0, 0), (0, 8), (9, 15), (16, 20), (21, 31), (32, 39), (40, 41), (0, 0)]
ENT2ID = {lab: i for i, lab in enumerate(ENDPOINT_LABELS)}
LEX = PaymentLexicon()
FOLDED = fold(TEXT)


def _pairs(cands: list) -> set[tuple[int, int]]:
    return {(c.h, c.t) for c in cands}


def test_party_of_candidates_use_global_indices_and_token_ranges() -> None:
    cands = build_window_candidates(ENTS, FULL_OFFS, FOLDED, ENT2ID, LEX)
    # both PERSON -> TRANSACTION party candidates are present, by GLOBAL entity idx
    assert (1, 0) in _pairs(cands)  # Ταῆσις -> μίσθωσις
    assert (2, 0) in _pairs(cands)  # Ἀπολλώνιον -> μίσθωσις
    thaesis = next(c for c in cands if (c.h, c.t) == (1, 0))
    # head Ταῆσις is token 2 (offset (9,15)); tail μίσθωσις is token 1 (offset (0,8))
    assert (thaesis.h0, thaesis.h1) == (2, 3)
    assert (thaesis.t0, thaesis.t1) == (1, 2)
    assert thaesis.hlab == "PERSON" and thaesis.tlab == "TRANSACTION"
    assert thaesis.htid == ENT2ID["PERSON"] and thaesis.ttid == ENT2ID["TRANSACTION"]


def test_person_money_direction_candidates_present() -> None:
    cands = build_window_candidates(ENTS, FULL_OFFS, FOLDED, ENT2ID, LEX)
    # PERSON -> MONEY_AMOUNT is the PAID_BY/PAID_TO candidate the direction head scores
    assert (1, 3) in _pairs(cands)  # Ταῆσις -> money
    assert (2, 3) in _pairs(cands)  # Ἀπολλώνιον -> money
    money = next(c for c in cands if (c.h, c.t) == (1, 3))
    # money "δραχμὰς κ" spans tokens 5 (32,39) and 6 (40,41)
    assert (money.t0, money.t1) == (5, 7)


def test_entities_outside_the_window_are_not_paired() -> None:
    # A window covering only "μίσθωσις Ταῆσις πρὸς": the two later entities have no
    # overlapping token, so only the Ταῆσις -> μίσθωσις party pair survives.
    partial = [(0, 0), (0, 8), (9, 15), (16, 20), (0, 0)]
    cands = build_window_candidates(ENTS, partial, FOLDED, ENT2ID, LEX)
    assert _pairs(cands) == {(1, 0)}
    only = cands[0]
    assert (only.h0, only.h1) == (2, 3) and (only.t0, only.t1) == (1, 2)


def test_fewer_than_two_in_window_entities_yields_no_candidates() -> None:
    # Window sees only μίσθωσις — nothing to pair it with.
    just_one = [(0, 0), (0, 8), (0, 0)]
    assert build_window_candidates(ENTS, just_one, FOLDED, ENT2ID, LEX) == []


def test_merge_scored_keeps_highest_probability_per_pair() -> None:
    # The same pair scored in two overlapping windows, plus a distinct pair.
    scored = [
        (1, 0, "PARTY_OF", 0.6),
        (1, 0, "PARTY_OF", 0.9),  # higher-confidence reading of the same pair
        (2, 0, "PARTY_OF", 0.5),
    ]
    merged = merge_scored(scored)
    assert len(merged) == 2
    by_pair = {(h, t): (ty, s) for (h, t, ty, s) in merged}
    assert by_pair[(1, 0)] == ("PARTY_OF", 0.9)
    assert by_pair[(2, 0)] == ("PARTY_OF", 0.5)


def test_merge_scored_can_switch_type_to_the_higher_scoring_window() -> None:
    # A seam-crossing pair read as PAID_BY in one window, PAID_TO (higher) in another.
    merged = merge_scored([(1, 3, "PAID_BY", 0.4), (1, 3, "PAID_TO", 0.7)])
    assert merged == [(1, 3, "PAID_TO", 0.7)]
