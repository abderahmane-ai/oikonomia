"""Long-document–safe candidate construction for corpus-scale relation inference.

The saved span-pair RE model (``modal_app/relations.py::launch`` → the
``oikonomia-ner`` Volume) is trained on gold docs that all fit one 512-token
window. Running it over the *whole* corpus means feeding it the NER model's
corpus-scale entities (``ner_corpus.jsonl``) — and 5.4% of documents tokenize to
more than 512 tokens. Truncating there would silently drop every party and
payment past the cutoff, i.e. exactly the long petitions, leases and accounts the
"women as principals" finding needs.

This module owns the **pure, model-free** half of that inference so it stays
laptop-testable, mirroring :mod:`oikonomia.ner.inference` for the entity model:

* windowing reuses :func:`oikonomia.ner.inference.plan_windows` (one stride
  policy, one place);
* :func:`build_window_candidates` turns one window's token offsets + the
  document's entities into the exact :class:`Cand` feature tuples the model's
  ``score_pairs`` consumes — reusing the frozen candidate generator
  (:func:`oikonomia.relations.encode.label_candidates`, type-admissible and
  gap-pruned) and the symbolic direction features;
* :func:`merge_scored` folds the per-window scored edges back into one set,
  keeping the highest-scoring reading of each entity pair the overlap produced.

The GPU half (tokenize → forward → mask/softmax/argmax → :func:`constrain`) is the
thin Modal entrypoint ``modal_app/relations.py::infer_corpus``; it feeds this
module a window's offsets and reads back candidates and merged edges. Candidate
indices ``h``/``t`` are **global** entity indices (into the document's full entity
list), so predictions from different windows compose without a reindex step.
"""

from __future__ import annotations

from typing import NamedTuple

from oikonomia.relations.encode import (
    Entity,
    Offset,
    char_span_to_token_range,
    label_candidates,
)
from oikonomia.relations.features import (
    PaymentLexicon,
    context_window,
    direction_features_from_folded,
)

__all__ = ["Cand", "ScoredEdge", "build_window_candidates", "merge_scored"]

# (global head/tail entity idx, head/tail token range, wide-context token range,
#  head/tail type-embedding id, 3 direction-feature ids, head/tail labels). The
#  field order and names match the ``namedtuple`` the model's ``score_pairs`` and
#  ``predict`` read — this is the single definition both training-time and
#  inference-time code build.
class Cand(NamedTuple):
    """One scored candidate pair, with window-local token ranges + global indices."""

    h: int
    t: int
    h0: int
    h1: int
    t0: int
    t1: int
    w0: int
    w1: int
    htid: int
    ttid: int
    vc: int
    vp: int
    pm: int
    hlab: str
    tlab: str


ScoredEdge = tuple[int, int, str, float]  # (global head, global tail, type, prob)


def build_window_candidates(
    entities: list[Entity],
    win_offsets: list[Offset],
    folded: str,
    ent2id: dict[str, int],
    lex: PaymentLexicon,
) -> list[Cand]:
    """Candidate feature tuples for the entities visible in one token window.

    ``win_offsets`` is the window's per-token ``(char_start, char_end)`` mapping,
    including the two special-token slots the caller wraps each window in (a
    ``(0, 0)`` at each end), so returned token ranges index directly into the
    model's hidden-state row for that window. An entity whose character span does
    not overlap any real token in the window is invisible here and simply not
    paired — the neighbouring (overlapping) window sees it whole.

    Candidate generation, type-admissibility and the local-family gap prune are
    the frozen ones from :mod:`oikonomia.relations.encode`; the head/tail indices
    on each :class:`Cand` are **global** (into ``entities``), so the caller can
    merge windows without reindexing.
    """
    ranges = [char_span_to_token_range(win_offsets, s, e) for s, e, _ in entities]
    keep = [i for i, r in enumerate(ranges) if r is not None]
    if len(keep) < 2:
        return []
    kept_ents = [entities[i] for i in keep]
    kept_ranges = [ranges[i] for i in keep]

    cands: list[Cand] = []
    for lh, lt, _ in label_candidates(kept_ents, []):  # no gold rels at inference
        rh, rt = kept_ranges[lh], kept_ranges[lt]
        assert rh is not None and rt is not None  # keep -> range is not None
        hc = (kept_ents[lh][0], kept_ents[lh][1])
        tc = (kept_ents[lt][0], kept_ents[lt][1])
        wlo, whi = context_window(hc, tc)
        wr = char_span_to_token_range(win_offsets, wlo, whi) or (
            min(rh[0], rt[0]),
            max(rh[1], rt[1]),
        )
        f = direction_features_from_folded(folded, hc, tc, lex)
        hlab, tlab = kept_ents[lh][2], kept_ents[lt][2]
        cands.append(
            Cand(
                h=keep[lh],
                t=keep[lt],
                h0=rh[0],
                h1=rh[1],
                t0=rt[0],
                t1=rt[1],
                w0=wr[0],
                w1=wr[1],
                htid=ent2id[hlab],
                ttid=ent2id[tlab],
                vc=f.verb_class,
                vp=f.verb_pos,
                pm=f.payer_mark,
                hlab=hlab,
                tlab=tlab,
            )
        )
    return cands


def merge_scored(scored: list[ScoredEdge]) -> list[ScoredEdge]:
    """Fold per-window scored edges into one edge per ordered entity pair.

    Overlapping windows can score the same ``(head, tail)`` pair twice (and, near
    a seam, with different types); keep the single highest-probability reading.
    Deterministic: ties keep the first seen, so a stable window order gives a
    stable result. The kept edges still carry their score for
    :func:`oikonomia.relations.decode.constrain` to break functional-head ties.
    """
    best: dict[tuple[int, int], ScoredEdge] = {}
    for edge in scored:
        h, t, _ty, s = edge
        key = (h, t)
        cur = best.get(key)
        if cur is None or s > cur[3]:
            best[key] = edge
    return list(best.values())
