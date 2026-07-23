"""The strong silver labeler (Phase 6).

The proximity baseline (:mod:`oikonomia.labeling.weak_rules`) handles the
economic half of the schema well — CURRENCY, UNIT, MONEY_AMOUNT, QUANTITY — but
the scorer showed it is *structurally blind* to the categories no lexicon
reaches: PERSON (30% of all gold entities), PLACE, TRANSACTION, PERSON_ROLE,
AGE, and the relations that anchor on them (PARTY_OF, DATED_TO, HAS_PRICE).

This labeler is built **on top of** the baseline rather than replacing it: it
runs :func:`~oikonomia.labeling.weak_rules.label_document` for the economic
spans and then adds labeling functions for the missing types, resolving
overlaps in the baseline's favour (its lexicon hits are the highest-precision
signal available). The added functions encode what mining the 65 gold documents
measured, not intuition:

* **PERSON** — 99.8% of gold persons are capital-initial, and capitalisation is
  71.6% precise for PERSON once titulature, months and numerals are removed.
  So: capitalised tokens, merged across filiation/alias particles into one span
  (``Πτολεμαὶς Χαιρήμονος τοῦ Χαιρήμονος``), minus imperial titulature standing
  alone in a dating formula.
* **PLACE** — capitalised tokens in administrative context (``κώμης X``,
  ``X πόλεως / μερίδος / νομοῦ / κλήρου``) or matching a toponym gazetteer. The
  admin noun is *part of* the span, which is what stops a land parcel's eponym
  (``Εἰρηναίου κλήρου``) from reading as a bare PERSON.
* **TRANSACTION / PERSON_ROLE** — closed classes matched by folded stem prefix
  (``μισθωσ`` covers μίσθωσις/μισθώσασθαι/μισθώσεως).
* **AGE** — a numeral adjacent to ``ἐτῶν``.

All patterns live in ``resources/silver/patterns.yaml`` and are tuned against
``oik silver score``.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from pydantic import BaseModel, Field

from oikonomia.labeling.apposition import (
    HAS_AGE,
    HAS_OCCUPATION,
    attribute_relations,
)
from oikonomia.labeling.matcher import Matcher
from oikonomia.labeling.mine import is_greek_letter, tokenize
from oikonomia.labeling.normalize import normalize
from oikonomia.labeling.weak_rules import (
    COMMODITY,
    DATE_REF,
    DEFAULT_WINDOW,
    MONEY_AMOUNT,
    WeakEntity,
    WeakLabeling,
    WeakRelation,
    label_document,
)
from oikonomia.schemas.spans import CharSpan

# A lexicon category emitted by the shared Matcher, named here so
# :data:`DIST_LABELS` can include it.
OCCUPATION = "OCCUPATION"

# Entity labels this labeler adds beyond the baseline's economic set.
PERSON = "PERSON"
PLACE = "PLACE"
TRANSACTION = "TRANSACTION"
PERSON_ROLE = "PERSON_ROLE"
AGE = "AGE"

# Relations this labeler adds.
PARTY_OF = "PARTY_OF"
DATED_TO = "DATED_TO"
HAS_PRICE = "HAS_PRICE"
# Payment direction: who gave the amount (PAID_BY) and who received it (PAID_TO).
# PERSON/PERSON_ROLE -> MONEY_AMOUNT/COMMODITY (see validate.RELATION_SIGNATURES).
PAID_BY = "PAID_BY"
PAID_TO = "PAID_TO"

# How close (characters) a numeral must sit to ``ἐτῶν`` to be an AGE.
AGE_ADJACENCY = 8

PATTERNS_RELPATH = ("silver", "patterns.yaml")

# Labels decided by the surface string, so their confidence can come from the
# corpus label distribution. Numeral labels (QUANTITY/MONEY_AMOUNT/FRACTION/AGE)
# and DATE_REF are decided by the <num>/date machinery: the digits carry no type
# signal, so they are excluded.
DIST_LABELS = frozenset({PERSON, PLACE, OCCUPATION, PERSON_ROLE, COMMODITY})

# Confidence priors for numeral- and lexicon-decided labels (whose confidence
# is not a corpus agreement). Values are the exact-match precisions measured by
# `oik silver score` against the gold draft. Confusable labels (DATE_REF,
# QUANTITY, TAX_TERM) sit low so a confidence filter reaches them.
SOURCE_CONFIDENCE: dict[str, float] = {
    "CURRENCY": 0.80,
    "UNIT": 0.74,
    "MONEY_AMOUNT": 0.82,
    "QUANTITY": 0.46,
    "DATE_REF": 0.35,
    "FRACTION": 0.60,
    "TAX_TERM": 0.26,
    "PRICE_TERM": 0.90,
    TRANSACTION: 0.75,
    AGE: 0.50,
}
# Confidence for a surface-decided span whose form is absent from the corpus
# table: novel names/toponyms, measured ~0.91 precise, priced conservatively.
UNSEEN_DIST_PRIOR = 0.85

# Relation confidence by type (measured precisions). PARTY_OF/DATED_TO/HAS_PRICE
# are the noisy tail — priced low so a confidence filter drops them first.
# HAS_OCCUPATION/HAS_AGE are the 8b appositions: deterministic and near-adjacency,
# so priced high. These two are PROVISIONAL priors (gold carries no HAS_OCCUPATION/
# HAS_AGE yet, so `oik silver score` cannot measure them); the prior reflects the
# gold-draft spot-check (occupation ~clean at gap 1; age looser, the ἐτῶν formula
# occasionally attaches a guardian/mother). Replace with measured precisions once
# the reviewed attribute draft is merged into gold.
RELATION_CONFIDENCE: dict[str, float] = {
    "HAS_CURRENCY": 0.70,
    "HAS_UNIT": 0.52,
    "HAS_QUANTITY": 0.72,
    "CHARGED_UNDER": 0.30,
    PARTY_OF: 0.28,
    DATED_TO: 0.12,
    HAS_PRICE: 0.30,
    HAS_OCCUPATION: 0.80,
    HAS_AGE: 0.70,
}

# Payment-direction confidence, keyed by the *construction* that fired, not the
# type — because precision varies far more by how the role was recovered than by
# payer-vs-payee. These are PROVISIONAL priors (the cleanest, "παρά + a receiver
# verb", is the mined 40-65%-reliable one); replace them with the measured
# precisions from `oik silver score` once the gold carries PAID_BY/PAID_TO.
PAID_CONFIDENCE: dict[str, float] = {
    "recv_para": 0.82,  # receiver verb + παρά PERSON -> that PERSON is the payer
    "give_subj": 0.60,  # giver verb's nearest PERSON (subject) -> payer
    "recv_subj": 0.45,  # receiver verb's preceding PERSON (subject) -> payee
    "give_dat": 0.45,   # giver verb's following dative PERSON -> payee
    "impersonal": 0.40,  # τέτακται's following PERSON -> payer (taxpayer)
}

# folded surface form -> {label: occurrences} across the corpus. Full
# distribution, not just the majority: the majority is the systematic bias for
# confusable forms (validated — a plain majority-vote flips 96% of PLACE to
# PERSON), so the useful signal is the *shape* of the distribution, e.g. "this
# form is place-dominant and almost never a person".
LabelDist = dict[str, dict[str, int]]


def doc_spans(doc: dict[str, Any]) -> tuple[list[CharSpan], list[CharSpan]]:
    """Edited-view numeral and line spans from one ``document_json`` dict."""
    numerals = [
        CharSpan(start=int(n["edited"]["start"]), end=int(n["edited"]["end"]))
        for n in doc.get("numerals", [])
        if n.get("edited")
    ]
    lines = [
        CharSpan(start=int(ln["edited"]["start"]), end=int(ln["edited"]["end"]))
        for ln in doc.get("lines", [])
        if ln.get("edited")
    ]
    return numerals, lines


class Patterns(BaseModel):
    """The folded stem/particle sets that drive the added labeling functions."""

    transaction_stems: list[str] = Field(default_factory=list)
    role_stems: list[str] = Field(default_factory=list)
    role_guarded_stems: list[str] = Field(default_factory=list)
    role_guard_determiners: list[str] = Field(default_factory=list)
    role_determiners: list[str] = Field(default_factory=list)
    place_admin_stems: list[str] = Field(default_factory=list)
    place_prepositions: list[str] = Field(default_factory=list)
    place_gazetteer_stems: list[str] = Field(default_factory=list)
    name_bridge_articles: list[str] = Field(default_factory=list)
    name_bridge_junior: list[str] = Field(default_factory=list)
    name_alias_pronouns: list[str] = Field(default_factory=list)
    titulature_stems: list[str] = Field(default_factory=list)
    month_stems: list[str] = Field(default_factory=list)
    party_prepositions: list[str] = Field(default_factory=list)
    age_marker_stems: list[str] = Field(default_factory=list)
    payment_receiver_stems: list[str] = Field(default_factory=list)
    payment_giver_stems: list[str] = Field(default_factory=list)
    payment_impersonal_stems: list[str] = Field(default_factory=list)
    dative_endings: list[str] = Field(default_factory=list)
    official_stems: list[str] = Field(default_factory=list)


def load_patterns(resources_root: Path) -> Patterns:
    """Load ``resources/silver/patterns.yaml``."""
    path = resources_root.joinpath(*PATTERNS_RELPATH)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Patterns(**raw)


class Tok(NamedTuple):
    """One Greek-letter token of the *original* (case-preserving) text."""

    surface: str
    folded: str
    start: int
    end: int
    cap: bool


def _first_letter_upper(surface: str) -> bool:
    for ch in surface:
        if is_greek_letter(ch):
            return ch.isupper()
    return False


def _tokens(text: str) -> list[Tok]:
    """Tokenise the original text, carrying case and the folded form."""
    out: list[Tok] = []
    for surface, span in tokenize(text):
        out.append(
            Tok(
                surface=surface,
                folded=normalize(surface).text,
                start=span.start,
                end=span.end,
                cap=_first_letter_upper(surface),
            )
        )
    return out


def _stem_match(folded: str, stems: list[str]) -> bool:
    return any(folded.startswith(s) for s in stems)


class _Occupied:
    """Tracks character ranges already claimed by an entity."""

    def __init__(self, spans: list[tuple[int, int]]) -> None:
        self._spans = list(spans)

    def hit(self, start: int, end: int) -> bool:
        return any(start < b and a < end for a, b in self._spans)

    def add(self, start: int, end: int) -> None:
        self._spans.append((start, end))


def _facing_distance(a: CharSpan, b: CharSpan) -> int:
    if a.end <= b.start:
        return b.start - a.end
    if b.end <= a.start:
        return a.start - b.end
    return 0


class SilverLabeler:
    """Baseline economic spans plus the PERSON/PLACE/TRANSACTION/ROLE/AGE LFs."""

    def __init__(
        self,
        matcher: Matcher,
        patterns: Patterns,
        *,
        window: int = DEFAULT_WINDOW,
        label_dist: LabelDist | None = None,
        place_min_count: int = 5,
        place_min_share: float = 0.75,
        place_max_person_share: float = 0.15,
    ) -> None:
        self.matcher = matcher
        self.p = patterns
        self.window = window
        self.label_dist = label_dist
        self.place_gazetteer = _derive_place_gazetteer(
            label_dist, place_min_count, place_min_share, place_max_person_share
        )

    # -- the added entity labeling functions ---------------------------------

    def _bridges(self, gap: list[str]) -> bool:
        """Whether a gap between two capitalised tokens keeps them in one span.

        Filiation articles and junior/senior tags always bridge; the alias
        formula ``ὁ/ὃς καὶ`` bridges; a bare ``καί`` does **not** (``X καὶ Y``
        are two parties).
        """
        if not gap:
            return True
        articles = set(self.p.name_bridge_articles) | set(self.p.name_bridge_junior)
        if all(t in articles for t in gap):
            return True
        alias = set(self.p.name_alias_pronouns)
        if len(gap) == 1 and gap[0] in alias:
            return True
        return len(gap) == 2 and gap[0] in alias and gap[1] == "και"

    def _is_titulature(self, folded: str) -> bool:
        return _stem_match(folded, self.p.titulature_stems)

    def _is_month(self, folded: str) -> bool:
        return _stem_match(folded, self.p.month_stems)

    def _capital_runs(
        self, tokens: list[Tok], occ: _Occupied
    ) -> list[tuple[int, int]]:
        """Maximal token-index runs of capitalised tokens, filiation-bridged."""
        runs: list[tuple[int, int]] = []
        n = len(tokens)
        i = 0
        while i < n:
            tok = tokens[i]
            if not tok.cap or occ.hit(tok.start, tok.end):
                i += 1
                continue
            last = i
            j = i + 1
            while j < n:
                nxt = tokens[j]
                if nxt.cap and not occ.hit(nxt.start, nxt.end):
                    last = j
                    j += 1
                    continue
                # Collect the gap of non-eligible tokens up to the next cap.
                k = j
                gap: list[str] = []
                while k < n and not (tokens[k].cap and not occ.hit(tokens[k].start, tokens[k].end)):
                    gap.append(tokens[k].folded)
                    k += 1
                if k < n and self._bridges(gap):
                    last = k
                    j = k + 1
                    continue
                break
            runs.append((i, last))
            i = last + 1
        return runs

    def _classify_run(
        self, run: tuple[int, int], tokens: list[Tok]
    ) -> tuple[str, int, int] | None:
        """Return ``(label, start, end)`` for a capitalised run, or None."""
        a, b = run
        run_toks = tokens[a : b + 1]
        folded_join = [t.folded for t in run_toks]
        start, end = tokens[a].start, tokens[b].end

        is_place = any(
            _stem_match(f, self.p.place_gazetteer_stems) for f in folded_join
        )
        prev = tokens[a - 1] if a > 0 else None
        nxt = tokens[b + 1] if b + 1 < len(tokens) else None
        if nxt is not None and _stem_match(nxt.folded, self.p.place_admin_stems):
            is_place, end = True, nxt.end
        if prev is not None and _stem_match(prev.folded, self.p.place_admin_stems):
            is_place, start = True, prev.start
        if prev is not None and prev.folded in self.p.place_prepositions:
            is_place = True

        if is_place:
            return PLACE, start, end

        # PERSON needs a real name token: multi-letter, not titulature, not a
        # calendar month that slipped past the date lexicon.
        has_name = any(
            len(t.folded) >= 2 and not self._is_titulature(t.folded) and not self._is_month(t.folded)
            for t in run_toks
            if t.cap
        )
        if not has_name:
            return None
        return PERSON, tokens[a].start, tokens[b].end

    # -- orchestration -------------------------------------------------------

    def label(
        self, text: str, numeral_spans: list[CharSpan], line_spans: list[CharSpan]
    ) -> WeakLabeling:
        base = label_document(text, numeral_spans, line_spans, self.matcher, window=self.window)
        entities: list[WeakEntity] = list(base.entities)
        relations: list[WeakRelation] = list(base.relations)

        tokens = _tokens(text)
        age_tokens = [t for t in tokens if _stem_match(t.folded, self.p.age_marker_stems)]

        # AGE: a <num> immediately AFTER ἐτῶν ("(ὡς) ἐτῶν N" = "N years old"),
        # the genitive plural — distinct from ἔτους/ἔτει/ἔτος (regnal year →
        # DATE_REF). The baseline swallows the numeral into a DATE_REF span
        # ("ἐτῶν μα") because ἐτῶν is a year-word, so reclassifying only QUANTITY
        # missed every age (133 gold, 0 found). Build AGE from the numeral span
        # itself (gold AGE is the numeral only) and drop whatever baseline entity
        # covers it. Ordering is load-bearing: "N ἐτῶν" (τεσσάρων ἐτῶν, "four
        # years" — a lease term) has the numeral *before* ἐτῶν and is excluded.
        etwn_ends = [t.end for t in age_tokens]
        age_spans = [
            n for n in numeral_spans
            if any(0 <= n.start - e <= AGE_ADJACENCY for e in etwn_ends)
        ]
        if age_spans:
            entities = [
                e
                for e in entities
                if not any(n.start < e.span.end and e.span.start < n.end for n in age_spans)
            ]
            for n in age_spans:
                entities.append(WeakEntity(label=AGE, span=n, text=n.slice(text)))

        occ = _Occupied([(e.span.start, e.span.end) for e in entities])

        def _add(label: str, start: int, end: int) -> None:
            span = CharSpan(start=start, end=end)
            entities.append(WeakEntity(label=label, span=span, text=span.slice(text)))
            occ.add(start, end)

        # TRANSACTION — closed-class stems. These are lowercase common words
        # (0/41 gold transactions are capitalised), so the cap guard keeps a
        # name that merely shares a stem (Κτησ-, Πρασ-) out. One anchor per
        # document: a deal restated several times gets a single TRANSACTION.
        for tok in tokens:
            if tok.cap or occ.hit(tok.start, tok.end):
                continue
            if _stem_match(tok.folded, self.p.transaction_stems):
                _add(TRANSACTION, tok.start, tok.end)
                break

        # PERSON_ROLE — role stem, pulling in a preceding determiner/preposition.
        # Also lowercase (0/20 gold roles are capitalised): the guard stops a
        # name like Ἀνδρονίκου (ανδρ-) or Κυρ- being mistaken for a role.
        for idx, tok in enumerate(tokens):
            if tok.cap or occ.hit(tok.start, tok.end):
                continue
            prev = tokens[idx - 1] if idx > 0 else None
            if _stem_match(tok.folded, self.p.role_stems):
                start = tok.start
                if prev is not None and prev.folded in self.p.role_determiners:
                    start = prev.start
                _add(PERSON_ROLE, start, tok.end)
            elif _stem_match(tok.folded, self.p.role_guarded_stems):
                # A gated role (κύριος) counts only inside its guardian formula,
                # and the μετά/χωρίς is part of the span.
                if prev is not None and prev.folded in self.p.role_guard_determiners:
                    _add(PERSON_ROLE, prev.start, tok.end)

        # PERSON / PLACE — capitalised runs.
        for run in self._capital_runs(tokens, occ):
            classified = self._classify_run(run, tokens)
            if classified is None:
                continue
            label, start, end = classified
            if occ.hit(start, end):
                continue
            _add(label, start, end)

        if self.place_gazetteer:
            entities = self._promote_places(entities)

        entities = [e.model_copy(update={"confidence": self._confidence(e)}) for e in entities]
        relations.extend(self._relations(entities, tokens))
        relations.extend(self._direction_relations(entities, tokens))
        relations.extend(self._attribute_relations(entities))
        return WeakLabeling(entities=entities, relations=relations)

    def _confidence(self, ent: WeakEntity) -> float:
        """Calibrated confidence for one entity.

        For surface-decided labels (PERSON/PLACE/…) it is the corpus-wide share
        of that form taking this label — validated to predict correctness, with
        the 0.7–0.9 band the empirical danger zone. Unseen novel forms get a
        conservative prior; numeral/lexicon labels get their measured precision.
        """
        if ent.label in DIST_LABELS:
            if self.label_dist is None:
                return SOURCE_CONFIDENCE.get(ent.label, 0.7)
            dist = self.label_dist.get(normalize(ent.text).text)
            if dist is None:
                return UNSEEN_DIST_PRIOR
            total = sum(dist.values())
            return dist.get(ent.label, 0) / total if total else UNSEEN_DIST_PRIOR
        return SOURCE_CONFIDENCE.get(ent.label, 0.7)

    def _promote_places(self, entities: list[WeakEntity]) -> list[WeakEntity]:
        """Relabel PERSON → PLACE for corpus-attested unambiguous toponyms.

        Directional on purpose: a plain majority vote flips place-dominant
        forms the wrong way (a run without local admin context defaults to
        PERSON), so only promotion is safe, and only for forms the corpus shows
        are place-dominant and almost never a person. An eponymous name
        (Ἡρακλείδου) is never in the gazetteer. The gain is recall on toponyms
        that carry admin context elsewhere in the corpus but appear bare here.
        """
        out: list[WeakEntity] = []
        for ent in entities:
            if ent.label == PERSON and normalize(ent.text).text in self.place_gazetteer:
                out.append(ent.model_copy(update={"label": PLACE}))
            else:
                out.append(ent)
        return out

    def _party_person_indices(
        self, entities: list[WeakEntity], tokens: list[Tok]
    ) -> set[int]:
        """PERSON entities introduced by a party preposition (παρά/διά/ὑπό).

        Linking every person to the transaction over-links (rulers, mothers and
        witnesses are not parties); the introducing preposition is the signal
        that a name is a contracting party.
        """
        start_to_tok = {t.start: i for i, t in enumerate(tokens)}
        flagged: set[int] = set()
        for ei, ent in enumerate(entities):
            if ent.label != PERSON:
                continue
            ti = start_to_tok.get(ent.span.start)
            if ti is not None and ti > 0 and tokens[ti - 1].folded in self.p.party_prepositions:
                flagged.add(ei)
        return flagged

    def _relations(
        self, entities: list[WeakEntity], tokens: list[Tok]
    ) -> list[WeakRelation]:
        """PARTY_OF, DATED_TO and HAS_PRICE over the full entity set."""
        by: dict[str, list[int]] = {}
        for i, e in enumerate(entities):
            by.setdefault(e.label, []).append(i)

        rels: list[WeakRelation] = []

        def _nearest_idx(anchor: int, candidates: list[int]) -> int | None:
            a = entities[anchor].span
            best: tuple[int, int] | None = None
            for c in candidates:
                d = _facing_distance(a, entities[c].span)
                if best is None or d < best[0]:
                    best = (d, c)
            return best[1] if best else None

        def _link(rel_type: str, head: int, tail: int) -> None:
            d = _facing_distance(entities[head].span, entities[tail].span)
            rels.append(
                WeakRelation(
                    type=rel_type,
                    head=head,
                    tail=tail,
                    distance=d,
                    confidence=RELATION_CONFIDENCE.get(rel_type, 0.5),
                )
            )

        transactions = by.get(TRANSACTION, [])
        dates = by.get(DATE_REF, [])
        money = by.get(MONEY_AMOUNT, [])

        # Parties = every role word (a role in a contract is a party), every
        # preposition-introduced name, and the nearest name to each transaction
        # (usually the verb's subject — the principal party, unprefixed).
        if transactions:
            party_persons = self._party_person_indices(entities, tokens)
            for t in transactions:
                subj = _nearest_idx(t, by.get(PERSON, []))
                if subj is not None:
                    party_persons.add(subj)
            for party in sorted(set(by.get(PERSON_ROLE, [])) | party_persons):
                tx = _nearest_idx(party, transactions)
                if tx is not None:
                    _link(PARTY_OF, party, tx)

        # Each transaction takes the nearest date within a clause's reach.
        for t in transactions:
            d = _nearest_idx(t, dates)
            if d is not None and _facing_distance(entities[t].span, entities[d].span) <= self.window * 3:
                _link(DATED_TO, t, d)

        # A commodity's price is the nearest money amount inside the window.
        for c in by.get(COMMODITY, []):
            m = _nearest_idx(c, money)
            if m is not None and _facing_distance(entities[c].span, entities[m].span) <= self.window:
                _link(HAS_PRICE, c, m)

        return rels

    def _is_dative(self, text: str) -> bool:
        """Whether a person span's HEAD name looks dative — a weak payee cue.

        The head token carries the case; filiation that follows is genitive, so
        only the first token is tested. A heuristic (endings overlap other
        cases), which is why the constructions that rely on it are low-confidence.
        """
        head = normalize(text).text.split()
        return bool(head) and any(head[0].endswith(e) for e in self.p.dative_endings)

    def _direction_relations(
        self, entities: list[WeakEntity], tokens: list[Tok]
    ) -> list[WeakRelation]:
        """PAID_BY / PAID_TO — payment direction, anchored on the payment verb.

        For each payment verb (classed giver/receiver/impersonal from the mined
        verb map) that has an amount within reach, the verb *class* decides how
        the surrounding names map to payer and payee:

        * receiver verb — a παρά-marked name is the payer (the cleanest signal);
          the preceding name (the subject) is the payee;
        * giver verb — the nearest name (the subject) is the payer; a following
          dative name is the payee;
        * impersonal τέτακται — the following name (the taxpayer) is the payer.

        Firing requires an amount (MONEY_AMOUNT/COMMODITY) near the verb — the
        filter that separates a transferred sum from a received *letter* or a
        submitted *petition*, the false positives a bare παρά rule collects.
        """
        amounts = [i for i, e in enumerate(entities) if e.label in (MONEY_AMOUNT, COMMODITY)]
        persons = [i for i, e in enumerate(entities) if e.label in (PERSON, PERSON_ROLE)]
        if not amounts or not persons:
            return []

        start_to_tok = {t.start: k for k, t in enumerate(tokens)}

        def prev_fold(ei: int) -> str:
            ti = start_to_tok.get(entities[ei].span.start)
            return tokens[ti - 1].folded if ti is not None and ti > 0 else ""

        agent_articles = set(self.p.name_bridge_articles) | {"ο", "η"}

        def is_para(ei: int) -> bool:
            """A name introduced by the *preposition* παρά (not παρών "present").

            Covers both the bare 'παρὰ Παοῦτος' and 'παρὰ τοῦ Ἰουλίου' where an
            article stands between παρά and the name (very common: "from the X").
            """
            if prev_fold(ei) in {"παρα", "παρ"}:
                return True
            ti = start_to_tok.get(entities[ei].span.start)
            return (
                ti is not None
                and ti >= 2
                and tokens[ti - 1].folded in agent_articles
                and tokens[ti - 2].folded in {"παρα", "παρ"}
            )

        def para_is_agent(ei: int) -> bool:
            """παρά-name that is an agent-of reference, not a payer.

            'ὁ παρὰ Σώσου (κεχρημάτικα)' (Sosos' clerk) and 'τοῦ παρὰ Πανίσκου
            ἀγορανόμου' (before Paniskos the agoranomos) both put an article
            immediately before παρά; a real payer has a bare 'παρὰ Παοῦτος'. An
            official title right after the name is the same tell from the far side.
            """
            ti = start_to_tok.get(entities[ei].span.start)
            if ti is not None and ti >= 2 and tokens[ti - 2].folded in agent_articles:
                return True
            nxt = next((t for t in tokens if t.start >= entities[ei].span.end), None)
            return nxt is not None and _stem_match(nxt.folded, self.p.official_stems)

        def nearest(anchor: CharSpan, cands: Iterable[int], *, side: int = 0) -> int | None:
            """Nearest candidate to ``anchor``; side>0 after only, side<0 before."""
            best: tuple[int, int] | None = None
            for c in cands:
                s = entities[c].span
                if (side > 0 and s.start < anchor.end) or (side < 0 and s.end > anchor.start):
                    continue
                d = _facing_distance(anchor, s)
                if best is None or d < best[0]:
                    best = (d, c)
            return best[1] if best else None

        rels: list[WeakRelation] = []
        seen: set[tuple[str, int, int]] = set()

        def emit(rtype: str, head: int | None, tail: int | None, key: str) -> None:
            if head is None or tail is None or head == tail or (rtype, head, tail) in seen:
                return
            seen.add((rtype, head, tail))
            rels.append(
                WeakRelation(
                    type=rtype,
                    head=head,
                    tail=tail,
                    distance=_facing_distance(entities[head].span, entities[tail].span),
                    confidence=PAID_CONFIDENCE[key],
                )
            )

        reach = self.window * 4
        # παρά-introduced names are payer candidates — but not the 'ὁ παρὰ X'
        # agent/official of a dating or subscription clause, who is not a party.
        para = {i for i in persons if is_para(i) and not para_is_agent(i)}
        for tok in tokens:
            if _stem_match(tok.folded, self.p.payment_receiver_stems):
                cls = "recv"
            elif _stem_match(tok.folded, self.p.payment_giver_stems):
                cls = "give"
            elif _stem_match(tok.folded, self.p.payment_impersonal_stems):
                cls = "impersonal"
            else:
                continue
            vspan = CharSpan(start=tok.start, end=tok.end)
            amount = nearest(vspan, amounts)
            if amount is None or _facing_distance(vspan, entities[amount].span) > reach:
                continue  # precision filter: no amount near the verb -> not a transfer

            # Everything is kept inside the verb's own clause (within `reach`), so
            # a παρά from another clause or the dating formula cannot be borrowed.
            near = [i for i in persons if _facing_distance(vspan, entities[i].span) <= reach]
            if cls == "recv":
                payer = nearest(vspan, [i for i in near if i in para and entities[i].span.start >= vspan.start], side=1)
                payee = nearest(vspan, [i for i in near if i != payer], side=-1)
                emit(PAID_BY, payer, amount, "recv_para")
                emit(PAID_TO, payee, amount, "recv_subj")
            elif cls == "give":
                # The dative name after the verb is the PAYEE (διέγραψε Σεκούνδῳ
                # "paid to Secundus"); the payer is a non-dative subject, never
                # that dative recipient sitting next to the verb.
                dative_after = [
                    i for i in near
                    if entities[i].span.start >= vspan.start and self._is_dative(entities[i].text)
                ]
                payee = nearest(vspan, dative_after, side=1)
                payer = nearest(vspan, [i for i in near if i != payee and not self._is_dative(entities[i].text)])
                emit(PAID_BY, payer, amount, "give_subj")
                emit(PAID_TO, payee, amount, "give_dat")
            else:  # impersonal τέτακται — the following name is the taxpayer (payer)
                payer = nearest(vspan, [i for i in near if entities[i].span.start >= vspan.start], side=1)
                emit(PAID_BY, payer, amount, "impersonal")

        return rels

    def _attribute_relations(self, entities: list[WeakEntity]) -> list[WeakRelation]:
        """HAS_OCCUPATION / HAS_AGE — attribute apposition (Phase 8b).

        Delegates the adjacency logic to the pure, unit-tested
        :func:`oikonomia.labeling.apposition.attribute_relations` (each
        OCCUPATION/AGE linked to the nearest PERSON/PERSON_ROLE that *ends before*
        it), and only wraps its ``(head, tail, type)`` output into
        :class:`WeakRelation` with the facing distance and the type's provisional
        confidence. Keeping the rule pure means it is shared, unchanged, with the
        gold-draft tool.
        """
        spans = [(e.span.start, e.span.end, e.label) for e in entities]
        rels: list[WeakRelation] = []
        for head, tail, rtype in attribute_relations(spans):
            rels.append(
                WeakRelation(
                    type=rtype,
                    head=head,
                    tail=tail,
                    distance=_facing_distance(entities[head].span, entities[tail].span),
                    confidence=RELATION_CONFIDENCE.get(rtype, 0.5),
                )
            )
        return rels


def _derive_place_gazetteer(
    label_dist: LabelDist | None, min_count: int, min_share: float, max_person_share: float
) -> frozenset[str]:
    """Forms that are place-dominant and almost never a person."""
    if not label_dist:
        return frozenset()
    gaz: set[str] = set()
    for form, dist in label_dist.items():
        total = sum(dist.values())
        if total < min_count:
            continue
        if dist.get(PLACE, 0) / total >= min_share and dist.get(PERSON, 0) / total <= max_person_share:
            gaz.add(form)
    return frozenset(gaz)


def fit_label_dist(
    labeler: SilverLabeler, batches: Iterable[Any], *, min_count: int = 3
) -> LabelDist:
    """Tally each surface form's label distribution across corpus batches.

    The labeler must be gazetteer-free here (we are *building* the table from
    its raw output). Only :data:`DIST_LABELS` are tallied.
    """
    dist: dict[str, Counter[str]] = defaultdict(Counter)
    for frame in batches:
        for blob in frame["document_json"]:
            doc = json.loads(blob)
            text = doc.get("edited_text") or ""
            if not text.strip():
                continue
            numerals, lines = doc_spans(doc)
            for ent in labeler.label(text, numerals, lines).entities:
                if ent.label in DIST_LABELS:
                    folded = normalize(ent.text).text
                    if len(folded) >= 2:
                        dist[folded][ent.label] += 1

    return {
        folded: dict(counter)
        for folded, counter in dist.items()
        if sum(counter.values()) >= min_count
    }


def save_label_dist(label_dist: LabelDist, path: Path) -> None:
    path.write_text(json.dumps(label_dist, ensure_ascii=False), encoding="utf-8")


def load_label_dist(path: Path) -> LabelDist:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): {str(lab): int(c) for lab, c in v.items()} for k, v in raw.items()}
