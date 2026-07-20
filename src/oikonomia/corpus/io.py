"""Streaming reads over the processed corpus table.

Everything that scans the whole corpus does it the same way: in record batches,
reading only the columns it needs. ``document_json`` is most of the parquet's
bulk, so column projection is the difference between a few hundred MB of RAM
and a few tens.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

CORPUS_FILENAME = "corpus.parquet"


def corpus_path(processed_root: Path) -> Path:
    return processed_root / CORPUS_FILENAME


def iter_batches(
    parquet_path: Path,
    columns: Sequence[str],
    batch_size: int = 2000,
) -> Iterator[pd.DataFrame]:
    """Stream the corpus table as pandas frames of ``batch_size`` rows."""
    if not parquet_path.is_file():
        msg = f"corpus table not found at {parquet_path}. Run `oik ingest build` first."
        raise FileNotFoundError(msg)
    parquet = pq.ParquetFile(parquet_path)
    for batch in parquet.iter_batches(batch_size=batch_size, columns=list(columns)):
        yield batch.to_pandas()
