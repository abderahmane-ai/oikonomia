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


# --- what makes a card usable rather than merely present ---

ALL_CARDS = {**CARDS, "db": DB_CARD}

#: Tables the dataset ships, keyed to the heading the card documents them under.
DB_TABLES = (
    "documents", "monetary", "prices", "taxes",
    "persons", "principals", "persons_distinct", "autonomy",
)


@pytest.mark.parametrize("name", sorted(ALL_CARDS))
def test_frontmatter_names_no_hub_repo_that_does_not_exist(name: str) -> None:
    """`datasets:` renders as a clickable "trained on" link on the model page.

    The corpus (DDbDP) is EpiDoc XML in a git repo, not a Hub dataset, so naming
    it there produced a dead link on both model pages. Cite it in prose instead.
    """
    fm = _frontmatter(ALL_CARDS[name])
    assert "papyri/DDbDP" not in str(fm.get("datasets", "")), (
        f"{ALL_CARDS[name].name} frontmatter links a Hub dataset that does not exist"
    )


@pytest.mark.parametrize("name", sorted(CARDS))
def test_model_cards_publish_their_training_hyperparameters(name: str) -> None:
    """A card without hyperparameters cannot be reproduced from, which is most of
    what a model card is for. Both models train in two stages (silver → gold), so
    both learning rates have to be on the card, not just one."""
    text = CARDS[name].read_text(encoding="utf-8")
    assert "Training Hyperparameters" in text
    assert "Learning rate" in text and "Seed" in text
    assert "3e-5" in text  # the gold-stage LR, shared by both models


@pytest.mark.parametrize("name", sorted(ALL_CARDS))
def test_every_card_links_the_other_two_artifacts(name: str) -> None:
    """The three artifacts are one deliverable: entities → relations → database.
    A reader landing on any of them must be able to reach the other two."""
    text = ALL_CARDS[name].read_text(encoding="utf-8")
    others = {
        "grammateus": "ainouche-abderahmane/grammateus",
        "homologia": "ainouche-abderahmane/homologia",
        "db": "ainouche-abderahmane/oikonomia-db",
    }
    for other, repo in others.items():
        if other == name:
            continue
        assert repo in text, f"{ALL_CARDS[name].name} does not link {repo}"


def test_entity_card_discloses_the_unrecorded_per_label_scores() -> None:
    """Three of the 15 labels have no logged per-label F1. Printing the other 12
    without saying so reads as hiding the weakest classes — and two of the three
    are exactly the ones the card calls consistency-bound. Name the gap."""
    text = CARDS["grammateus"].read_text(encoding="utf-8")
    assert "not recorded" in text
    for label in ("COMMODITY", "PERSON_ROLE", "TAX_TERM"):
        assert label in text


def test_relation_card_leads_with_end_to_end_not_oracle() -> None:
    """Oracle scores (gold entity spans) flatter every RE model. The card must
    carry the end-to-end numbers a user will actually get, and must not quote the
    train-on-test 0.993 as if it were a generalization estimate."""
    text = CARDS["homologia"].read_text(encoding="utf-8")
    assert "0.623" in text and "end-to-end" in text.lower()
    assert "train-on-test" in text, "the 0.993 figure must be labelled as such"


def test_relation_card_flags_the_two_unsupervised_relations() -> None:
    """`HAS_AGE` / `HAS_OCCUPATION` are in the label space with zero gold edges,
    so they are trained on silver only and scored nowhere. A user reading the
    relation table would otherwise assume all 11 are equally supported."""
    text = CARDS["homologia"].read_text(encoding="utf-8")
    assert "HAS_AGE" in text and "HAS_OCCUPATION" in text
    assert "no gold supervision" in text


@pytest.mark.parametrize("table", DB_TABLES)
def test_dataset_card_documents_every_shipped_table(table: str) -> None:
    """Row counts and a grain are not documentation. Someone who downloads
    `monetary.parquet` needs to know what `value_base` and `system` mean, so each
    table gets its own column reference section."""
    text = DB_CARD.read_text(encoding="utf-8")
    assert f"#### `{table}`" in text, f"the dataset card has no column reference for {table}"


def test_dataset_card_carries_the_vocabularies_and_the_pitfalls() -> None:
    """Two things make the difference between a queryable database and a pile of
    parquet: knowing the allowed values of a categorical, and knowing which joins
    and aggregations are silently wrong."""
    text = DB_CARD.read_text(encoding="utf-8")
    assert "Controlled vocabularies" in text
    for vocab in ("gender_basis", "guardian", "roles", "deal_type", "currency_id"):
        assert f"**`{vocab}`**" in text, f"vocabulary {vocab} is not documented"
    assert "Pitfalls" in text
    # The two that silently corrupt a result rather than erroring.
    assert "never aggregate across systems" in text.lower()
    assert "`tm_id` is not unique" in text


@pytest.mark.corpus
def test_dataset_card_column_reference_matches_the_real_parquet_files() -> None:
    """The card claims a schema; the files are the schema. Drift between them is
    invisible until a user writes a query that returns nothing — which is how the
    `gender in ('F','M')` guess wastes an afternoon.

    Skipped when the (gitignored, re-derivable) tables are absent.
    """
    pq = pytest.importorskip("pyarrow.parquet")
    root = Path(__file__).resolve().parents[1] / "data" / "processed" / "db"
    paths = {t: root / f"{t}.parquet" for t in DB_TABLES}
    paths["documents"] = root / "export" / "documents.parquet"
    paths["persons_distinct"] = root / "export" / "persons_distinct.parquet"
    if not all(p.is_file() for p in paths.values()):
        pytest.skip("built database absent; run `oik db build` … `oik db export`")

    text = DB_CARD.read_text(encoding="utf-8")
    for table, path in paths.items():
        for column in pq.read_schema(path).names:
            assert f"`{column}`" in text, f"{table}.{column} is undocumented in the dataset card"
