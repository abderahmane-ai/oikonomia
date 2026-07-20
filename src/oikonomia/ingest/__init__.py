"""Corpus ingestion: EpiDoc parsing, HGV metadata, and the join stage."""

from oikonomia.ingest.build_corpus import BuildCorpusStage, build_rows
from oikonomia.ingest.epidoc_text import parse_ddbdp
from oikonomia.ingest.hgv_meta import parse_hgv

__all__ = ["BuildCorpusStage", "build_rows", "parse_ddbdp", "parse_hgv"]
