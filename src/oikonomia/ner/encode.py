"""Char-span ↔ BIO token-label alignment for token-classification NER.

Pure and tokenizer-agnostic: every function takes an ``offsets`` list — the
per-token ``(char_start, char_end)`` pairs a fast tokenizer returns from
``return_offsets_mapping`` — so the logic is unit-testable on a laptop with no
model. A token whose offset has zero length (``end <= start``) is a special or
padding token: it is never labelled (loss ignores it, decoding skips it).

``align_bio`` (char spans → per-token label ids) and ``decode_spans`` (label ids
→ char spans) are inverses on token-aligned entities, which is exactly the
round-trip the test suite pins.
"""

from __future__ import annotations

from collections.abc import Iterable

Entity = tuple[int, int, str]  # (char_start, char_end, label)
Offset = tuple[int, int]  # (char_start, char_end) of one token

IGNORE_INDEX = -100  # torch cross-entropy ignore_index: excluded from the loss.


def build_label_list(labels: Iterable[str]) -> list[str]:
    """BIO label list: ``O`` first (id 0), then ``B-``/``I-`` per type, sorted.

    Sorted so the id assignment is deterministic — a saved model's head indices
    stay stable across rebuilds of the schema.
    """
    out = ["O"]
    for t in sorted(set(labels)):
        out.extend((f"B-{t}", f"I-{t}"))
    return out


def label_maps(label_list: list[str]) -> tuple[dict[str, int], dict[int, str]]:
    """Return ``(label2id, id2label)`` for a BIO label list."""
    label2id = {lab: i for i, lab in enumerate(label_list)}
    id2label = {i: lab for lab, i in label2id.items()}
    return label2id, id2label


def align_bio(
    offsets: list[Offset],
    entities: list[Entity],
    label2id: dict[str, int],
) -> list[int]:
    """Per-token BIO label ids for one document.

    Each token overlapping an entity becomes ``B-TYPE`` (its first token) or
    ``I-TYPE`` (the rest). Special/padding tokens (zero-length offset) get
    ``IGNORE_INDEX``. Overlapping entities resolve first-by-start-offset; a token
    already claimed by an earlier entity is not overwritten. A label outside the
    frozen schema is skipped (the model cannot represent it).
    """
    o_id = label2id["O"]
    labels = [IGNORE_INDEX if end <= start else o_id for start, end in offsets]
    for es, ee, lab in sorted(entities):
        b_id = label2id.get(f"B-{lab}")
        i_id = label2id.get(f"I-{lab}")
        if b_id is None or i_id is None:
            continue
        first = True
        for ti, (cs, ce) in enumerate(offsets):
            if ce <= cs or not (cs < ee and es < ce):
                continue
            if labels[ti] == o_id:
                labels[ti] = b_id if first else i_id
            first = False
    return labels


def decode_spans(
    label_ids: list[int],
    offsets: list[Offset],
    id2label: dict[int, str],
) -> list[Entity]:
    """Inverse of :func:`align_bio`: BIO token ids → ``(start, end, label)`` spans.

    A run of ``B-X`` then ``I-X`` becomes one span from the first token's start
    to the last token's end. Lenient on malformed sequences: a leading ``I-X``
    or a label switch opens a new span, so no prediction is silently dropped.
    """
    spans: list[Entity] = []
    cur_label: str | None = None
    cur_start = cur_end = 0
    for lid, (cs, ce) in zip(label_ids, offsets, strict=False):
        if ce <= cs:  # special / padding token
            continue
        tag = id2label.get(lid, "O")
        if tag == "O":
            if cur_label is not None:
                spans.append((cur_start, cur_end, cur_label))
                cur_label = None
            continue
        bio, _, lab = tag.partition("-")
        if bio == "B" or cur_label != lab:
            if cur_label is not None:
                spans.append((cur_start, cur_end, cur_label))
            cur_label, cur_start, cur_end = lab, cs, ce
        else:  # I- continuing the same label
            cur_end = ce
    if cur_label is not None:
        spans.append((cur_start, cur_end, cur_label))
    return spans
