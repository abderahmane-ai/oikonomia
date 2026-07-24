"""The two shipped model cards must be publishable as-is.

A model card is the *public face* of deliverable #1 and it is uploaded verbatim by
the Hub push, so a defect in it ships. These guard the failure modes that would
actually embarrass a release: an unfilled `<your-org>` placeholder in the usage
snippet, a licence in the frontmatter that the firewall would refuse, a base model
that is not the one we trained on, or a card that silently loses its frontmatter
(HF then renders it as plain text and indexes nothing).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from oikonomia.models.licensing import KNOWN_LICENCES, is_noncommercial

RELEASE = Path(__file__).resolve().parents[1] / "resources" / "release"
CARDS = {"grammateus": RELEASE / "GRAMMATEUS_CARD.md", "homologia": RELEASE / "HOMOLOGIA_CARD.md"}


def _frontmatter(path: Path) -> dict[str, object]:
    """The card's YAML frontmatter (the block between the leading `---` fences)."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} has no frontmatter fence"
    _, block, _ = text.split("---\n", 2)
    loaded = yaml.safe_load(block)
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.parametrize("name", sorted(CARDS))
def test_card_exists_and_has_frontmatter(name: str) -> None:
    fm = _frontmatter(CARDS[name])
    assert fm["language"] == ["grc"]  # Ancient Greek — what makes it findable on the Hub
    assert fm["base_model"] == "bowphs/GreBerta"


@pytest.mark.parametrize("name", sorted(CARDS))
def test_declared_licence_passes_the_firewall(name: str) -> None:
    # The card must not advertise a licence the firewall would refuse to publish
    # under, and it must match the backbone we actually inherit from.
    licence = str(_frontmatter(CARDS[name])["license"])
    assert not is_noncommercial(licence)
    assert licence == KNOWN_LICENCES["bowphs/GreBerta"]


@pytest.mark.parametrize("name", sorted(CARDS))
def test_no_unfilled_placeholders(name: str) -> None:
    text = CARDS[name].read_text(encoding="utf-8")
    for placeholder in ("<your-org>", "<org>", "TODO", "XXX"):
        assert placeholder not in text, f"{CARDS[name].name} still carries {placeholder!r}"


def test_cards_cross_reference_each_other() -> None:
    # The pair is only useful together (entities → relations); each card must send
    # a reader to the sibling model.
    assert "ainouche-abderahmane/homologia" in CARDS["grammateus"].read_text(encoding="utf-8")
    assert "ainouche-abderahmane/grammateus" in CARDS["homologia"].read_text(encoding="utf-8")


def test_relation_card_warns_it_is_not_an_automodel() -> None:
    # The RE checkpoint is a custom head; a reader who calls `from_pretrained` on
    # it gets a confusing failure. The card must say so before the usage snippet.
    text = CARDS["homologia"].read_text(encoding="utf-8")
    assert "not a `transformers` `AutoModel`" in text
    assert "relation_head.pt" in text


# --- the dataset card (deliverable #2), which ships the same way ---

DB_CARD = RELEASE / "OIKONOMIA_DB_CARD.md"


def test_dataset_card_declares_the_corpus_licence() -> None:
    # The data is derived from DDbDP/HGV, so the card must carry that licence
    # forward rather than the code's.
    assert str(_frontmatter(DB_CARD)["license"]) == "cc-by-3.0"
    assert _frontmatter(DB_CARD)["language"] == ["grc"]


def test_dataset_card_configs_match_the_shipped_files() -> None:
    """The card's `configs:` block is what the Hub viewer and `load_dataset` read.

    A config naming a file the release does not ship gives a viewer error and a
    download that fails, so the two lists must not drift apart.
    """
    from oikonomia.models.release import MODELS

    configs = _frontmatter(DB_CARD)["configs"]
    assert isinstance(configs, list)
    declared = {str(c["data_files"]) for c in configs}  # type: ignore[index]
    shipped = set(MODELS["db"].required)
    assert declared == shipped, f"card declares {declared ^ shipped} that the release does not"


def test_dataset_card_does_not_oversell_the_price_table() -> None:
    """98 observations is a thin sample; the card must say so where a reader
    meets the number, not bury it."""
    text = DB_CARD.read_text(encoding="utf-8")
    assert "Limitations" in text
    assert "not as a price history" in text
    assert "98" in text  # the actual n, stated rather than rounded away
