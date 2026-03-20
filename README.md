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
          │    Tier 3 — Human Expert Review           │
          │    (three-column web UI)                  │
          │                                           │
          │  • Side-by-side: transcript / note / judge│
          │  • CRUD on judge annotations              │
          │  • Expert reasoning traces                │
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

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 20+ (for Tier 3 frontend)
- An [OpenRouter](https://openrouter.ai) API key (for Tier 2 LLM judge)

### Installation

```bash
git clone <repo-url>
cd soap-notes-eval

# Python dependencies
cp .env.example .env     # Add OPENROUTER_API_KEY
uv sync

# Tier 3 frontend dependencies
cd src/tier3/frontend && npm install && cd ../../..
```

### Data Preparation

```bash
# Download 2-3 samples per dataset (adesouza1, ACI-Bench, Omi Health)
uv run python data/samples/download.py

# Generate synthetically degraded variants (programmatic + LLM)
uv run python data/samples/generate_degraded.py
```

---

## Running

### Tier 1 & 2 — Evaluation Pipeline

```bash
# Emit sample reports
uv run python scripts/emit_tier1_report.py   # → output/tier1_sample_report.json
uv run python scripts/emit_tier2_report.py   # → output/tier2_sample_report.json
```

### Tier 3 — Expert Review UI

Start both servers, then open http://localhost:3000:

```bash
# Terminal 1 — FastAPI backend (API + SQLite persistence)
uv run uvicorn src.tier3.app:app --reload --port 8000

# Terminal 2 — Next.js frontend
cd src/tier3/frontend && npm run dev
```

Select a note, click "Start Review," annotate judge verdicts, and export the review as JSON for calibration.

### Tests

```bash
# Unit + schema validation (no API key required)
uv run pytest tests/ -v

# Include LLM integration tests (requires OPENROUTER_API_KEY)
RUN_INTEGRATION_TESTS=1 uv run pytest tests/ -v
```

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

### 3. Tier 3 Expert Review as a Calibration Tool

The review UI isn't just a dashboard — it's the feedback mechanism that closes the meta-evaluation loop. Every expert accept/reject/modify decision is captured with reasoning traces and diffed against the original judge output. The JSON export format is designed specifically to feed back into prompt refinement: when an expert rejects an accuracy verdict, that example becomes training signal for the next prompt iteration. This is how you move from "the judge agrees with me 78% of the time" to ">90%."

---

## Future Work

- **Online evaluation** — real-time feedback loops and production monitoring
- **Generator self-correction** — judge feedback improving the note-generation model
- **Full dataset processing** — currently processes samples only; architecture is dataset-agnostic
- **Deployment infrastructure** — local-first by design; no Docker or CI/CD
