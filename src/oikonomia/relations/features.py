"""Neuro-symbolic features for the payment-direction / party-role head (Phase 8a).

Direction (PAID_BY vs PAID_TO) is the measured bottleneck (gold: PAID_BY 0.15,
PAID_TO 0.30), and the data audit showed why: it is verb-governed but *not*
verb-class alone. The same verb class flips role by the payer's grammatical
marking — *ἔσχον παρὰ σοῦ* (subject = payee, παρά = payer) vs *διέγραψεν X τῷ Y*
(subject = payer, dative = payee). On gold, the governing verb sits **between**
payer and amount 75% of the time, **before** the payer 25%, and is absent near
39% of edges; PAID_BY and PAID_TO both draw on receiver *and* giver verbs.

So the direction head is fed compact SYMBOLIC features distilled from the mined
verb lexicon (`resources/silver/patterns.yaml`) plus case morphology, alongside
the neural context — the lexicon becomes *features*, not brittle rules, and the
model learns the exceptions the Phase-5c rules miss.

Pure and torch-free: computed from ``(text, head_span, tail_span)`` + the
lexicon, so it is unit-testable on a laptop. Folding is offset-stable (a dropped
combining mark maps to a space) so search positions line up with the text.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import yaml
from pydantic import BaseModel

from oikonomia.labeling.normalize import fold_char

Span = tuple[int, int]  # (char_start, char_end)

# --- Categorical feature values (small ints, embedded by the direction head) ---
# Verb class of the nearest governing payment verb.
VERB_NONE, VERB_RECEIVER, VERB_GIVER, VERB_IMPERSONAL = 0, 1, 2, 3
# Where that verb sits relative to the payer (head) span.
POS_NONE, POS_BEFORE_HEAD, POS_BETWEEN, POS_AFTER = 0, 1, 2, 3
# How the payer (head PERSON) is grammatically marked.
MARK_OTHER, MARK_PARA, MARK_DATIVE, MARK_ARTICLE_PARA = 0, 1, 2, 3

# Cardinality of each categorical feature — the direction head builds one
# embedding table per feature from these.
FEATURE_CARDINALITIES: tuple[int, int, int] = (4, 4, 4)

# How far before the payer to look for a governing verb / marking (chars). The
# audit put pre-head verbs within ~40 chars; markings sit immediately before.
_VERB_LOOKBACK = 40
_MARK_LOOKBACK = 14

# Greek article forms (folded) that precede "παρά" in the agent-of construction
# `ὁ/τοῦ παρὰ X` — X is then an official/agent, never the payer (Phase-5c bug).
_ARTICLES = ("ο", "του", "τω", "τον", "οι", "των", "τοισ", "η", "της", "τη")
_PARA = "παρα"


class PaymentLexicon(BaseModel):
    """The payment-verb + morphology stems the features need (from patterns.yaml)."""

    receiver: list[str] = []
    giver: list[str] = []
    impersonal: list[str] = []
    dative_endings: list[str] = []


def load_payment_lexicon(resources_root: Path) -> PaymentLexicon:
    """Read the payment stems from ``resources/silver/patterns.yaml``."""
    raw = yaml.safe_load((resources_root / "silver" / "patterns.yaml").read_text(encoding="utf-8"))
    return PaymentLexicon(
        receiver=raw.get("payment_receiver_stems", []),
        giver=raw.get("payment_giver_stems", []),
        impersonal=raw.get("payment_impersonal_stems", []),
        dative_endings=raw.get("dative_endings", []),
    )


class DirectionFeatures(NamedTuple):
    """The symbolic feature triple fed (as embeddings) to the direction head."""

    verb_class: int
    verb_pos: int
    payer_mark: int


def fold(text: str) -> str:
    """Offset-stable fold: each original char maps to one folded char (or a space).

    A dropped combining mark becomes a space rather than nothing, so
    ``len(fold(text)) == len(text)`` and a match position in the folded string is
    the same index in ``text``.
    """
    return "".join(fold_char(c) or " " for c in text)


def _first_hit(folded: str, stems: list[str], lo: int, hi: int) -> int | None:
    """Leftmost start index in ``[lo, hi)`` where any stem occurs, else None."""
    best: int | None = None
    for stem in stems:
        idx = folded.find(stem, max(0, lo), hi)
        if idx != -1 and (best is None or idx < best):
            best = idx
    return best


def _nearest_verb(folded: str, head: Span, tail: Span, lex: PaymentLexicon) -> tuple[int, int]:
    """(verb_class, verb_pos) of the payment verb nearest the pair, or (NONE, NONE)."""
    lo = min(head[0], tail[0]) - _VERB_LOOKBACK
    hi = max(head[1], tail[1]) + 10
    candidates = [
        (VERB_RECEIVER, _first_hit(folded, lex.receiver, lo, hi)),
        (VERB_GIVER, _first_hit(folded, lex.giver, lo, hi)),
        (VERB_IMPERSONAL, _first_hit(folded, lex.impersonal, lo, hi)),
    ]
    anchor = min(head[0], tail[0])
    best_cls, best_idx, best_d = VERB_NONE, None, None
    for cls, idx in candidates:
        if idx is None:
            continue
        d = abs(idx - anchor)
        if best_d is None or d < best_d:
            best_cls, best_idx, best_d = cls, idx, d
    if best_idx is None:
        return VERB_NONE, POS_NONE
    if best_idx < head[0]:
        pos = POS_BEFORE_HEAD
    elif best_idx < max(head[1], tail[0]):
        pos = POS_BETWEEN
    else:
        pos = POS_AFTER
    return best_cls, pos


def _payer_marking(folded: str, head: Span, lex: PaymentLexicon) -> int:
    """How the payer (head) is marked: παρά (+article?), dative ending, or other."""
    pre = folded[max(0, head[0] - _MARK_LOOKBACK) : head[0]]
    para_at = pre.rfind(_PARA)
    if para_at != -1:
        before_para = pre[:para_at].split()
        if before_para and before_para[-1] in _ARTICLES:
            return MARK_ARTICLE_PARA  # `ὁ/τοῦ παρὰ X` — an agent, not the payer
        return MARK_PARA
    head_tokens = folded[head[0] : head[1]].split()
    if head_tokens and any(head_tokens[-1].endswith(e) for e in lex.dative_endings if e):
        return MARK_DATIVE
    return MARK_OTHER


def direction_features_from_folded(
    folded: str, head: Span, tail: Span, lex: PaymentLexicon
) -> DirectionFeatures:
    """Direction features from a pre-folded text (fold the doc once, reuse per pair)."""
    verb_class, verb_pos = _nearest_verb(folded, head, tail, lex)
    payer_mark = _payer_marking(folded, head, lex)
    return DirectionFeatures(verb_class=verb_class, verb_pos=verb_pos, payer_mark=payer_mark)


def direction_features(text: str, head: Span, tail: Span, lex: PaymentLexicon) -> DirectionFeatures:
    """Compute the symbolic direction-feature triple for a (payer, amount) pair.

    ``head`` is the PERSON/PERSON_ROLE span, ``tail`` the MONEY_AMOUNT/COMMODITY.
    """
    return direction_features_from_folded(fold(text), head, tail, lex)


def context_window(head: Span, tail: Span, *, pad: int = _VERB_LOOKBACK) -> Span:
    """Char window the direction head should pool over: pad-before-payer → amount-end.

    Wider than the strictly-between span so it catches the 25% of governing verbs
    that precede the payer (the audit's ``before_head`` bucket), which the current
    between-span context in ``RelationHead.score_pairs`` misses.
    """
    lo = max(0, min(head[0], tail[0]) - pad)
    hi = max(head[1], tail[1])
    return lo, hi
