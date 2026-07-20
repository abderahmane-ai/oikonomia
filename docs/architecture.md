# Architecture

## Boundaries

Four boundaries are enforced by directory layout and import direction. Violating
them is a design bug, not a style preference.

| Layer | Path | May import | Must not |
|-------|------|-----------|----------|
| Library | `src/oikonomia/` | stdlib, lxml, pydantic, pyyaml, pandas/pyarrow | import `modal`, torch, transformers at module load |
| Modal | `modal_app/` | `oikonomia`, `modal` | be imported by the library |
| Data | `data/` | — | `raw/` never written by a stage |
| Resources | `resources/` | — | contain generated-only artifacts |

The library is importable and testable on a laptop with no GPU. Heavy stacks
live behind optional extras (`.[train]`, `.[modal]`) and are imported locally
inside the functions that use them.

## Data flow (Phase 1)

```
github.com/papyri/idp.data @ pinned rev
        │  ingest/sync.py  (git checkout, read-only)
        ▼
data/raw/idp.data/            IMMUTABLE, gitignored
   ├─ DDbDP/*.xml    ─► ingest/epidoc_text.py ─► Document (edited + diplomatic
   │                                              views, OffsetMap, markup,
   │                                              numerals, lines)
   ├─ HGV_meta/*.xml ─► ingest/hgv_* ──────────► HgvMetadata (dates, places, genre)
   └─ Translations/  ─► ingest/translations.py ► doc-level EN text
        │
        │  join by TM id (ingest/paths.py)   ← the ONLY join logic
        ▼
data/processed/corpus.parquet   (+ ingest_failures.json)
```

Every processed artifact carries the corpus git rev (as the stage's
`inputs_key`) so any downstream number is traceable to an exact corpus state.

## The pipeline runner

`pipeline/stage.py` defines a `Stage` protocol and `run_stage`. A stage declares
a cheap `inputs_key` (the pinned corpus rev, never a 68k-file scan), its
`params`, and its `outputs`. `run_stage` computes a freshness key
(`version + inputs_key + params`) and skips the stage when a matching manifest
with intact output hashes already exists.

Guarantees:
- **Atomic outputs** — write temp, rename; manifest written last, so a crash
  never marks a stage falsely fresh.
- **Deterministic** — same version + corpus rev + params ⇒ same freshness key.
- **Resumable** — re-running the pipeline recomputes only what changed.
- **Explicit** — bump a stage's `version` when its logic changes (or use
  `--force`). No hidden source-hashing; you can see exactly why a stage re-ran.

## The load-bearing module: `ingest/epidoc_text.py`

EpiDoc editions are rendered into two aligned character strings:

- **edited** — the scholarly reading (expansions and restorations included,
  spelling regularised).
- **diplomatic** — what is physically on the papyrus.

Both are produced in a single recursive walk that emits each text chunk into the
edited view, the diplomatic view, or both. "Both" chunks become the aligned
segments of the `OffsetMap`, giving a bidirectional edited↔diplomatic mapping.
Markup phenomena (gap, unclear, supplied, expansion, regularisation) and
numerals are located as spans into the relevant view(s).

**Why two views:** currency and measure terms are overwhelmingly abbreviated
(`<expan>` in 65% of docs, `<choice>` in 47%). Annotating against one view and
needing the other later would strand the annotations irrecoverably. See
`docs/decisions/0001-dual-text-views.md`.

The core correctness property, asserted in tests: for every aligned segment,
`edited[e0:e1] == diplomatic[d0:d1]`. If the offset map is wrong, this fails.

## Configuration

Layered YAML → typed `Settings`:

1. `configs/base.yaml`
2. `configs/paths.<env>.yaml` (`local` | `modal`)
3. dotted `--set key=value` overrides
4. `OIK_*` environment variables (highest precedence)

No module constructs a data-path literal; all paths come from `settings.paths.*`.
The same code runs locally (`paths.local.yaml`) and inside a Modal container
(`paths.modal.yaml`, rooted at the `/vol/data` Volume mount).
