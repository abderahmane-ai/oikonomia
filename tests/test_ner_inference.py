"""Hand-computed fixtures for the long-doc windowing (plan + merge).

Both functions are pure integer/tuple logic, so the whole seam contract —
coverage without gaps, overlap by ``stride``, and folding truncated fragments
back into whole spans — is pinned here without a tokenizer or a model.
"""

from __future__ import annotations

from itertools import pairwise

from oikonomia.ner.inference import merge_window_spans, plan_windows


def _covers(windows: list[tuple[int, int]], n: int) -> bool:
    """Every token index in ``range(n)`` falls inside at least one window."""
    hit = set()
    for a, b in windows:
        hit.update(range(a, b))
    return hit == set(range(n))


def test_short_doc_is_one_window() -> None:
    assert plan_windows(0, 510, 64) == []
    assert plan_windows(1, 510, 64) == [(0, 1)]
    assert plan_windows(510, 510, 64) == [(0, 510)]


def test_windows_cover_all_tokens_with_overlap() -> None:
    windows = plan_windows(1000, 100, 20)
    assert _covers(windows, 1000)
    # each non-final window is full width and advances by step = max_content - stride
    assert windows[0] == (0, 100)
    assert windows[1] == (80, 180)  # overlaps the previous by stride=20
    assert windows[-1] == (900, 1000)  # clamped full-width, reaches the end
    for a, b in windows:
        assert b - a == 100


def test_final_window_never_a_short_tail() -> None:
    # 105 tokens, width 100: naive tiling would leave a 5-token tail; instead the
    # last window is (5, 105), overlapping the first heavily but full width.
    windows = plan_windows(105, 100, 10)
    assert _covers(windows, 105)
    assert all(b - a == 100 for a, b in windows)
    assert windows[-1] == (5, 105)


def test_windows_are_ordered_and_gap_free() -> None:
    windows = plan_windows(777, 128, 32)
    assert _covers(windows, 777)
    starts = [a for a, _ in windows]
    assert starts == sorted(starts)  # strictly forward
    for (_, b0), (a1, _) in pairwise(windows):
        assert a1 <= b0  # no gap between consecutive windows


def test_merge_drops_exact_duplicates() -> None:
    spans = [(0, 9, "PERSON"), (0, 9, "PERSON"), (10, 17, "CURRENCY")]
    assert merge_window_spans(spans) == [(0, 9, "PERSON"), (10, 17, "CURRENCY")]


def test_merge_drops_truncated_fragment_keeps_whole() -> None:
    # A window cut "Κροκοδίλων πόλει" (45-61) short at 55; the neighbour has it
    # whole. The fragment ⊂ whole, same label → only the whole survives.
    spans = [(45, 55, "PLACE"), (45, 61, "PLACE")]
    assert merge_window_spans(spans) == [(45, 61, "PLACE")]


def test_merge_resolves_partial_seam_overlap_to_longest() -> None:
    # Neither contained in the other, same label, overlapping at a seam → keep the
    # longer, drop the shorter.
    spans = [(10, 18, "PERSON"), (12, 25, "PERSON")]
    assert merge_window_spans(spans) == [(12, 25, "PERSON")]


def test_merge_keeps_distinct_adjacent_same_label() -> None:
    # Two different people back to back: no overlap, both kept.
    spans = [(0, 9, "PERSON"), (10, 19, "PERSON")]
    assert merge_window_spans(spans) == [(0, 9, "PERSON"), (10, 19, "PERSON")]


def test_merge_keeps_cross_label_overlap() -> None:
    # Different labels are not suppressed against each other.
    spans = [(0, 9, "PERSON"), (0, 9, "PLACE")]
    assert merge_window_spans(spans) == [(0, 9, "PERSON"), (0, 9, "PLACE")]


def test_merge_is_deterministic_regardless_of_input_order() -> None:
    a = merge_window_spans([(45, 55, "PLACE"), (45, 61, "PLACE"), (0, 9, "PERSON")])
    b = merge_window_spans([(0, 9, "PERSON"), (45, 61, "PLACE"), (45, 55, "PLACE")])
    assert a == b == [(0, 9, "PERSON"), (45, 61, "PLACE")]
