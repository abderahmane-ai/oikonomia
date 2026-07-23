"""Hand-computed fixtures for the attribute-apposition rule (Phase 8b).

The rule is pure over ``(start, end, label)`` tuples — it never reads text — so
every case here fixes offsets and labels by hand and asserts the exact edge set.
The offsets are chosen to mirror the real Greek constructions the rule was built
from (``Ἀρτεμίδωρος ἰατρός``, ``Φιλουμένη ὡς ἐτῶν ν``) without needing the strings.

What each group pins down:
  * direction + adjacency — the subject precedes the attribute and the nearest
    *preceding* one wins;
  * the false attractor — the next registrant's name sits right after an age and
    must never be read as its subject;
  * the headcount guard — a counted category (``ἱερεῖς β``) is not a title;
  * position-not-list-order — heads are found by character position, so list
    order is irrelevant.
"""

from __future__ import annotations

from oikonomia.labeling.apposition import (
    DEFAULT_MAX_GAP,
    HAS_AGE,
    HAS_OCCUPATION,
    attribute_relations,
)


def test_basic_occupation_apposition() -> None:
    # "Ἀρτεμίδωρος ἰατρός": PERSON then OCCUPATION at gap 1.
    ents = [(0, 11, "PERSON"), (12, 18, "OCCUPATION")]
    assert attribute_relations(ents) == [(0, 1, HAS_OCCUPATION)]


def test_basic_age_apposition_across_the_etwn_formula() -> None:
    # "Φιλουμένη ὡς ἐτῶν ν": the "ὡς ἐτῶν " sits between name and numeral (gap 8).
    ents = [(0, 9, "PERSON"), (17, 18, "AGE")]
    assert attribute_relations(ents) == [(0, 1, HAS_AGE)]


def test_person_role_is_an_admissible_subject() -> None:
    # A bare role can bear the attribute ("the priest, N years old").
    ents = [(0, 7, "PERSON_ROLE"), (8, 14, "AGE")]
    assert attribute_relations(ents) == [(0, 1, HAS_AGE)]


def test_nearest_preceding_subject_wins() -> None:
    # Two names precede the occupation; the closer one (index 1, gap 2) is the
    # head, not the far one (index 0, gap 12).
    ents = [(0, 8, "PERSON"), (10, 18, "PERSON"), (20, 26, "OCCUPATION")]
    assert attribute_relations(ents) == [(1, 2, HAS_OCCUPATION)]


def test_following_subject_is_never_the_head_false_attractor() -> None:
    # Dense register: an age is flanked by its own subject (before) and the next
    # registrant (after, gap 1). The after-name must be ignored entirely.
    ents = [
        (0, 9, "PERSON"),  # subject, ends 9  (gap to age = 8)
        (17, 18, "AGE"),
        (19, 27, "PERSON"),  # next registrant — ends after the age, excluded
    ]
    assert attribute_relations(ents) == [(0, 1, HAS_AGE)]


def test_no_subject_within_reach_yields_no_edge() -> None:
    # Precision over recall: a lost/distant name gives no edge, not a wrong one.
    ents = [(0, 8, "PERSON"), (60, 66, "OCCUPATION")]  # gap 52 > 40
    assert attribute_relations(ents) == []


def test_max_gap_boundary() -> None:
    at = [(0, 10, "PERSON"), (50, 56, "OCCUPATION")]  # gap exactly 40
    over = [(0, 10, "PERSON"), (51, 57, "OCCUPATION")]  # gap 41
    assert attribute_relations(at) == [(0, 1, HAS_OCCUPATION)]
    assert attribute_relations(over) == []
    assert DEFAULT_MAX_GAP == 40


def test_headcount_guard_skips_counted_occupation() -> None:
    # "ἱερεῖς β" = "priests: 2": the OCCUPATION is a HAS_QUANTITY head (the count
    # begins 1 char after it), not a personal title — so no HAS_OCCUPATION edge.
    ents = [(0, 10, "PERSON"), (11, 17, "OCCUPATION"), (18, 19, "QUANTITY")]
    assert attribute_relations(ents) == []


def test_headcount_guard_boundary() -> None:
    # QUANTITY at the guard gap (3) is a headcount; one char further is not.
    skip = [(0, 10, "PERSON"), (11, 17, "OCCUPATION"), (20, 21, "QUANTITY")]  # gap 3
    keep = [(0, 10, "PERSON"), (11, 17, "OCCUPATION"), (21, 22, "QUANTITY")]  # gap 4
    assert attribute_relations(skip) == []
    assert attribute_relations(keep) == [(0, 1, HAS_OCCUPATION)]


def test_headcount_guard_is_occupation_only() -> None:
    # AGE followed by a QUANTITY still links — the guard never applies to AGE.
    ents = [(0, 9, "PERSON"), (10, 11, "AGE"), (12, 13, "QUANTITY")]
    assert attribute_relations(ents) == [(0, 1, HAS_AGE)]


def test_head_is_by_character_position_not_list_order() -> None:
    # The subject follows the attribute in list order but precedes it in the text;
    # the head is still found (index 1), proving position-based anchoring.
    ents = [(20, 26, "OCCUPATION"), (0, 10, "PERSON")]
    assert attribute_relations(ents) == [(1, 0, HAS_OCCUPATION)]


def test_each_attribute_takes_its_own_subject() -> None:
    # Two registrants, each with one attribute — no cross-linking.
    ents = [
        (0, 8, "PERSON"),  # A
        (9, 15, "OCCUPATION"),  # A's trade
        (20, 28, "PERSON"),  # B
        (29, 32, "AGE"),  # B's age
    ]
    assert attribute_relations(ents) == [(0, 1, HAS_OCCUPATION), (2, 3, HAS_AGE)]


def test_no_attributes_no_edges() -> None:
    assert attribute_relations([(0, 8, "PERSON"), (9, 15, "PLACE")]) == []
    assert attribute_relations([]) == []
