"""Normalize a monetary amount into a single comparable number — per system.

A price series is meaningless until amounts share a unit: "2 talents", "100
drachmas" and "3 obols" must become one scale. The conversions inside the
classical silver ladder are fixed and uncontested:

    1 talent = 6000 drachmas ;  1 drachma = 6 obols ;  1 obol = 8 chalkoi

so everything reduces to **drachmas**. The compound-obol coin names (diobol =
2 obols, …) reduce the same way.

**The one rule you must never break:** the Ptolemaic–Roman *silver* system
(drachma/obol/talent) and the Byzantine *gold* system (nomisma/solidus =
24 keratia) are different metals six centuries apart and are **not convertible**.
Summing a drachma with a nomisma is a category error that would silently corrupt
any series. So every amount is normalized *within its system* and tagged with
that system; aggregation must group by :attr:`Money.system` and never cross it.

Identity is taken from the lexicon's canonical currency id (``entry_id`` on a
CURRENCY entity: ``drachma``, ``talent``, ``nomisma``, …), so this module is a
fixed table keyed on that id, not a surface-form guesser.
"""

from __future__ import annotations

from dataclasses import dataclass

SILVER = "silver"  # Ptolemaic–Roman drachma system; base unit = drachma
GOLD = "gold"  # Byzantine gold system; base unit = nomisma (solidus)
UNKNOWN = "unknown"  # a money word with no fixed denomination (argyrion, chrysion)

# canonical currency id (lexicon entry_id) -> (system, value in base units of that
# system). Silver base = 1 drachma; gold base = 1 nomisma. `None` factor means the
# word names money but not a countable denomination, so a numeral cannot be scaled.
_DENOMINATIONS: dict[str, tuple[str, float | None]] = {
    # --- silver ladder (base: drachma) ---
    "talent": (SILVER, 6000.0),
    "drachma": (SILVER, 1.0),
    "obol": (SILVER, 1.0 / 6),
    "diobol": (SILVER, 2.0 / 6),
    "triobol": (SILVER, 3.0 / 6),
    "tetrobol": (SILVER, 4.0 / 6),
    "pentobol": (SILVER, 5.0 / 6),
    "hemiobelion": (SILVER, 0.5 / 6),
    "chalkous": (SILVER, 1.0 / 48),  # 1/8 obol (conventional); Ptolemaic bronze varies
    "argyrion": (SILVER, None),  # "silver money" — generic, no fixed denomination
    # --- gold system (base: nomisma / solidus) ---
    "nomisma": (GOLD, 1.0),
    "keration": (GOLD, 1.0 / 24),  # 24 keratia = 1 nomisma
    "chrysion": (GOLD, None),  # "gold money" — generic
}


@dataclass(frozen=True)
class Money:
    """A normalized amount. ``value_base`` is in drachmas (silver) or nomismata
    (gold); ``None`` when the amount or denomination could not be resolved.

    Never compare or sum ``value_base`` across differing :attr:`system`.
    """

    system: str
    currency_id: str | None
    value_base: float | None


def is_currency_id(currency_id: str | None) -> bool:
    """Whether a canonical id is a known monetary denomination."""
    return currency_id in _DENOMINATIONS


def normalize_amount(value_num: float | None, currency_id: str | None) -> Money:
    """Reduce ``value_num`` of ``currency_id`` to its system's base unit.

    ``value_num`` is the EpiDoc-decoded ``<num>`` value inside the amount span;
    ``currency_id`` the canonical id of the linked CURRENCY entity. An unknown or
    missing currency yields ``system=UNKNOWN`` and ``value_base=None`` — recorded,
    not guessed, so a downstream filter can exclude un-normalizable amounts rather
    than silently mis-scale them.
    """
    denom = _DENOMINATIONS.get(currency_id or "")
    if denom is None:
        return Money(system=UNKNOWN, currency_id=currency_id, value_base=None)
    system, factor = denom
    if factor is None or value_num is None:
        return Money(system=system, currency_id=currency_id, value_base=None)
    return Money(system=system, currency_id=currency_id, value_base=value_num * factor)
