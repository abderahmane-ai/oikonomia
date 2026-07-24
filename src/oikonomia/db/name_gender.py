"""A corpus-bootstrapped name→gender gazetteer — the coverage lever for the
women-as-principals finding, built with no external data.

The rule classifier (:mod:`oikonomia.db.persons`) attributes gender only where a
name carries a local marker (a guardian formula, a Roman nomen, a kin noun, an
Egyptian article prefix) — ~40% of principals. But a name that appears *once* as a
bare form here appears *many* times across the 61k-document corpus, and somewhere
it usually carries a decisive marker. This module harvests that: it votes each
name-form's gender from its high-precision attestations corpus-wide, then keeps the
forms that vote decisively. The result propagates the strong evidence to the
bare-name majority, using only the CC BY 3.0 corpus and staying auditable (every
entry traces to its attesting occurrences).

No learning, no external service: aggregation of the classifier's own decisive
signals. Built once (``oik db names build``), consumed by the party assembler.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from oikonomia.db.persons import classify_gender, name_key

# Which classifier bases are trustworthy enough to cast a gender vote. The
# in-clause markers are decisive; the Egyptian prefix is weaker per-occurrence but
# denoises in aggregate (a genuinely mixed form fails the agreement threshold). The
# inline gazetteer is excluded — voting from it would be circular.
VOTING_BASES = frozenset({"guardian", "nomen", "kin", "egypt_prefix"})

NameGender = dict[str, str]  # name_key → "female" | "male"


class Votes:
    """Per-name-form (female, male) tallies from decisive attestations."""

    def __init__(self) -> None:
        self._v: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    def add(self, name: str, after: str) -> None:
        """Record one PERSON occurrence's decisive-signal vote, if it has one."""
        key = name_key(name)
        if len(key) < 3:
            return
        g = classify_gender(name, after)  # no gazetteer → no circularity
        if g.basis not in VOTING_BASES:
            return
        if g.gender == "female":
            self._v[key][0] += 1
        elif g.gender == "male":
            self._v[key][1] += 1

    def tallies(self) -> Iterable[tuple[str, int, int]]:
        for key, (nf, nm) in self._v.items():
            yield key, nf, nm


def build_gazetteer(votes: Votes, min_attest: int = 3, min_agree: float = 0.85) -> NameGender:
    """Keep name-forms attested ``min_attest``+ times that agree ``min_agree``+.

    Agreement is the majority share; a form split near 50/50 (an ambiguous name, or
    a stem collision) is dropped rather than guessed — precision over coverage.
    """
    gaz: NameGender = {}
    for key, nf, nm in votes.tallies():
        total = nf + nm
        if total >= min_attest and max(nf, nm) / total >= min_agree:
            gaz[key] = "female" if nf > nm else "male"
    return gaz


def save_gazetteer(gaz: NameGender, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(gaz, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")


def load_gazetteer(path: Path) -> NameGender:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items() if v in ("female", "male")}
