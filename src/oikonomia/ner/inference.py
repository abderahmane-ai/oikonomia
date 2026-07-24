"""Long-document–safe windowing for corpus-scale NER inference.

The entity model is a 512-context encoder, but 6.8% of the corpus — and one
459,505-char register — is longer than that. Truncating at 512 tokens would
silently drop every person, place and amount past the cutoff, i.e. exactly the
long petitions and accounts a corpus-scale reading most needs. This module owns
the *chunking* side of inference so it stays pure and unit-testable on a laptop
with no model:

* :func:`plan_windows` slices a document's tokens into overlapping windows that
  together cover every token — the stride policy, stated once, in one place.
* :func:`merge_window_spans` folds the per-window predictions back into one span
  set, resolving the duplicates and truncated fragments the overlap produces.

The GPU half (tokenize → forward → argmax → :func:`decode_spans`) lives in the
thin Modal entrypoint (``modal_app/ner.py``); it feeds this module a token count
per window and the per-window decoded spans. Keeping the two halves apart is why
the hard part — the seam logic — is covered by fast, model-free tests.
"""

from __future__ import annotations

from collections.abc import Iterable

from oikonomia.ner.encode import Entity


def plan_windows(n_tokens: int, max_content: int, stride: int) -> list[tuple[int, int]]:
    """Overlapping ``[start, end)`` token-index windows covering all ``n_tokens``.

    ``max_content`` is how many *content* tokens a window may hold — the model's
    context length minus the two special tokens the caller wraps each window in.
    Consecutive windows overlap by ``stride`` tokens so that an entity split by
    one window's edge is seen whole by its neighbour; :func:`merge_window_spans`
    then drops the fragment.

    The final window is clamped to end exactly at ``n_tokens`` and kept full
    width (its start pulled back rather than left as a short tail), so coverage is
    gap-free and every window is the same size — no ragged last chunk for the
    model to behave oddly on.
    """
    if max_content <= 0:
        raise ValueError(f"max_content must be positive, got {max_content}")
    if not 0 <= stride < max_content:
        raise ValueError(
            f"stride must be in [0, max_content); got stride={stride}, max_content={max_content}"
        )
    if n_tokens <= 0:
        return []
    if n_tokens <= max_content:
        return [(0, n_tokens)]

    step = max_content - stride
    windows: list[tuple[int, int]] = []
    start = 0
    while start + max_content < n_tokens:
        windows.append((start, start + max_content))
        start += step
    windows.append((n_tokens - max_content, n_tokens))  # full-width, reaches the end
    return windows


def merge_window_spans(spans: Iterable[Entity]) -> list[Entity]:
    """Fold overlapping-window predictions into one deduplicated span set.

    Overlapping windows create two kinds of redundancy: the *same* entity
    predicted identically in two windows, and a *fragment* of an entity truncated
    at one window's edge sitting next to the whole entity from the neighbour.
    Both are resolved the same way — greedily keep the longest span and drop any
    same-label span that overlaps an already-kept one:

    * exact duplicate → overlaps the first copy, dropped;
    * truncated fragment ⊂ whole → the whole span is longer, kept first; the
      fragment overlaps it, dropped;
    * two distinct adjacent same-label entities → they do not overlap, both kept.

    Spans of *different* labels are never suppressed against one another: a
    per-window :func:`decode_spans` never emits overlapping labels, so any
    cross-label overlap reflects two genuine model opinions for the downstream
    layer to weigh, not a windowing artefact. Deterministic — ties break by
    longest, then earliest start, then end, then label.
    """
    ordered = sorted(set(spans), key=lambda s: (-(s[1] - s[0]), s[0], s[1], s[2]))
    kept: list[Entity] = []
    for s in ordered:
        if any(k[2] == s[2] and s[0] < k[1] and k[0] < s[1] for k in kept):
            continue
        kept.append(s)
    kept.sort(key=lambda s: (s[0], s[1], s[2]))
    return kept
