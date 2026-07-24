"""The licence firewall — the gate every Hub push must clear.

A model artifact inherits the licences of everything it derives from. OIKONOMIA's
one hard licence rule (CLAUDE.md §2): **never release an artifact whose lineage
includes a NonCommercial ancestor.** The author's own `koine-t5*` Koine models are
CC-BY-NC-SA; a model initialised from one could never be shipped.

This module makes that rule executable and, crucially, **fail-closed**: an ancestor
that is not on the vetted allowlist is refused, not waved through — so an unrecorded
or mis-remembered lineage blocks the push rather than leaking an NC-tainted model.
``assert_releasable`` is called by the Hub-push step before a single byte is
uploaded. Verified lineage facts live in ``MODEL_LICENSES.md`` (the audit trail).
"""

from __future__ import annotations

from collections.abc import Sequence

# Vetted licences of every model an OIKONOMIA artifact may descend from. Each entry
# is verified against the source's own model card (see MODEL_LICENSES.md), not
# recalled. Anything absent here is treated as unknown → refused (fail-closed).
KNOWN_LICENCES: dict[str, str] = {
    "bowphs/GreBerta": "apache-2.0",  # B1 backbone — verified apache-2.0 (Riemenschneider & Frank 2023)
    "bowphs/GreTa": "apache-2.0",  # T5 sibling; the superseded ablation arm
    "bowphs/koineformer": "cc-by-sa-4.0",  # GreTa LoRA — ShareAlike, releasable under SA
    "bowphs/koine-t5": "cc-by-nc-sa-4.0",  # NonCommercial — NEVER releasable
    "bowphs/koine-t5-omni": "cc-by-nc-sa-4.0",  # NonCommercial — NEVER releasable
    # Our own training data. The model weights are apache-2.0 (backbone-inherited);
    # DDbDP is attributed in the model card as required by CC BY 3.0, and DAPT/gold
    # carry no NC term. Listed so a lineage naming them still passes the allowlist.
    "DDbDP": "cc-by-3.0",
    "oikonomia-gold": "cc-by-3.0",
}

# Substrings that mark a licence as NonCommercial (the disqualifier). Kept as a
# check on the *licence string* too, so a new allowlist entry can never sneak an
# NC term past the firewall by being typo'd into the map.
_NONCOMMERCIAL_MARKERS = ("-nc-", "-nc", "noncommercial", "non-commercial")


class LicenceError(RuntimeError):
    """Raised when an artifact's lineage forbids a public release."""


def is_noncommercial(licence: str) -> bool:
    """True if a licence string carries a NonCommercial term."""
    lic = licence.lower()
    return any(marker in lic for marker in _NONCOMMERCIAL_MARKERS)


def assert_releasable(lineage: Sequence[str]) -> None:
    """Refuse to release unless every ancestor is vetted and commercially open.

    ``lineage`` is the ordered list of model/data ids the artifact derives from
    (backbone first). Raises :class:`LicenceError` if any ancestor is unknown
    (fail-closed) or NonCommercial. Returns ``None`` when the push may proceed.
    """
    if not lineage:
        raise LicenceError("empty lineage — cannot verify releasability (fail-closed)")
    for ancestor in lineage:
        licence = KNOWN_LICENCES.get(ancestor)
        if licence is None:
            raise LicenceError(
                f"ancestor {ancestor!r} is not on the vetted allowlist — refusing to "
                f"publish an artifact of unverified lineage (fail-closed). Add it to "
                f"KNOWN_LICENCES with a source-checked licence first."
            )
        if is_noncommercial(licence):
            raise LicenceError(
                f"ancestor {ancestor!r} is {licence} (NonCommercial) — releasing any "
                f"descendant is forbidden by the OIKONOMIA licence firewall."
            )
