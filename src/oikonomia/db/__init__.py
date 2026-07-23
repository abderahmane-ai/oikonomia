"""The database-assembly layer (Phase 9): extractions → a queryable economic DB.

Where the labeling/model layers *read* the papyri, this layer *normalizes and
assembles* what they found into auditable, authority-linked economic facts
(deliverable #2). Deterministic and GPU-free: a labeled document plus the corpus's
own metadata (HGV dates, Pleiades places, decoded ``<num>`` values) becomes fact
records, each with ``(tm_id, char-span)`` provenance. No learned model lives here —
identity and normalization come from the lexicon's canonical ids and the
EpiDoc-decoded numerals, all checkable by a papyrologist.
"""
