"""Deterministic gender attribution for a PERSON span — the enabler for the
"women as economic principals" finding (Phase 9, deliverable #3).

Sex is not annotated in the papyri, but Greek-Egyptian documentary practice
encodes it in ways a rule can read *auditably* — every call returns the exact
``basis`` that fired, so a papyrologist can check each attribution against the
text. The rules, precision-ordered (a earlier hit wins):

1. **Guardian formula** — a woman without the *ius liberorum* transacted only
   ``μετὰ κυρίου`` ("with her guardian") or, if she held the privilege,
   ``χωρὶς κυρίου χρηματίζουσα`` ("transacting without a guardian"). Both formulae
   attach *only* to women, so the immediately-preceding principal is female. This
   is the single highest-precision signal (~0.97).
2. **Roman nomen** — Latin nomina keep grammatical gender in Greek: ``Αὐρήλιος``
   (m) vs ``Αὐρηλία`` (f), across all cases (α-declension = f, ο-declension = m).
   After the Constitutio Antoniniana (212 AD) nearly every principal bears one,
   so this is high-coverage *and* high-precision in Roman-era documents (~0.9).
3. **Kin noun** — an explicit ``θυγάτηρ`` / ``γυνή`` (daughter/wife) marks the
   person female; ``υἱός`` marks male. Decisive when present (~0.9), but the bare
   genitive filiation (no noun) carries no signal, and a *metronymic*
   (``… μητρὸς Ταεισᾶτος``, "his/her mother being Taeisas") names the person's
   **mother**, not the person — so ``μήτηρ`` in that frame is deliberately NOT a
   female signal for the head person.
4. **Egyptian onomastic prefix** — Egyptian names built on the definite article
   carry its gender: feminine *tꜣ* → ``Τα-``/``Τσεν-``/``Σεν-`` ("she of / daughter
   of"), masculine *pꜣ* → ``Πα-``/``Πετε-``/``Πσεν-``/``Ψεν-`` ("he of / he whom [god]
   gave"). Robust to case (the prefix is word-initial), but weaker (~0.72) — a few
   Greek/Latin names collide (``Ταυρῖνος`` m, ``Παῦλος`` m), which the exclusion
   list guards against.
5. **Gazetteer** — a short list of very common names whose gender morphology alone
   would miss, matched on a case-stable stem (~0.8).

Nothing here is learned; identity of the *signal* is what carries provenance.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal, NamedTuple

Gender = Literal["female", "male", "unknown"]


class GenderGuess(NamedTuple):
    """A gender attribution with the rule that produced it (its provenance)."""

    gender: Gender
    basis: str  # which rule fired: guardian | nomen | kin | egypt_prefix | gazetteer
    confidence: float


UNKNOWN = GenderGuess("unknown", "none", 0.0)

# --- token cleanup -----------------------------------------------------------

# Leading articles / prepositions / conjunctions that introduce a name but are
# not part of it; stripped to expose the first real name token.
_LEAD = re.compile(
    r"^(?:ὁ|ἡ|οἱ|αἱ|τοῦ|τῆς|τῷ|τῇ|τὸν|τὴν|τό|τά|τῶν|τοῖς|ταῖς"
    r"|καὶ|καί|και|παρὰ|παρα|διὰ|δια|πρὸς|προς|ὑπὸ|υπο|ἀπὸ|απο|ὑπὲρ|υπερ)\b[\s'ʼ]*"
)


def first_name_token(name: str) -> str:
    """The first genuine name token: leading articles/preps/conjunctions removed."""
    nm = name.replace("ʼ", " ").replace("'", " ").strip()
    for _ in range(4):  # a name may be preceded by up to a few function words
        stripped = _LEAD.sub("", nm)
        if stripped == nm:
            break
        nm = stripped
    toks = nm.split()
    return toks[0] if toks else ""


def _strip_accents(s: str) -> str:
    """Fold accents/breathings for accent-insensitive stem matching (keep case)."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# --- rule 1: guardian formula ------------------------------------------------

# Only women transact μετὰ/χωρὶς κυρίου. Kept tight: the formula must fall in the
# window *right after* the name and before any conjunction that would hand off to
# a different principal (so "A καὶ B χωρὶς κυρίου" attributes to B, not A).
_GUARDIAN = re.compile(r"(?:μετὰ|μετα|χωρὶς|χωρις)\s+κυρ(?:ίου|ιου|ία|ια)")
_HANDOFF = re.compile(r"\s(?:καὶ|καί|και)\s")


def has_guardian(after: str) -> bool:
    """True if a guardian formula attaches to the name introducing ``after``.

    ``after`` is the text immediately following the person span. A ``καὶ`` before
    the formula means it belongs to a later, co-ordinated principal, not this one.
    """
    m = _GUARDIAN.search(after)
    if not m:
        return False
    handoff = _HANDOFF.search(after)
    return handoff is None or handoff.start() >= m.start()


# --- rule 2: Roman nomina ----------------------------------------------------

_NOMEN = re.compile(
    r"^(?:Αυρηλ|Ιουλ|Κλαυδ|Φλαυ|Φλαου|Ουαλερ|Αντων|Σεπτιμ|Αιλ|Ελουι|Ουλπ"
    r"|Πετρων|Ποµπ|Κλωδ|Δομ[ιε]τ|Κορνηλ|Καικιλ)"
)
# Endings matched on the accent-folded form (so dative ῳ, folded to bare ω, is
# caught). Masculine ο-declension is tested first; -ων (gen. plural) is left out
# of both so a group like Αὐρηλίων ("of the Aurelii") stays unattributed.
_MASC_END = re.compile(r"(?:ιος|ιου|ιω|ιον|ος|ου|ω|ον)$")
_FEM_END = re.compile(r"(?:ιας|ιαν|ια|ας|αν|α)$")


def _nomen_gender(first_raw: str) -> GenderGuess | None:
    """Gender from a Roman nomen's declension ending (α-stem f vs ο-stem m)."""
    folded = _strip_accents(first_raw)
    if not _NOMEN.match(folded):
        return None
    if _MASC_END.search(folded):
        return GenderGuess("male", "nomen", 0.9)
    if _FEM_END.search(folded):
        return GenderGuess("female", "nomen", 0.9)
    return None  # e.g. genitive plural Αυρηλιων — a group, not a person


# --- rule 3: explicit kin nouns ----------------------------------------------

_DAUGHTER = re.compile(r"\bθυγα?τ[ρέη]")  # θυγάτηρ / θυγατρός — qualifies THIS person
_SON = re.compile(r"\b(?:υἱὸς|υιος|υἱοῦ|υιου|υἱῷ|υιω|υἱὸν|υιον)\b")


def _kin_before_handoff(pat: re.Pattern[str], after: str) -> bool:
    """A kin noun qualifies THIS person only if no ``καὶ`` intervenes first.

    ``X καὶ ὁ υἱὸς Y`` ("X and his son Y") and ``X καὶ τῆς γυναικός`` point the kin
    noun at a *co-ordinated other* person; the guard rejects those, keeping only
    ``X υἱὸς Y`` / ``X θυγάτηρ Y`` where the noun modifies X itself.
    """
    m = pat.search(after[:24])
    if not m:
        return False
    handoff = _HANDOFF.search(after)
    return handoff is None or handoff.start() >= m.start()


def _kin_gender(after: str) -> GenderGuess | None:
    """Female if the person is called a daughter; male if a son.

    Uses only the window right after the name so it qualifies *this* person, and
    guards against the ``… καὶ ὁ υἱὸς …`` handoff. Two deliberate omissions: the
    metronymic ``μητρὸς X`` names the mother, not the head person, so ``μήτηρ`` is
    never consulted; and ``γυνή`` is dropped because it appears as ``… καὶ τῆς
    γυναικός`` ("… and his wife") — a *different* party — far more often than as a
    self-descriptor (the wife is handled at party level).
    """
    if _kin_before_handoff(_DAUGHTER, after):
        return GenderGuess("female", "kin", 0.9)
    if _kin_before_handoff(_SON, after):
        return GenderGuess("male", "kin", 0.9)
    return None


# --- rule 4: Egyptian onomastic prefix ---------------------------------------

# tꜣ- (feminine article) and pꜣ- (masculine). Longest/most specific first.
_FEM_PREFIX = ("Τσεν", "Σεν", "Ταη", "Ταυη", "Θαη", "Θαι", "Θαυ", "Θασ", "Τα", "Τε", "Τθ")
_MASC_PREFIX = ("Πετε", "Πσεν", "Ψεν", "Πνεφ", "Πικ", "Πα", "Παπ", "Πε", "Ψα", "Πχ")
# Greek/Latin names that collide with the prefixes above — never Egyptian-prefixed.
_PREFIX_EXCLUDE = re.compile(
    r"^(?:Ταυρ|Ταρ|Τατ|Τερ|Τιμ|Τιτ|Τελ|Παυλ|Παππ|Παπ[πο]|Πανκ|Πανθ|Παμ|Παρθ|Πελ|Περ[γισ])"
)


def _egypt_prefix_gender(first_raw: str) -> GenderGuess | None:
    """Gender from the Egyptian definite-article prefix, guarded by exclusions."""
    folded = _strip_accents(first_raw)
    if len(folded) < 4 or _PREFIX_EXCLUDE.match(folded):
        return None
    if folded.startswith(_FEM_PREFIX):
        return GenderGuess("female", "egypt_prefix", 0.72)
    if folded.startswith(_MASC_PREFIX):
        return GenderGuess("male", "egypt_prefix", 0.72)
    return None


# --- rule 5: gazetteer -------------------------------------------------------

# Very common names whose gender morphology alone misses; matched on an
# accent-folded, case-stable *stem* (the part invariant across grammatical cases).
_GAZ_FEMALE = (
    "Διδυμ", "Θερμουθ", "Ισιδωρ", "Σαραπου", "Ευδαιμον", "Σαμβαθ", "Ελεν",
    "Ταειτ", "Τεφερω", "Θατρη", "Θαυβασ", "Θαεισ",
)
_GAZ_MALE = (
    "Απολλωνιο", "Ηρακλειδ", "Σαραπιων", "Διοσκορ", "Πτολεμαι", "Διονυσι",
    "Αμμωνι", "Θεων", "Ωρο", "Ωριγεν", "Φιβ", "Κρονιων", "Ισιδωρο", "Σαραπαμμ",
    "Γεμελλ", "Νεμεσι", "Ψεναμουν",
)


# A clearly-masculine ο-declension inflection vetoes a *female* gazetteer stem:
# ``Δίδυμον``/``Διδύμῳ`` (acc./dat. of Δίδυμος m) and ``Θερμούθιος`` (m) must not be
# read as the feminine Διδύμη / Θερμοῦθις just because they share a stem. Matched on
# the *accent-folded* form (so the dative ῳ, folded to bare ω, is caught); female
# contract forms in -οῦς (Σαραποῦς, Ταοῦς) are not masculine, so ``ους`` is excluded.
_MASC_INFLECTION = re.compile(r"(?:ιος|ιου|ιω|ιον|ος|ου|ω|ον|ων)$")


def _gazetteer_gender(first_raw: str) -> GenderGuess | None:
    folded = _strip_accents(first_raw)
    # longest matching stem wins (Απολλωνιο- m beats Απολλωνι- f)
    best: tuple[int, Gender] | None = None
    for stem in _GAZ_MALE:
        if folded.startswith(stem) and (best is None or len(stem) > best[0]):
            best = (len(stem), "male")
    for stem in _GAZ_FEMALE:
        if folded.startswith(stem) and (best is None or len(stem) > best[0]):
            # a female stem on a masculine inflection is a wrong-name collision
            if not folded.endswith("ους") and _MASC_INFLECTION.search(folded):
                continue
            best = (len(stem), "female")
    if best is None:
        return None
    return GenderGuess(best[1], "gazetteer", 0.8)


# --- the classifier ----------------------------------------------------------


def classify_gender(name: str, after: str = "") -> GenderGuess:
    """Attribute a gender to a PERSON span, precision-first.

    ``name``  — the PERSON span text (may carry leading articles/prepositions).
    ``after`` — the text immediately following the span (for guardian/kin frames);
    the caller should truncate it at the next co-ordinated principal for tightest
    precision, but the guardian rule also self-guards on an intervening ``καὶ``.

    The high-precision signals — the guardian formula, the Roman nomen, an explicit
    kin noun — are the ones to trust; the ``basis`` on every result says which fired
    so a downstream analysis can keep only the strong ones.
    """
    first = first_name_token(name)
    if not first:
        return UNKNOWN

    if has_guardian(after):
        return GenderGuess("female", "guardian", 0.97)

    return (
        _nomen_gender(first)
        or _kin_gender(after)
        or _gazetteer_gender(first)
        or _egypt_prefix_gender(first)
        or UNKNOWN
    )
