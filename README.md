# DeepScribe SOAP Note Evaluation Suite

An offline evaluation system for AI-generated SOAP notes from doctor-patient conversations. Uses a tiered architecture that balances cost, speed, and clinical validity — from fast deterministic checks to LLM-as-a-judge to human expert review.

---

## Why This Exists

DeepScribe's core product is AI-generated clinical notes. Demonstrating deep fluency in how to *evaluate* that output — not just generate it — directly addresses the highest-leverage problem the team faces. Most candidates build a generator. This builds the system that tells you whether the generator is any good.

The design is grounded in three strategic insights from the evaluation literature:

**Tiered architecture mirrors real production systems.** The Tier 1 → 2 → 3 escalation pattern (cheap/fast screening → expensive/thorough judgment → human-in-the-loop calibration) is how mature ML teams actually operate. It shows awareness of cost-quality tradeoffs at scale, not just "call GPT-4 on everything."

**Meta-evaluation is the differentiator.** Including a calibration module that measures judge-vs-human agreement (Cohen's kappa, targeted >90% binary agreement) demonstrates understanding of a problem most candidates don't even consider: *how do you know your evaluator is trustworthy?*

**Literature-grounded decisions build trust.** Binary pass/fail criteria come from the LLM-as-a-judge literature showing numeric scales produce rater drift. PDQI-9 comes from clinical quality research. Chain-of-thought-before-verdict comes from G-Eval (Liu et al., EMNLP 2023). This is not a vibe-coded prototype — it is a researched system.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Input: SOAP note + source transcript                                │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
          ┌─────────────────▼────────────────────────┐
          │    Tier 1 — Automated Screening           │
          │    (synchronous, ~50–200 ms per note)     │
          │                                           │
          │  • Entity extraction (spaCy + scispaCy)   │
          │  • Section completeness checks            │
          │  • Structural validation / ordering       │
          │  • Redundancy / note-bloat detection      │
          │                                           │
          │  Output: JSON with per-check pass/fail    │
          │           + extracted entity lists        │
          └─────────────────┬────────────────────────┘
                            │
          ┌─────────────────▼────────────────────────┐
          │    Tier 2 — LLM-as-a-Judge               │
          │    (async batch, ~3–8 s per note)         │
          │                                           │
          │  • 6 PDQI-9-adapted binary criteria       │
          │  • Chain-of-thought before verdict        │
          │  • Hallucination detection (NLI proxy)    │
          │  • Versioned prompt templates             │
          │                                           │
          │  Output: Structured JSON verdict          │
          │          + escalation flag for Tier 3     │
          └─────────────────┬────────────────────────┘
                            │
          ┌─────────────────▼────────────────────────┐
          │    Tier 3 — Human Expert Review (future)  │
          │    (three-column web UI — Cursor build)   │
          │                                           │
          │  • Side-by-side: transcript / note / judge│
          │  • CRUD on judge annotations              │
          │  • Expert reasoning capture               │
          │  • Diff export for prompt calibration     │
          └──────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Binary pass/fail (not Likert)** | Simpler judgments are more reliable and actionable. Numeric scales introduce rater drift and ambiguous midpoints (Husain, 2024). |
| **Reference-free as primary mode** | Production notes have no gold-standard reference. The system evaluates using only the source transcript + internal consistency. |
| **Chain-of-thought before verdict** | Forces the judge to articulate reasoning, improving consistency and creating auditable reasoning trails for human review. |
| **Versioned prompt templates** | Judge prompts are the most sensitive component. Stored as separate files with version tracking. Never hardcoded. |
| **Cohen's kappa meta-evaluation** | Inter-rater agreement between judge and human expert is the primary quality signal — target >90% agreement on binary pass/fail. |

---

## Tech Stack

- **Python 3.12+** with `uv` for package management
- **Pydantic v2** — strict typed I/O at all boundaries
- **pydantic-settings** — config from `.env`, never hardcoded
- **LiteLLM** via OpenRouter — single key for Claude, GPT, Gemini
- **spaCy + scispaCy** — biomedical NER for Tier 1
- **scikit-learn + krippendorff** — agreement metrics for meta-eval
- **pytest + pytest-asyncio** — test coverage for each tier independently

---

## Project Structure

```
soap-notes-eval/
├── src/
│   ├── config.py              # Central config (pydantic-settings)
│   ├── tier1/
│   │   ├── entities.py        # spaCy + scispaCy entity extraction
│   │   ├── structure.py       # Section completeness & structural validation
│   │   └── pipeline.py        # Tier 1 orchestrator
│   ├── tier2/
│   │   ├── judge.py           # LLM-as-a-judge orchestrator
│   │   └── schemas.py         # Pydantic verdict models
│   ├── data/
│   │   ├── models.py          # SOAP note Pydantic models
│   │   └── loaders.py         # Dataset loaders + section parser
│   └── meta_eval/
│       ├── agreement.py       # Cohen's kappa, Krippendorff's alpha
│       └── calibrate.py       # Judge calibration vs ground truth
├── data/samples/
│   ├── download.py            # Download 2-3 samples per HuggingFace dataset
│   ├── generate_degraded.py   # Hybrid programmatic + LLM degradation
│   ├── manifest.json          # Catalog of all samples (good + degraded)
│   └── degraded/
│       ├── manifest.json      # Ground-truth failure labels
│       └── *.json             # 18 degraded note variants
├── prompts/
│   ├── manifest.json          # Active version tracking
│   └── tier2_judge_v001.md    # PDQI-9-adapted judge prompt
├── tests/
│   ├── conftest.py            # Shared fixtures (good + degraded notes)
│   ├── test_tier1.py          # Tier 1 tests (10 cases)
│   ├── test_tier2.py          # Tier 2 tests (10 unit + 3 integration)
│   └── test_meta_eval.py      # Agreement metric tests (15 cases)
├── output/
│   ├── tier1_sample_report.json
│   └── tier2_sample_report.json
└── scripts/
    ├── emit_tier1_report.py
    └── emit_tier2_report.py
```

---

## Setup

### Prerequisites

- Python 3.12
- [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- An [OpenRouter](https://openrouter.ai) API key

### Installation

```bash
git clone <repo-url>
cd soap-notes-eval

# Copy and populate the env file
cp .env.example .env
# Edit .env — add OPENROUTER_API_KEY

# Install dependencies (uv reads pyproject.toml, generates uv.lock)
uv sync

# Install the scispaCy biomedical NER model
uv add "en_core_sci_sm @ https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz"
```

### Data Preparation

```bash
# Download 2-3 samples per dataset (adesouza1, ACI-Bench, Omi Health)
uv run python data/samples/download.py

# Generate synthetically degraded variants (programmatic + LLM)
uv run python data/samples/generate_degraded.py
```

---

## Usage

### Tier 1 — Automated Screening

```python
from src.data.loaders import parse_soap_sections
from src.data.models import SOAPNote
from src.tier1.pipeline import run_tier1

note = SOAPNote(
    note_id="example_001",
    source_dataset="custom",
    transcript="Doctor: ...\nPatient: ...",
    note_text="Subjective:\n...\n\nObjective:\n...\n\nAssessment:\n...\n\nPlan:\n...",
    sections=parse_soap_sections("Subjective:\n...\n\nObjective:\n..."),
)

report = run_tier1(note)
print(report.to_json())
```

### Tier 2 — LLM Judge

```python
import asyncio
from src.tier2.judge import judge_note

verdict = asyncio.run(judge_note(note))
print(f"Overall: {verdict.overall_verdict.value}")   # "pass" or "fail"
print(f"Escalate to Tier 3: {verdict.escalate_to_tier3}")
```

### Meta-Evaluation

```python
from src.meta_eval.agreement import compute_agreement

result = compute_agreement(
    judge_labels=["pass", "fail", "pass", "fail"],
    human_labels=["pass", "fail", "fail", "fail"],
)
print(f"Agreement: {result.percent_agreement:.1%}")
print(f"Cohen's kappa: {result.cohens_kappa:.3f} ({result.kappa_interpretation})")
```

### Emit Sample Reports

```bash
uv run python scripts/emit_tier1_report.py   # → output/tier1_sample_report.json
uv run python scripts/emit_tier2_report.py   # → output/tier2_sample_report.json
```

---

## Testing

```bash
# Unit + schema validation tests (no API key required)
uv run pytest tests/ -v

# Include LLM integration tests (requires OPENROUTER_API_KEY in .env)
RUN_INTEGRATION_TESTS=1 uv run pytest tests/ -v
```

**Coverage:**
- `test_tier1.py` — good notes pass; each degradation type triggers expected failure; edge cases
- `test_tier2.py` — schema chain-of-thought enforcement; consistency constraints; JSON parsing
- `test_meta_eval.py` — agreement metrics on known pairs; calibration detection rates; edge cases

---

## Evaluation Criteria (PDQI-9 Adapted)

| Criterion | Pass Condition |
|---|---|
| **Accuracy** | All facts traceable to transcript |
| **Completeness** | Critical transcript facts present in note |
| **Succinctness** | No redundant sentences or padding |
| **Organization** | All 4 SOAP sections present, correct order |
| **Consistency** | Subjective → Assessment → Plan tells coherent story |
| **Appropriateness** | Language and management consistent with standard practice |

---

## Synthetic Degradation Types

| Type | Method | What's Broken |
|---|---|---|
| `missing_section` | Programmatic | Assessment section removed |
| `omitted_findings` | Programmatic | Clinical keywords removed from Subjective |
| `redundancy_bloat` | Programmatic | Plan sentences duplicated + filler added |
| `structural_errors` | Programmatic | Plan appears before Assessment |
| `hallucinated_entities` | LLM-assisted | Plausible but unsupported medications/diagnoses injected |
| `internal_contradiction` | LLM-assisted | Contradiction between Subjective and Assessment |

---

## Craftsmanship: What I Paid Close Attention To

### 1. The Meta-Evaluation Loop

Most eval systems stop at "the judge says pass." This system asks the harder question: *how do you know the judge is trustworthy?*

`src/meta_eval/agreement.py` implements Cohen's kappa and Krippendorff's alpha between judge verdicts and ground-truth labels. `src/meta_eval/calibrate.py` tracks per-failure-type detection rates (did the judge catch `missing_section`? `hallucinated_entities`?). This is the calibration loop that enables iterative prompt refinement — the same loop described in Husain's Critique Shadowing methodology, which reports >90% judge-human agreement achievable in as few as three iterations.

### 2. Schema-Enforced Chain-of-Thought

`src/tier2/schemas.py` uses Pydantic validators to enforce the chain-of-thought pattern at the *model level* — not just in the prompt. `CriterionVerdict` raises `ValidationError` if the rationale is fewer than 10 characters. `Tier2Verdict` raises if `overall_verdict` is PASS while any criterion is FAIL or a hallucination is detected. The LLM cannot produce an inconsistent verdict that passes schema validation.

### 3. Graceful Degradation in Entity Extraction

`src/tier1/entities.py` tries the scispaCy biomedical model (`en_core_sci_sm`) but silently falls back to `en_core_web_sm` if unavailable. The entity classification heuristic (`_classify_entity`) uses clinical vocabulary patterns rather than relying solely on model labels — because `en_core_sci_sm` returns generic `ENTITY` labels that require post-classification anyway. The system stays functional at both full and reduced capability.

---

## Future Work

- **Tier 3 frontend** — scaffold is in place; build in Cursor for visual iteration with browser preview
- **Online evaluation** — real-time feedback loops and production monitoring
- **Generator self-correction** — judge feedback improving the note-generation model
- **Full dataset processing** — currently processes samples only; architecture is dataset-agnostic
- **Deployment infrastructure** — local-first by design; no Docker or CI/CD
