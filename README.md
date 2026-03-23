# DeepScribe SOAP Note Evaluation Suite

An offline evaluation system for AI-generated SOAP notes from doctor-patient conversations. Uses a tiered architecture that balances cost, speed, and clinical validity — from fast deterministic checks to LLM-as-a-judge to human expert review.

---

## How I Approached This

I want to be transparent about my process, because I think the thinking matters as much as the code.

### Starting from the problem, not the solution

I began by reading the assessment carefully and recognizing that the core ask is *evaluation*, not generation. This sounds obvious, but it's a distinction I had to keep reminding myself of throughout my research — the literature on AI-generated SOAP notes frequently blurs the line between "here's how to make notes better" and "here's how to know if notes are good." My job was the latter.

I commissioned two structured Deep Research reports — one on [AI SOAP note evaluation methods](docs/AI_SOAP_NOTE_GENERATION_RESEARCH.md) and one on [meta-evaluation of LLM judges](docs/EVALUATING_LLM_JUDGE_RESEARCH.md) — and then spent significant time actually reading through them, following citations to the primary sources, and forming my own conclusions. This was not a skim. I went into the MTS Dialogue paper (Ben Abacha et al., 2023), the NotChat paper that produced the Omi Health dataset, the UCSF/Stanford patient safety study (Dai et al., 2025), the PDQI-9 validation study, and Hamel Husain's widely-referenced guide to LLM-as-a-judge evaluation. The design decisions documented in [`docs/DESIGN_RESEARCH_AND_DECISIONS.md`](docs/DESIGN_RESEARCH_AND_DECISIONS.md) came out of that process.

### What I brought vs. what I learned

I'm familiar with classical ML — supervised vs. unsupervised approaches, cost/latency tradeoffs, the importance of training/validation/test splits, common techniques like linear regression, KNN, random forests. I understand what it means to evaluate an evaluator and why you can't just grade your own homework. What I did *not* walk in knowing was the specific clinical NLP tooling (scispaCy for biomedical NER, ClinicalBERT for semantic similarity), the PDQI-9 rubric, or the specific failure taxonomy for clinical notes. Those came from the research. The architecture is mine; many of the specific tools were chosen based on what the literature recommended for this domain.

### The meta-evaluation problem — the sneaky thing

The moment that shaped the entire project was realizing: *I need to evaluate the evaluation system. This is the sneaky thing.* If I build an LLM judge, how do I know the judge is good? If I just run it against good SOAP notes and it says "good," that tells me almost nothing. I need bad SOAP notes — with *known* failure types — so I can measure whether the judge actually catches what it should catch.

This is why the synthetic degradation suite exists. The existing datasets (MTS Dialogue, ACI-Bench, Omi Health) only contain good examples. To test an evaluator, you need both good and bad, with ground-truth labels for what's wrong. So I generate intentionally degraded variants — missing sections, hallucinated entities, internal contradictions — and use those as the test bed for the judge itself.

### Why a tiered architecture

Reading through the evaluation literature, I kept noticing a pattern: every method had real tradeoffs. Traditional NLP metrics (ROUGE, BERTScore) are fast and cheap but correlate poorly with clinical quality. LLM-as-a-judge is powerful but slow and expensive. Human expert review is the gold standard but doesn't scale. No single approach covers everything.

This led me to the tiered design — not because I'd seen it in a textbook, but because it naturally fell out of the tradeoff analysis. Tier 1 handles things you can check deterministically in milliseconds (are all SOAP sections present? is there obvious redundancy?). Tier 2 handles judgment that requires language understanding (is this note accurate relative to the transcript?). Tier 3 is where humans close the loop. The principle is: conquer the cheap deterministic checks before investing in expensive LLM calls, and use LLM judgment to triage what needs human eyes. Each tier filters down the volume for the next.

### The domain expert UX problem

This is the part I feel most strongly about. A lot of the evaluation discussion in the literature centers on metrics, models, and golden datasets. But how are you going to *create* that golden dataset? Domain experts — the clinicians whose judgment you need — are not technical. They're not going to run Python scripts or parse JSON. The bottleneck in clinical AI evaluation is not compute; it's expert time.

So the question becomes: how do you make it as easy as possible for a health professional to provide their expertise? You build a workspace where they see the dialogue, the generated SOAP note, and the judge's annotations side-by-side — and can accept, reject, or modify those annotations through simple point-and-click. The diff between what the judge said and what the expert decided becomes the training signal for the next iteration of the judge prompt. That's the flywheel: make expert annotation cheap enough that you can actually build the golden dataset you need.

### What the literature told me about binary scoring

One specific finding shaped the Tier 2 design significantly. The Hugging Face LLM-as-a-judge cookbook showed that two human raters had only 0.563 correlation when scoring on a continuous scale — but after switching to structured evaluation with a small integer scale and chain-of-thought reasoning, correlation jumped to 0.843. The broader LLM-as-a-judge literature reinforces this: domain expert pass/fail judgments correlate better with actual quality than granular numeric scores. Between this and the documented rater drift on numeric scales, I committed to binary pass/fail for all criteria. It's simpler, more actionable, and more reliable.

### Honest scoping under time constraints

The assessment asks for 3-5 hours of build. I spent a significant chunk of that on research — reading papers, following citations, understanding the problem space. This was a deliberate tradeoff, not a failure to plan. With AI coding tools, iterating on builds has become extremely cheap. But so has deep domain-specific research. The payoff of upfront research isn't avoiding failure or minimizing iteration — it's not reinventing the wheel. You use available public domain knowledge as a base to get something functional quickly, then iterate as you tailor it to your use case. The key is keeping first principles in mind: it's no good to copy over a base that doesn't fit your problem.

Things I thought about but explicitly scoped out:
- **Online evaluation / real-time feedback loops.** Valuable in production, but fundamentally a deployment concern rather than an eval design concern.
- **Generator self-correction.** Having the judge LLM provide feedback to the note-generating LLM in real-time is a compelling idea, but it's a product feature, not an evaluation system.
- **End-user edit flywheel.** Capturing what physicians change in generated notes — the way [Wispr Flow](https://wisprflow.ai/) learns from your text corrections — could be an incredibly rich data source. But it raises HIPAA/PII concerns and is more of a data pipeline problem than an eval problem.
- **Head-to-head frontier model comparison.** The research revealed a genuine gap: nobody has published a clean comparison of frontier models on clinical note generation benchmarks like MTS Dialogue or ACI-Bench. For an individual researcher, this is prohibitively expensive. But for a company like DeepScribe, this would be highly valuable to implement internally — it directly answers "which model should we use for generation?" and "how much quality do we gain from the latest model release?" The eval system architecture here is model-agnostic by design, so running the same evaluation suite across different generator models is straightforward to add.

### What needs more iteration

**Tier 3 UX.** Let me be honest: the current UI is not polished. The three-column layout exists, CRUD on annotations works, diff export works — but it doesn't look good, and there's plenty of iteration I could do on my own before I'd even need to loop in a physician. Progress indicators, keyboard navigation for speed, better visual hierarchy, surfacing flagged notes for priority review — these are all things I know would improve the experience. Time constraint. But the core information architecture is right: transcript | SOAP note | judge annotations, side by side, with the ability to accept/reject/modify and capture why.

**Judge prompt calibration.** The Tier 2 judge prompt (`prompts/tier2_judge_v001.md`) is a v001 for a reason. The critique shadowing methodology — iterate between domain expert review and prompt refinement until you reach >90% agreement — is the process I've designed the system to support, but actually *running* that process requires a domain expert and multiple iterations. The meta-eval module (`src/meta_eval/`) provides the agreement metrics; the Tier 3 UI provides the annotation workflow; the versioned prompt system provides the iteration mechanism. The pieces are in place for the loop, but the loop hasn't been run yet.

**Sample size.** The assessment mentions 100 SOAP notes. The current implementation works with 9 source notes + 30 degraded variants = 39 total. The architecture is dataset-agnostic — scaling to 100+ is a config change, not a redesign — but I prioritized depth of evaluation design over breadth of data processing within the time constraint. The scripts currently emit single-note sample reports; batch processing across the full dataset with aggregate reporting is a natural next step.

**Aggregate reporting / dashboard.** The assessment mentions dashboard as a bonus deliverable. I don't have one. The individual JSON reports from Tier 1 and Tier 2 exist, but there's no cross-note summary showing patterns like "hallucinations are most common in the Plan section" or "completeness failures cluster in notes from dataset X." This is where the meta-eval module's per-failure-type detection rates would shine if run at scale.

---

## How This Serves Goals 1 and 2

The assessment defines two goals:

**Goal 1: Move fast** — "quickly measure and incorporate the latest models and PR changes, without waiting days/weeks." This is about velocity of iteration: when a new model drops or a PR changes the generation pipeline, how quickly can you know whether things got better or worse?

My approach to the assessment itself reflects this principle — I discuss the research-before-building tradeoff in "Honest scoping" above.

In the system itself: Tier 1 runs in ~50-200ms per note with zero API calls, so it can gate a CI pipeline or run on every PR. Tier 2 runs asynchronously in batch. Both produce structured JSON that can be diffed across runs. When a new model or prompt change lands, you re-run the suite and compare. The architecture is designed so that adding a new model to evaluate is a config change, not a code change.

**Goal 2: Understand production quality** — "measure note quality in the wild, quickly detect regressions or areas of lower quality." Tier 2 provides the deeper quality signal — six PDQI-9-adapted criteria evaluated by an LLM judge, with hallucination detection via transcript grounding. The meta-evaluation module then answers the question the assessment explicitly asks: "how do you know if the eval is working?" By measuring judge-vs-human agreement (Cohen's kappa) and per-failure-type detection rates, you get a quantitative answer to whether your evaluator is trustworthy, and where it's falling short.

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

| Decision | Rationale | Source |
|---|---|---|
| **Binary pass/fail (not Likert)** | Simpler judgments are more reliable and actionable. Numeric scales introduce rater drift and ambiguous midpoints. Human rater correlation jumped from 0.563 to 0.843 when switching to structured evaluation with chain-of-thought. | HuggingFace LLM-as-Judge cookbook; LLM-as-Judge literature |
| **Reference-free as primary mode** | Production notes have no gold-standard reference. The system evaluates using only the source transcript + internal consistency. Even physician-authored "Gold" notes contained hallucinations 20% of the time. | Palm et al. 2025; Asgari et al. 2025 |
| **Chain-of-thought before verdict** | Forces the judge to articulate reasoning before scoring — a form of test-time scaling that improves consistency and creates auditable reasoning trails for human review. | G-Eval (Liu et al., EMNLP 2023) |
| **Versioned prompt templates** | The judge prompt is the most sensitive component. The evaluation prompt matters more than the model choice — invest in rubric engineering before switching models. Stored as separate files with version tracking. Never hardcoded. | LLM-as-Judge literature |
| **Cohen's kappa meta-evaluation** | Inter-rater agreement between judge and human expert is the primary quality signal. Literature reports >90% agreement achievable in as few as three iterations of the calibration loop. | Croxford et al. 2025; LLM-as-Judge literature |

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

To test the evaluator, I needed bad SOAP notes with known failure types — the existing datasets only provide good examples. The degradation suite generates variants using both programmatic manipulation and LLM-assisted generation:

| Type | Method | What's Broken |
|---|---|---|
| `missing_section` | Programmatic | Assessment section removed |
| `omitted_findings` | Programmatic | Clinical keywords removed from Subjective |
| `redundancy_bloat` | Programmatic | Plan sentences duplicated + filler added |
| `structural_errors` | Programmatic | Plan appears before Assessment |
| `hallucinated_entities` | LLM-assisted | Plausible but unsupported medications/diagnoses injected |
| `internal_contradiction` | LLM-assisted | Contradiction between Subjective and Assessment |

27 degraded variants across 9 source notes, each with ground-truth labels in `data/samples/degraded/manifest.json`. These become both pytest fixtures and calibration targets for the meta-evaluation module.

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

49 tests pass (unit + schema validation). 3 integration tests are available when an API key is configured.

---

## Craftsmanship: What I Paid Close Attention To

### 1. Designing for the meta-evaluation loop

Most eval systems stop at "the judge says pass." The harder question — the one I kept coming back to during my research — is: *how do you know the judge is trustworthy?*

The system is designed around this question. `src/meta_eval/agreement.py` implements Cohen's kappa and Krippendorff's alpha to measure judge-vs-human agreement. `src/meta_eval/calibrate.py` tracks per-failure-type detection rates — did the judge catch `missing_section`? Did it catch `hallucinated_entities`? The synthetic degradation suite provides the ground-truth labels. The Tier 3 review UI provides the human annotation workflow. The versioned prompt system provides the iteration mechanism. Together, these form the calibration loop: domain expert reviews judge output, disagreements become prompt refinements, re-run, measure agreement, repeat until convergence.

I haven't run that loop — it requires a domain expert and multiple iterations — but the system is designed so that when a clinician sits down to use it, every piece is in place to start turning.

### 2. The Tier 3 expert review design

This is where I see the most remaining work, and also where I think the highest leverage is. The insight that shaped this tier came from recognizing that evaluation is ultimately *for* humans — specifically, non-technical health professionals whose time is the scarcest resource in the system. Making their review experience frictionless isn't a nice-to-have; it's the bottleneck that determines whether the whole meta-evaluation loop actually works.

The current implementation provides the core information architecture: three-column layout (transcript | SOAP note | judge annotations), CRUD operations on annotations, reasoning capture, and diff export for calibration. It's not pretty yet — I'd be the first to say it needs polish before putting it in front of a physician. But the data flow is right: every expert accept/reject/modify decision is captured with reasoning and diffed against the original judge output. That diff is the training signal for the next prompt iteration.

### 3. Schema-enforced chain-of-thought

`src/tier2/schemas.py` enforces the chain-of-thought pattern at the *data model level*, not just in the prompt. `CriterionVerdict` raises `ValidationError` if the rationale is fewer than 10 characters. `Tier2Verdict` raises if `overall_verdict` is PASS while any criterion is FAIL or a hallucination is detected. The LLM literally cannot produce an inconsistent verdict that passes schema validation. This is a small thing, but it's the kind of structural guarantee that prevents silent failures in a pipeline where you're processing notes in batch.

---

## Research References

Key sources that shaped the design (full references in `docs/`):

- **Asgari et al. 2025** — CREOLA framework: 12,999 clinician-annotated sentences, 1.47% hallucination rate, 44% classified as "major." Hallucinations most common in Plan section.
- **Palm et al. 2025** — PDQI-9 applied to 97 encounters. AI notes scored higher on Thoroughness and Organization, lower on Succinctness and Internal Consistency.
- **Croxford et al. 2025** — PDSQI-9 + LLM-as-a-Judge. GPT-o3-mini with 5-shot prompting achieved ICC 0.818 with human evaluators. 96% reduction in eval time.
- **Dai et al. 2025** — UCSF/Stanford patient safety study. Medication and treatment errors were the most significant safety risk. AI generated severe errors in 22% of cases.
- **Mukherjee et al. 2026** — Meta-evaluation collapse: recursive LLM evaluation converges on internally consistent but fragile fixed points detached from human truth.
- **HuggingFace LLM-as-Judge cookbook** — Practical demonstration of scoring improvements from structured evaluation + chain-of-thought (0.563 → 0.843 correlation with human raters).
- **Ben Abacha et al. 2023** — MTS Dialogue dataset: 1,700 conversations. No commercial LLM benchmarks attempted (a gap that still exists).

---

## Future Work

Beyond the Tier 3 UX refinement and judge prompt calibration discussed above:

- **Online evaluation** — Real-time feedback loops and production monitoring. The tiered architecture supports this (Tier 1 can run synchronously in a request pipeline), but the orchestration infrastructure isn't built.
- **Generator self-correction** — Having the judge provide feedback to the note-generating LLM so it can fix its notes in real time. This is a compelling product feature that sits at the boundary of evaluation and generation.
- **End-user edit flywheel** — Capturing what physicians change in generated notes (the way [Wispr Flow](https://wisprflow.ai/) learns from text corrections) and feeding those diffs back as evaluation signal. Raises HIPAA/PII concerns, but the edit patterns themselves — are they correcting medications? moving sentences between sections? — would be an incredibly rich data source for understanding systematic failure modes. Subject to survivorship bias though: the edits that get made are the errors that get caught, and the dangerous ones are the ones that slip through undetected.
- **Full dataset processing** — Currently processes samples only; the architecture is dataset-agnostic and ready for scale.
