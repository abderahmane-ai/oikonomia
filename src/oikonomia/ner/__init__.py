"""Downstream entity NER (Phase 7): span↔BIO encoding and data loading.

Pure, GPU-free, unit-testable. The training loop that consumes these lives in
``modal_app/ner.py``; the scoring lives in ``oikonomia.labeling.score``.
"""
