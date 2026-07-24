"""Split a PERSON blob into structured name elements — the prosopography enabler.

The entity model tags a whole run of words as one PERSON span, so 37% of corpus
PERSON spans (130k) are *blobs*: the person's own name followed by a patronymic
(the father in the genitive), sometimes a grandfather, a metronymic, an alias, or
a status word. As one node a blob is useless for the two things the women finding
needs — gender must read the *principal's* own name (not the father's), and
kinship (``CHILD_OF``) is exactly the father that the blob hides.

Documentary practice, verified against the corpus, makes the split tractable
without a model:

* the patronymic is overwhelmingly **bare juxtaposition** — ``Ὧρος Πετεσούχου`` —
  with no "son of" word (``υἱός`` occurs in <0.01% of blobs), so the rule is
  positional: after the head, bare name tokens are the filiation chain;
* the connectives that *do* appear are boundaries, not names: ``τοῦ/τῆς`` (article
  before the father), ``μητρὸς X`` (X is the **mother**, not the head), ``ὁ καὶ Y``
  ("also called Y", an alias — same person), ``μετὰ/χωρὶς κυρίου Z`` (Z is the
  **guardian**, a different person — stop there);
* status words (``Πέρσης``, the feminine ``Περσίνη``, ``ἐπιγονῆς``) and royal
  epithets (``Σωτῆρος``, ``Εὐεργέτιδος`` — regnal dating formulae the model
  mis-tags as PERSON) are flagged, never treated as filiation.

Every element keeps its character offset (absolute, if a ``base`` is given), so a
kinship edge or a gender attribution traces back to a span in the document. Pure
and model-free: the whole contract is pinned by hand-computed tests.
"""

from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple


class NameElement(NamedTuple):
    """One name token with its character span (absolute if a ``base`` was given)."""

    text: str
    start: int
    end: int


class PersonName(NamedTuple):
    """A PERSON blob decomposed into its parts, each with provenance.

    ``head`` is the principal's own name; ``patronymics`` is the filiation chain
    (father first, then grandfather…); ``metronymic``/``alias`` are the mother and
    the "also-called" name when present; ``status`` holds ethnic/legal-status
    words (not names); ``flags`` records the boundaries that fired
    (``guardian_in_blob``, ``royal_formula``, ``fem_ethnic``, ``has_kai``,
    ``kin_noun``).
    """

    head: NameElement | None
    patronymics: list[NameElement]
    metronymic: NameElement | None
    alias: NameElement | None
    status: list[str]
    flags: frozenset[str]

    @property
    def father(self) -> NameElement | None:
        """The immediate patronymic (the father), if any — the ``CHILD_OF`` target."""
        return self.patronymics[0] if self.patronymics else None


# --- token vocabulary (all matched on the accent-folded, lower-cased form) -----

_PUNCT = "().,·;:’'ʼ[]{}—–-…\"«»"

# Function words that introduce but are not part of a name; skipped at the head.
_LEAD = {
    "ο", "η", "οι", "αι", "τον", "την", "το", "τα", "των", "τοις", "ταις",
    "παρα", "δια", "προς", "υπο", "απο", "υπερ", "εις", "εκ", "εξ", "συν",
}
# Article before a patronymic ("… τῆς Πατοῦτος") — skipped, not a name.
_ARTICLE = {"του", "της", "τω", "τη", "των", "τοις", "ταις", "τον", "την", "το", "τα"}
# The mother-word forms only — an exact set, NOT a stem, so names built on the
# same root (``Μητρόδωρος``, ``Μητρᾶς``) are not mistaken for "mother of".
_METRO = {"μητρος", "μητρι", "μητηρ", "μητερα", "μρ"}
_GUARD_PREP = {"μετα", "χωρις"}
_GUARD_NOUN = "κυρ"       # μετὰ/χωρὶς κυρίου — the following name is the GUARDIAN
# Explicit son/daughter nouns (rare in practice); exact forms so a name starting
# ``Υι-``/``Θυγατ-`` is not swallowed as a kin noun.
_KIN = {"υιος", "υιου", "υιω", "υιον", "υιε", "θυγατηρ", "θυγατρος", "θυγατρι", "θυγατερα"}
# Ethnic / legal-status words — descriptors, never filiation.
_STATUS = {
    "περσης", "περσου", "περσην", "περσαι", "περσινη", "περσιναι", "περσινης",
    "επιγονης", "αστη", "αστης", "αστος", "αστου", "απελευθερος", "απελευθερα",
    "δουλος", "δουλη", "δημοσιος",
}
# Royal epithets — regnal dating formulae the model mis-tags as a person.
_ROYAL = {
    "σωτηρος", "σωτηρων", "σωτηρι", "ευεργετου", "ευεργετιδος", "ευεργετων",
    "φιλομητορος", "φιλομητορων", "φιλοπατορος", "επιφανους", "θεου", "θεων",
    "νεου", "νεος", "μεγαλου", "βασιλεως", "βασιλισσης", "αυτοκρατορος",
    "καισαρος", "σεβαστου", "σεβαστης",
}

_TOKEN = re.compile(r"\S+")


def _fold(s: str) -> str:
    """Accent/breathing-fold and lower-case, for case- and accent-insensitive keys."""
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def _clean_bounds(raw: str, start: int) -> tuple[str, int, int]:
    """Trim edge punctuation from a token, returning ``(text, start, end)`` offsets."""
    a, b = 0, len(raw)
    while a < b and raw[a] in _PUNCT:
        a += 1
    while b > a and raw[b - 1] in _PUNCT:
        b -= 1
    return raw[a:b], start + a, start + b


def parse_person_name(text: str, base: int = 0) -> PersonName:
    """Decompose a PERSON span ``text`` into head + filiation + metronymic + alias.

    ``base`` is the span's absolute start offset in the document; pass it so every
    returned :class:`NameElement` slices the document text directly. With
    ``base=0`` the offsets are relative to ``text`` itself.
    """
    toks: list[tuple[str, int, int]] = []
    for m in _TOKEN.finditer(text):
        t, s, e = _clean_bounds(m.group(), base + m.start())
        if t:  # a token that was pure punctuation collapses to nothing
            toks.append((t, s, e))

    head: NameElement | None = None
    patronymics: list[NameElement] = []
    metronymic: NameElement | None = None
    alias: NameElement | None = None
    status: list[str] = []
    flags: set[str] = set()

    n = len(toks)
    i = 0
    while i < n and _fold(toks[i][0]) in _LEAD:  # strip leading function words
        i += 1
    if i < n:
        head = NameElement(*toks[i])
        i += 1

    def next_name(j: int) -> int:
        """Index of the next real name token at/after ``j`` (skipping articles)."""
        while j < n and _fold(toks[j][0]) in _ARTICLE:
            j += 1
        return j

    while i < n:
        raw, s, e = toks[i]
        f = _fold(raw)
        if f in _GUARD_PREP and i + 1 < n and _fold(toks[i + 1][0]).startswith(_GUARD_NOUN):
            flags.add("guardian_in_blob")  # the rest is the guardian, a different person
            break
        if f in _METRO:
            j = next_name(i + 1)
            if j < n:
                metronymic = NameElement(*toks[j])
                i = j + 1
                continue
            i += 1
            continue
        if f == "και" or (f in {"ο", "η"} and i + 1 < n and _fold(toks[i + 1][0]) == "και"):
            flags.add("has_kai")
            j = next_name(i + 2 if f in {"ο", "η"} else i + 1)
            if j < n:
                alias = NameElement(*toks[j])
                i = j + 1
                continue
            i += 1
            continue
        if f in _KIN:
            flags.add("kin_noun")  # "son"/"daughter" noun; the next name is the parent
            i += 1
            continue
        if f in _STATUS:
            status.append(raw)
            if f.startswith("περσιν"):
                flags.add("fem_ethnic")  # Περσίνη = "Persian woman" → a female cue
            i += 1
            continue
        if f in _ROYAL:
            flags.add("royal_formula")
            i += 1
            continue
        if f in _ARTICLE:
            i += 1  # τοῦ/τῆς before the patronymic — skip the bare article
            continue
        patronymics.append(NameElement(raw, s, e))  # a bare name token → filiation
        i += 1

    return PersonName(head, patronymics, metronymic, alias, status, frozenset(flags))
