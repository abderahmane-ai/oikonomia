"""Enforce the boundaries CLAUDE.md §3 declares, rather than trusting them.

These are the invariants that keep the library usable on a laptop with no GPU
and no Modal account. They are easy to break by accident with a single import
and hard to notice until someone tries a clean install.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "oikonomia"
MODAL_APP = Path(__file__).resolve().parents[1] / "modal_app"

# Installed only in the Modal training image. The library may reference them
# inside a function body (lazy import), never at module import time.
HEAVY = {"torch", "transformers", "peft", "accelerate", "datasets", "modal"}


def _module_level_imports(path: Path) -> set[str]:
    """Top-level import names only — imports inside functions are allowed."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:  # module level only, deliberately not ast.walk
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_library_has_no_heavy_module_level_imports(path: Path) -> None:
    """`import oikonomia` must work with no ML stack installed."""
    offenders = _module_level_imports(path) & HEAVY
    assert not offenders, f"{path.name} imports {offenders} at module level; import it lazily"


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_library_never_imports_modal_app(path: Path) -> None:
    """Orchestration depends on the library, never the reverse.

    Deleting modal_app/ must not break the library.
    """
    assert "modal_app" not in _module_level_imports(path)


def test_modal_app_may_import_the_library() -> None:
    """The dependency is allowed to run in this direction."""
    assert MODAL_APP.is_dir()
    sources = list(MODAL_APP.rglob("*.py"))
    assert sources, "modal_app/ has no modules"
    assert any("oikonomia" in p.read_text(encoding="utf-8") for p in sources)


def test_published_architectures_are_defined_in_the_library() -> None:
    """A released model must stay loadable if modal_app/ is deleted.

    Homologia ships as a state_dict, so whichever module defines its layers *is*
    the model. That definition belongs in the library; modal_app may only call it.
    """
    from oikonomia.relations.model import build_relation_head

    assert build_relation_head.__module__ == "oikonomia.relations.model"
    body = (MODAL_APP / "relations.py").read_text(encoding="utf-8")
    assert "nn.Module" not in body, "modal_app/relations.py defines layers; move them into the library"


def test_library_imports_without_ml_stack() -> None:
    """The end-to-end version of the rule: importing every module must not
    require torch/peft/modal, none of which are installed here."""
    import importlib

    for path in sorted(SRC.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        module = "oikonomia." + str(path.relative_to(SRC).with_suffix("")).replace("/", ".")
        importlib.import_module(module)
