"""Tests for DAPT text selection and token packing.

The property that matters most is negative: DAPT must never see dev or test.
It is unsupervised, so nothing would complain if it did, and every downstream
number would quietly become meaningless. That is asserted first and directly.

Packing is tested against a trivial fake tokenizer so the ML stack is not
needed to check the logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from oikonomia.dapt.pack import (
    UINT16_MAX,
    encode_documents,
    pack_blocks,
    read_shard,
    write_shard,
)
from oikonomia.dapt.text import iter_dapt_texts, load_split_ids, prepare_for_lm


class FakeTokenizer:
    """One id per character, offset past the specials. Deterministic."""

    def __call__(self, text: str, **kwargs: Any) -> dict[str, list[int]]:
        return {"input_ids": [ord(c) % 1000 + 10 for c in text]}


# --------------------------------------------------------------------------
# Text selection — the leakage guard
# --------------------------------------------------------------------------


@pytest.fixture
def settings(tmp_path: Path):
    from oikonomia.config import load_settings

    s = load_settings(env="local", overrides=[f"paths.root={tmp_path}"])
    s.paths.ensure_writable()

    pd.DataFrame(
        {
            "stem": ["a", "b", "c", "d"],
            "edited_text": [
                "ΠΥΡΟΥ ἈΡΤΆΒΑΣ ΤΕΣΣΑΡΆΚΟΝΤΑ καὶ ἄλλα πολλά",
                "οἴνου κεράμια τέσσαρα παρὰ Σαραπίωνος τοῦ Διονυσίου",
                "κριθῆς ἀρτάβαι δέκα ἐν τῷ ἐνεστῶτι ἔτει τῆς ἰνδικτίονος",
                "μικρόν",  # below min_chars
            ],
        }
    ).to_parquet(s.paths.processed / "corpus.parquet", index=False)

    pd.DataFrame(
        {
            "doc_id": ["a", "b", "c", "d"],
            "split_random": ["train", "dev", "test", "train"],
            "split_chronological": ["train", "train", "dev", "test"],
        }
    ).to_parquet(s.paths.processed / "splits.parquet", index=False)
    return s


def test_dapt_reads_only_the_train_split(settings) -> None:
    """The whole point of Phase 3: dev and test must be unreachable here."""
    texts = list(iter_dapt_texts(settings, regime="split_random", split="train"))
    joined = " ".join(texts)
    assert "ΠΥΡΟΥ" in joined  # doc a, train — case preserved
    assert "κεράμια" not in joined  # doc b is dev
    assert "ἀρτάβαι" not in joined  # doc c is test


def test_regime_is_respected(settings) -> None:
    """The chronological regime assigns the same documents differently."""
    ids = load_split_ids(settings, "split_chronological", "train")
    assert ids == {"a", "b"}


def test_missing_split_table_is_a_hard_error(settings) -> None:
    """Refusing to run beats silently language-modelling the whole corpus."""
    (settings.paths.processed / "splits.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="must not read the whole"):
        load_split_ids(settings, "split_random", "train")


def test_unknown_regime_rejected(settings) -> None:
    with pytest.raises(ValueError, match="regime must be one of"):
        load_split_ids(settings, "split_nonsense", "train")


def test_short_documents_are_dropped(settings) -> None:
    texts = list(iter_dapt_texts(settings, regime="split_random", split="train"))
    assert all(len(t) >= 20 for t in texts)
    assert len(texts) == 1  # doc d is too short, docs b/c are not train


# --------------------------------------------------------------------------
# Case folding
# --------------------------------------------------------------------------


def test_case_is_preserved_by_default() -> None:
    """The regression: lowercasing destroyed the best PERSON/PLACE cue.

    GreBerta tokenises Γεώργιος (a name) and γεωργός (a farmer) to different
    ids, and keeping case costs -0.59% tokens — strictly better on both counts.
    """
    assert prepare_for_lm("Ἡλιοδώρου") == "Ἡλιοδώρου"
    assert prepare_for_lm("Γεώργιος τοῦ γεωργοῦ") == "Γεώργιος τοῦ γεωργοῦ"


def test_lowercase_is_opt_in_for_case_folding_backbones() -> None:
    """GreTa folds case in its own normalizer, so the flag exists for it."""
    assert prepare_for_lm("Ἡλιοδώρου", lowercase=True) == "ἡλιοδώρου"


def test_fold_is_lighter_than_lexicon_normalisation() -> None:
    """Distinct from normalize(): that strips accents, which would push the
    text out of the model's distribution rather than into it."""
    from oikonomia.labeling.normalize import normalize

    raw = "ἈΡΤΆΒΑΣ"
    assert prepare_for_lm(raw) != normalize(raw).text
    assert normalize(raw).text == "αρταβασ"


# --------------------------------------------------------------------------
# Packing
# --------------------------------------------------------------------------


def test_blocks_are_exactly_seq_len() -> None:
    blocks = list(pack_blocks([[1] * 10, [2] * 10], seq_len=4))
    assert all(len(b) == 4 for b in blocks)
    assert len(blocks) == 5  # 20 tokens // 4


def test_trailing_partial_block_is_dropped() -> None:
    blocks = list(pack_blocks([[1] * 9], seq_len=4))
    assert len(blocks) == 2  # 9 tokens -> two full blocks, one token discarded


def test_packing_preserves_token_order_across_documents() -> None:
    blocks = list(pack_blocks([[1, 2, 3], [4, 5, 6]], seq_len=2))
    assert blocks == [[1, 2], [3, 4], [5, 6]]


def test_separator_is_appended_to_each_document() -> None:
    encoded = list(encode_documents(["ab", "cd"], FakeTokenizer(), sep_id=2))
    assert all(ids[-1] == 2 for ids in encoded)
    assert len(encoded) == 2


def test_empty_documents_are_skipped() -> None:
    assert list(encode_documents(["", "a"], FakeTokenizer(), sep_id=2)) != []
    assert len(list(encode_documents(["", ""], FakeTokenizer(), sep_id=2))) == 0


def test_seq_len_must_be_sane() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        list(pack_blocks([[1, 2, 3]], seq_len=1))


# --------------------------------------------------------------------------
# Shard IO
# --------------------------------------------------------------------------


def test_shard_round_trips(tmp_path: Path) -> None:
    blocks = [[1, 2, 3, 4], [5, 6, 7, 8]]
    meta = write_shard(
        iter(blocks), tmp_path / "train.bin", seq_len=4, vocab_size=52000, meta={"split": "train"}
    )
    assert meta["n_blocks"] == 2
    assert meta["n_tokens"] == 8

    arr = read_shard(tmp_path / "train.bin")
    assert arr.shape == (2, 4)
    assert np.array_equal(np.asarray(arr), np.asarray(blocks, dtype=np.uint16))


def test_shard_metadata_records_provenance(tmp_path: Path) -> None:
    write_shard(
        iter([[1, 2]]),
        tmp_path / "train.bin",
        seq_len=2,
        vocab_size=52000,
        meta={"split": "train", "corpus_rev": "abc123", "model_name": "bowphs/GreBerta"},
    )
    meta = json.loads((tmp_path / "train.json").read_text(encoding="utf-8"))
    assert meta["corpus_rev"] == "abc123"
    assert meta["model_name"] == "bowphs/GreBerta"
    assert meta["dtype"] == "uint16"


def test_oversized_vocabulary_is_refused(tmp_path: Path) -> None:
    """uint16 is exact for GreBerta's 52k vocab; it must not silently wrap."""
    with pytest.raises(ValueError, match="exceeds uint16"):
        write_shard(
            iter([[1, 2]]),
            tmp_path / "x.bin",
            seq_len=2,
            vocab_size=UINT16_MAX + 1,
            meta={},
        )


def test_greberta_vocabulary_fits_uint16() -> None:
    """The assumption the shard dtype rests on, asserted rather than assumed."""
    assert UINT16_MAX >= 52000


def test_test_split_is_never_packed() -> None:
    """Phase 4 has no business reading test; the file is not produced at all."""
    from oikonomia.dapt.stage import PACKED_SPLITS

    assert "test" not in PACKED_SPLITS
    assert set(PACKED_SPLITS) == {"train", "dev"}


# --------------------------------------------------------------------------
# Training schedule
# --------------------------------------------------------------------------


def test_schedule_is_derived_from_shard_size(tmp_path: Path) -> None:
    """The regression this exists for: a step count copied from a paper.

    12,500 steps is the published DAPT setting, but against this corpus's
    ~16,200 blocks it is ~49 epochs — the run would look healthy and memorise
    the train split.
    """
    from oikonomia.dapt.schedule import plan

    write_shard(
        iter([[1, 2]] * 16217), tmp_path / "train.bin", seq_len=2, vocab_size=52000, meta={}
    )
    schedule = plan(tmp_path / "train.bin", batch_size=32, grad_accum=2, epochs=8.0)

    assert schedule.steps_per_epoch == 253
    assert schedule.max_steps == 2024
    assert schedule.effective_epochs == pytest.approx(8.0, abs=0.05)
    # The number that would have been used instead:
    assert 12500 / schedule.steps_per_epoch > 45


def test_steps_scale_with_epochs() -> None:
    from oikonomia.dapt.schedule import steps_for_epochs

    assert steps_for_epochs(16217, 32, 2, 8.0) == 2024
    assert steps_for_epochs(16217, 32, 2, 4.0) == 1012
    assert steps_for_epochs(16217, 32, 2, 1.0) == 253


def test_larger_batches_need_fewer_steps() -> None:
    from oikonomia.dapt.schedule import steps_for_epochs

    small = steps_for_epochs(16217, 16, 2, 8.0)
    large = steps_for_epochs(16217, 64, 2, 8.0)
    assert small > large


def test_explicit_max_steps_overrides_the_epoch_budget(tmp_path: Path) -> None:
    from oikonomia.dapt.schedule import plan

    write_shard(iter([[1, 2]] * 1000), tmp_path / "t.bin", seq_len=2, vocab_size=100, meta={})
    schedule = plan(tmp_path / "t.bin", batch_size=8, grad_accum=1, epochs=8.0, max_steps=50)
    assert schedule.max_steps == 50


def test_degenerate_batch_rejected() -> None:
    from oikonomia.dapt.schedule import steps_for_epochs

    with pytest.raises(ValueError, match="must both be positive"):
        steps_for_epochs(100, 0, 0, 1.0)


def test_blocks_are_framed_like_roberta_pretraining() -> None:
    """RoBERTa never saw a sequence that did not open with <s> and close </s>.

    v1 of the packer emitted raw streams. Position 0 then holds arbitrary
    content at exactly the position the model is most confident about, and
    nothing in the loss reports it — the run just adapts less well.
    """
    blocks = list(pack_blocks([[9] * 20], seq_len=6, bos_id=0, eos_id=2))
    assert blocks, "expected at least one block"
    for b in blocks:
        assert len(b) == 6
        assert b[0] == 0 and b[-1] == 2
        assert all(t == 9 for t in b[1:-1])  # 4 content tokens per block


def test_framing_is_optional_and_off_by_default() -> None:
    assert list(pack_blocks([[1, 2, 3, 4]], seq_len=2)) == [[1, 2], [3, 4]]


def test_framing_reserves_two_slots() -> None:
    """Content per block drops by exactly 2 when framing is on."""
    unframed = list(pack_blocks([[7] * 100], seq_len=10))
    framed = list(pack_blocks([[7] * 100], seq_len=10, bos_id=0, eos_id=2))
    assert len(unframed) == 10  # 100 / 10
    assert len(framed) == 12  # 100 / 8


def test_seq_len_too_small_for_framing_is_rejected() -> None:
    with pytest.raises(ValueError, match="too small to hold framing"):
        list(pack_blocks([[1, 2, 3]], seq_len=2, bos_id=0, eos_id=2))
