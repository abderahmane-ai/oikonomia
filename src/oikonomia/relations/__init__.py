"""Downstream relation extraction (Phase 8): typed candidate generation.

Pure, GPU-free, unit-testable. Candidate generation is *typed* — it uses the
single relation contract in :data:`oikonomia.gold.validate.RELATION_SIGNATURES`
to prune the O(n²) entity pairs to the handful whose ``(head-label, tail-label)``
is admissible for some relation type. The span-pair model that consumes these
candidates is :mod:`oikonomia.relations.model`; scoring reuses
``oikonomia.labeling.score.build_report``.
"""
