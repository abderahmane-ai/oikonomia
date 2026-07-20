# Model licence lineage

Model artifacts inherit the licences of everything they are derived from. This
file is the audit trail for that lineage. It is enforced in code from Phase 4:
`oikonomia.models.backbone` asserts a candidate backbone's ancestry against an
allowlist, and the Hub-push step refuses to publish any artifact whose lineage
includes a NonCommercial ancestor.

## Backbone lineage (verified)

All of the author's prior Koine models are **PEFT LoRA adapters over the same
backbone**, `bowphs/GreTa` (T5, apache-2.0). `koineformer` is *not* an
encoder-only model — its `adapter_config.json` declares `task_type:
SEQ_2_SEQ_LM`.

| Artifact                | Init / ancestor            | Licence            | Releasable |
|-------------------------|----------------------------|--------------------|------------|
| `bowphs/GreTa`          | —                          | **apache-2.0**     | yes        |
| `koineformer`           | GreTa LoRA (span corrupt.) | **CC-BY-SA-4.0**   | yes (SA)   |
| `koine-t5`              | GreTa LoRA (multitask)     | CC-BY-NC-SA-4.0    | **NO (NC)**|
| `koine-t5-omni`         | GreTa LoRA (multitask)     | CC-BY-NC-SA-4.0    | **NO (NC)**|

## Planned OIKONOMIA arms (Phase 4 ablation)

| Arm | Initialisation                          | Licence         | Releasable |
|-----|-----------------------------------------|-----------------|------------|
| A0  | `bowphs/GreTa` (raw)                    | apache-2.0      | yes        |
| A1  | GreTa + papyri DAPT (**primary**)       | apache-2.0      | yes        |
| A2  | `koineformer` merged + papyri DAPT      | CC-BY-SA-4.0    | yes (SA)   |
| A3  | `koine-t5-omni` merged                  | CC-BY-NC-SA-4.0 | **NO** — comparison metric only |

**Rule:** A3 exists solely to produce numbers in the ablation table. No A3
descendant is ever pushed to the Hub.
