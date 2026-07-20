# OIKONOMIA

**Information extraction from ancient Greek documentary papyri.**

OIKONOMIA turns the ~68,000 documentary papyri of Greco-Roman Egypt — tax
receipts, leases, loans, wage payments, census returns, private letters — into a
structured, auditable database of everyday economic life, and trains open Greek
models to read them. It is the first attempt to automate the information
extraction that economic historians currently do by hand, one document at a
time.

The corpus is the [Duke Databank of Documentary Papyri](https://papyri.info)
(DDbDP) with [HGV](https://aquila.zaw.uni-heidelberg.de/) metadata, distributed
via [`papyri/idp.data`](https://github.com/papyri/idp.data) under
**CC BY 3.0**.

## Status

Phase 1 (corpus ingestion) is implemented. See
[`CLAUDE.md`](CLAUDE.md) for the full phase plan, progress, and working
conventions, and [`docs/`](docs/) for architecture and design decisions.

## Quickstart

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"

# Pin a corpus revision, then sync + build the processed table.
uv run oik ingest sync  --set ingest.idp_git_rev=<commit-sha>
uv run oik ingest build
uv run oik ingest report        # coverage + parse-failure report
```

## Layout

```
src/oikonomia/     pure-Python library (no Modal, no GPU deps) — testable on a laptop
modal_app/         thin Modal orchestration (Phase 4+); imports the library, never vice versa
configs/           layered YAML configuration (local | modal)
resources/         curated knowledge (lexicons, genre map, prompts) — reviewed as code
data/              tiered by mutability; only data/gold and data/.manifests are tracked
tests/             progressive tests, incl. hand-crafted + real EpiDoc fixtures
docs/              architecture, data model, ADRs
```

## Licensing

- **Code**: MIT (this repository).
- **Corpus / derived data**: CC BY 3.0 — see [`DATA_ATTRIBUTION.md`](DATA_ATTRIBUTION.md).
- **Models**: released artifacts and their licence lineage are tracked in
  [`MODEL_LICENSES.md`](MODEL_LICENSES.md).
