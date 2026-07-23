"""The database-assembly layer (Phase 9): extractions → a queryable economic DB.

Where the labeling/model layers *read* the papyri, this layer *normalizes and
assembles* what they found into auditable, authority-linked economic facts — the
project's deliverable #2. It is deterministic and GPU-free: it turns a labeled
document (entities + relations) plus the corpus's own metadata (HGV dates,
Pleiades places, decoded ``<num>`` values) into fact records, each carrying the
``(tm_id, char-span)`` provenance that makes every row traceable to its source.

No learned model lives here. The monetary/measure/date normalization and the
commodity/currency identity come from the lexicon's canonical ids and the
EpiDoc-decoded numerals — all deterministic, all checkable by a papyrologist.
"""
