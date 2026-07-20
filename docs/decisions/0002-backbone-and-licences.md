# ADR 0002 — Backbone selection and the licence firewall

**Status:** accepted (planning); enforced from Phase 4

## Context

The author's three prior Koine models are all **PEFT LoRA adapters over the same
backbone**, `bowphs/GreTa` (T5, apache-2.0) — verified from their
`adapter_config.json` files. `koineformer` is therefore *not* an encoder-only
model (`task_type: SEQ_2_SEQ_LM`). Two of the three (`koine-t5`,
`koine-t5-omni`) are **CC-BY-NC-SA-4.0** — NonCommercial, inherited from PROIEL.
The project's goal is to release *open* models and an *open* database.

## Decision

1. Extraction models use `T5EncoderModel` (GreTa's encoder) + a
   token-classification / span-pair head. This sidesteps GreTa's case-folding
   tokenizer (which cannot emit capitals) and is the right inductive bias for
   span extraction.
2. Publish a **four-arm ablation**: A0 GreTa-raw · A1 GreTa + new papyri DAPT
   (**primary release, apache-2.0**) · A2 koineformer + papyri DAPT (CC-BY-SA) ·
   A3 koine-t5-omni (**CC-BY-NC-SA — comparison metric only, never released**).
3. **Licence firewall:** `models/backbone.py` asserts a candidate's ancestry
   against an allowlist; any artifact with a NonCommercial ancestor is tagged
   `release_blocked` and the Hub-push step refuses it. This is a runtime
   assertion, not a convention.

## Consequences

- The primary released model has a clean apache-2.0 lineage.
- The scientific question "does literary/biblical Koine adaptation transfer to
  documentary Greek?" is answered by the ablation; a null result is still
  publishable.
- A3's value is one row in a table; nothing derived from it ships.

See `MODEL_LICENSES.md` for the full lineage table.
