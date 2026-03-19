# Data Preparation

Dataset acquisition, synthetic degradation, and test fixture plan for the DeepScribe SOAP Note Evaluation Suite. Referenced by CLAUDE.md. Execute during Step 0 before implementing any tier.

## Datasets

Download 2–3 representative samples from each source into /data/samples/ using the HuggingFace `datasets` library (pip install datasets). Write a download script at data/samples/download.py.

- **adesouza1/soap_notes** (HuggingFace) — listed in assessment requirements
- **ACI-Bench** (HuggingFace) — 87 complete doctor-patient dialogues with paired clinical notes. Higher fidelity.
- **Omi Health** (HuggingFace) — 10K synthetic dialogues via GPT-4 / NotChat framework. Useful for volume testing, not ground truth.

Save as JSON with original field names preserved.

## Config Prerequisite

Create src/config.py using pydantic-settings (BaseSettings class that auto-reads .env) with config-driven model switching. Model names use `openrouter/` prefix. generate_degraded.py uses LLM calls and requires OPENROUTER_API_KEY in .env.

## Synthetic Degradation

Create data/samples/generate_degraded.py — hybrid approach that takes good SOAP notes and produces synthetically degraded variants with labeled failure types.

### Programmatic (no LLM)
- **missing_section:** drop Assessment or Plan entirely
- **omitted_findings:** remove sentences containing key entities from dialogue
- **redundancy_bloat:** duplicate sentences, pad with filler
- **structural_errors:** swap section ordering (e.g., Plan before Assessment)

### LLM-assisted (uses config.py → LiteLLM)
- **hallucinated_entities:** inject contextually plausible medications/diagnoses not in transcript
- **internal_contradiction:** generate natural-sounding contradictions between Subjective and Assessment

Output to data/samples/degraded/ with manifest.json mapping each file to its ground-truth failure labels.

## Manifest

Create data/samples/manifest.json cataloging all samples (good + degraded) with source dataset, filename, and label metadata.

## Test Fixture Expectations

These become pytest cases:
- Known-good notes pass all Tier 1 checks and all Tier 2 criteria
- Each degradation type triggers its expected failure
- Entity extraction matches expected entity lists
- Edge cases: empty sections, malformed SOAP, missing transcript