"""Coreference-lite: collapse person MENTIONS into distinct PEOPLE.

The person and principal tables hold one row per *mention* — a heavily-attested
individual is counted many times. For an honest "how many distinct women were
principals?" (the question a reviewer asks first) the mentions must be folded to
people. This is **not** full prosopographical coreference — that needs
disambiguation across the whole corpus and is a research problem of its own. It is
a deliberately conservative surface key:

    (normalized own-name, normalized patronymic, place)

so it merges case/whitespace variants of the *same* (name, father, nome) while
keeping two homonyms in different nomes apart. It under-merges (a person named
without their father, or in two nomes, splits) far more than it over-merges, so
the distinct count it yields is an **upper bound** on the true number of people —
the safe direction for a "not fewer than" claim. Deterministic and pure.
"""

from __future__ import annotations

import hashlib
import unicodedata

import pandas as pd


def _norm(s: object) -> str:
    """Fold a name field to a match key ("" for missing).

    Normalizes Unicode form (NFC) so a name typed composed vs decomposed matches,
    casefolds (which also folds Greek final sigma ς→σ, a positional variant of one
    letter), collapses whitespace, and re-normalizes to keep the key in one form.
    """
    if not isinstance(s, str):
        return ""
    folded = unicodedata.normalize("NFC", s).casefold()
    return unicodedata.normalize("NFC", " ".join(folded.split()))


def _place(place: object) -> str:
    """A Pleiades id to a stable string key ("" for missing/NaN)."""
    if place is None:
        return ""
    try:
        f = float(place)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(place)
    return "" if f != f else str(int(f))  # NaN → ""


def person_key(head: object, father: object, place: object) -> tuple[str, str, str]:
    """The conservative identity key for one mention: (name, father, place).

    Two mentions with the same normalized own-name *and* patronymic *and* place
    are treated as one person. A mention missing the father or the place keys on
    "" there, so it only merges with other equally-underspecified mentions — it
    never absorbs a fully-specified homonym.
    """
    return (_norm(head), _norm(father), _place(place))


def person_id(head: object, father: object, place: object) -> str:
    """A stable, portable id for the person :func:`person_key` identifies.

    The tuple key is the identity; this is that key hashed to 16 hex chars so it
    survives a parquet round-trip and can be joined on from any tool. It is a pure
    function of the normalized key, so the same person gets the same id on every
    rebuild and across the shipped tables.
    """
    raw = "\x1f".join(person_key(head, father, place))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# Which mention wins when picking a person's representative gender: a positively
# attributed sex beats "unknown"; among attributed mentions the majority wins.
def _mode_gender(genders: pd.Series) -> str:
    known = genders[genders.isin(["male", "female"])]
    if known.empty:
        return "unknown"
    return str(known.mode().iloc[0])


def _fold_guardian(guardians: pd.Series) -> str:
    """A person's guardian status: 'without' if ever attested autonomous, else
    'with' if ever guarded, else 'none'. 'without' wins because a single
    unambiguous χωρὶς-κυρίου attestation establishes the person acted alone."""
    vals = set(guardians.dropna())
    if "without" in vals:
        return "without"
    if "with" in vals:
        return "with"
    return "none"


def collapse_to_persons(df: pd.DataFrame) -> pd.DataFrame:
    """Fold a mention table into one row per distinct person.

    ``df`` must carry ``head_text, father_text, place_pleiades, gender,
    guardian`` (the person/principal schema) and may carry ``deal_type`` and
    ``century``. Returns one row per :func:`person_key` with a representative
    name/father/place, the folded gender + guardian, the mention count, and — when
    present — the set of deal types and the earliest century. Sorted by mention
    count descending (the best-attested people first).
    """
    if df.empty:
        return pd.DataFrame(
            columns=["person_id", "head_text", "father_text", "place_pleiades", "gender",
                     "guardian", "n_mentions", "deal_types", "first_century"]
        )
    keyed = df.copy()
    keyed["_k"] = [
        person_key(h, f, p)
        for h, f, p in zip(keyed["head_text"], keyed["father_text"], keyed["place_pleiades"], strict=True)
    ]
    has_deal = "deal_type" in keyed.columns
    has_cen = "century" in keyed.columns

    rows: list[dict[str, object]] = []
    for _key, sub in keyed.groupby("_k", sort=False):
        first = sub.iloc[0]
        rows.append({
            "person_id": person_id(first["head_text"], first["father_text"], first["place_pleiades"]),
            "head_text": first["head_text"],
            "father_text": first["father_text"],
            "place_pleiades": first["place_pleiades"],
            "gender": _mode_gender(sub["gender"]),
            "guardian": _fold_guardian(sub["guardian"]),
            "n_mentions": len(sub),
            "deal_types": "|".join(sorted({str(x) for x in sub["deal_type"] if isinstance(x, str) and x and x != "?"})) if has_deal else "",
            "first_century": (int(sub["century"].dropna().min()) if has_cen and sub["century"].notna().any() else None),
        })
    out = pd.DataFrame(rows)
    return out.sort_values("n_mentions", ascending=False).reset_index(drop=True)
