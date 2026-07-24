# Model licence lineage

Model artifacts inherit the licences of everything they are derived from. This
file is the audit trail for that lineage. The one hard rule (CLAUDE.md §2): **never
release an artifact whose lineage includes a NonCommercial ancestor.**

**Enforced in code by `oikonomia.models.licensing`** (`assert_releasable`), which
the Hub-push step (`modal_app/ner.py::push_to_hub`) calls before uploading a single
byte. It is **fail-closed**: an ancestor absent from the vetted allowlist is refused,
not waved through — so an unrecorded or mis-remembered lineage blocks the release.

## The shipped backbone (verified against the source model card)

The OIKONOMIA models are built on **`bowphs/GreBerta`**, an encoder-only RoBERTa-base
Ancient Greek model — *not* the GreTa/T5 arms sketched in the superseded Phase-4
ablation below. Its licence was checked against its Hugging Face model card:

| Artifact | Init / ancestor | Licence | Releasable |
|---|---|---|---|
| **`bowphs/GreBerta`** (the backbone) | — | **apache-2.0** | **yes** |
| **OIKONOMIA-NER** (`GreBerta` + papyri DAPT + gold-FT) | GreBerta | **apache-2.0** | **yes** |
| **OIKONOMIA-RE** (`GreBerta` + papyri DAPT + span-pair) | GreBerta | apache-2.0 | yes (not yet trained/saved) |

Training data: the Duke Databank (DDbDP), **CC BY 3.0** — attributed in the model
card as CC BY 3.0 requires; the weights are apache-2.0 (backbone-inherited). No
ancestor carries a NonCommercial term, so both models clear the firewall.

## The author's Koine models (why the firewall exists)

All are **PEFT LoRA adapters over `bowphs/GreTa`** (T5, apache-2.0). They are *not*
used by the shipped models, but are recorded because two are NonCommercial — the
exact case the firewall must block. `koineformer` declares `task_type:
SEQ_2_SEQ_LM` (not encoder-only).

| Artifact | Init / ancestor | Licence | Releasable |
|---|---|---|---|
| `bowphs/GreTa` | — | **apache-2.0** | yes |
| `koineformer` | GreTa LoRA (span corrupt.) | **CC-BY-SA-4.0** | yes (SA) |
| `koine-t5` | GreTa LoRA (multitask) | CC-BY-NC-SA-4.0 | **NO (NC)** |
| `koine-t5-omni` | GreTa LoRA (multitask) | CC-BY-NC-SA-4.0 | **NO (NC)** |

## Superseded plan (Phase-4 ablation, GreTa-based — NOT shipped)

The original Phase-4 plan compared GreTa arms A0–A3. It was superseded: GreBerta
(case-preserving, encoder-only) won as the backbone, and DAPT is a full fine-tune on
GreBerta. Arm A3 (a `koine-t5-omni` descendant) existed **solely to produce numbers
in the ablation table — no A3 descendant is ever pushed to the Hub.**

| Arm | Initialisation | Licence | Releasable |
|-----|-----------------------------------------|-----------------|------------|
| A0 | `bowphs/GreTa` (raw) | apache-2.0 | yes |
| A1 | GreTa + papyri DAPT | apache-2.0 | yes |
| A2 | `koineformer` merged + papyri DAPT | CC-BY-SA-4.0 | yes (SA) |
| A3 | `koine-t5-omni` merged | CC-BY-NC-SA-4.0 | **NO** — comparison metric only |
