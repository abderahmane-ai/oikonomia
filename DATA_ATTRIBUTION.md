# Data attribution

OIKONOMIA is built on data from the **Duke Databank of Documentary Papyri
(DDbDP)** and the **Heidelberger Gesamtverzeichnis der griechischen
Papyrusurkunden Ägyptens (HGV)**, distributed via the
[`papyri/idp.data`](https://github.com/papyri/idp.data) repository.

## Licence

All idp.data text and metadata are licensed under the
[Creative Commons Attribution 3.0 License](https://creativecommons.org/licenses/by/3.0/)
(as stated inside each source file; the repository carries no separate `LICENSE`
file). Any redistributed derivative of this data — including the processed
corpus table, the extracted database, and dataset releases — must carry this
attribution and licence.

## Required attribution

> Text and metadata © Duke Databank of Documentary Papyri and the Heidelberger
> Gesamtverzeichnis, made available via papyri.info under a Creative Commons
> Attribution 3.0 License.

## What is and is not redistributed

- **Redistributed** (as derivatives, with attribution): the processed
  `corpus.parquet`, extracted transaction records, gold annotations, and dataset
  releases derived from the CC BY 3.0 text.
- **Not redistributed in bulk**: the raw `idp.data` checkout is re-derivable
  from a pinned git revision and is not committed here (see `.gitignore`).

## Corpus reproducibility

Every processed artifact records the exact idp.data git revision it was built
from (`ingest.idp_git_rev`) in its stage manifest under `data/.manifests/`, so a
result can always be traced to a specific corpus state.
