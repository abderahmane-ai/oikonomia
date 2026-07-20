"""Load the curated lexicons in ``resources/lexicon/``.

The YAML files are reviewed as source code: model behaviour depends on them, and
every form in them was mined from the corpus (see
:mod:`oikonomia.labeling.mine`). This module only loads and indexes them.

Forms are stored **folded** — the shape produced by
:func:`oikonomia.labeling.normalize.normalize`. Matching therefore happens in
folded space, and results are reported back in original offsets by the matcher.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from oikonomia.labeling.normalize import normalize

LEXICON_DIRNAME = "lexicon"


class LexiconEntry(BaseModel):
    """One lexical item: a concept plus every attested surface form of it."""

    id: str
    category: str
    gloss: str = ""
    forms: list[str] = Field(default_factory=list)
    # Truncated abbreviations (e.g. "δραχμ"). Kept apart from full forms because
    # they are short enough to collide with unrelated words, so a caller may
    # want to weight or exclude them.
    abbrev_forms: list[str] = Field(default_factory=list)

    @property
    def all_forms(self) -> list[str]:
        return [*self.forms, *self.abbrev_forms]


class Lexicon(BaseModel):
    """All entries across all category files, indexed by folded form."""

    entries: list[LexiconEntry] = Field(default_factory=list)

    def index(self) -> dict[str, LexiconEntry]:
        """Map every folded form to its entry.

        A form claimed by two entries is an error rather than a silent
        first-wins: it means the curation has not decided what the word is, and
        resolving it in code would bury that decision.
        """
        idx: dict[str, LexiconEntry] = {}
        for entry in self.entries:
            for form in entry.all_forms:
                existing = idx.get(form)
                if existing is not None and existing.id != entry.id:
                    msg = (
                        f"form {form!r} is claimed by both {existing.category}/"
                        f"{existing.id} and {entry.category}/{entry.id}; "
                        "resolve it in resources/lexicon/"
                    )
                    raise ValueError(msg)
                idx[form] = entry
        return idx

    def by_category(self, category: str) -> list[LexiconEntry]:
        return [e for e in self.entries if e.category == category]


def _check_folded(form: str, where: str) -> None:
    """Reject a form that is not already in folded shape.

    An accented entry would simply never match — folded text contains no
    accents — and would do so silently. Failing at load time turns an invisible
    recall hole into an immediate error.
    """
    folded = normalize(form).text
    if folded != form:
        msg = f"{where}: form {form!r} is not folded (expected {folded!r})"
        raise ValueError(msg)


def load_lexicon_file(path: Path) -> list[LexiconEntry]:
    """Load one category YAML file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    category = raw.get("category")
    if not category:
        msg = f"{path}: missing top-level 'category'"
        raise ValueError(msg)

    entries: list[LexiconEntry] = []
    for item in raw.get("entries") or []:
        entry = LexiconEntry(
            id=item["id"],
            category=category,
            gloss=item.get("gloss", ""),
            forms=list(item.get("forms") or []),
            abbrev_forms=list(item.get("abbrev_forms") or []),
        )
        if not entry.all_forms:
            msg = f"{path}: entry {entry.id!r} has no forms"
            raise ValueError(msg)
        for form in entry.all_forms:
            _check_folded(form, f"{path}:{entry.id}")
        entries.append(entry)
    return entries


def load_lexicon(resources_root: Path) -> Lexicon:
    """Load every ``*.yaml`` under ``resources/lexicon/``."""
    lex_dir = resources_root / LEXICON_DIRNAME
    if not lex_dir.is_dir():
        msg = f"lexicon directory not found at {lex_dir}"
        raise FileNotFoundError(msg)

    entries: list[LexiconEntry] = []
    for path in sorted(lex_dir.glob("*.yaml")):
        entries.extend(load_lexicon_file(path))
    lexicon = Lexicon(entries=entries)
    lexicon.index()  # fail fast on cross-file form collisions
    return lexicon
