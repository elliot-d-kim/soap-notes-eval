## Project: DeepScribe SOAP Note Evaluation Suite

Build an offline evaluation system for AI-generated SOAP notes from doctor-patient conversations. The system uses a tiered architecture that balances cost, speed, and clinical validity.

### Architecture

**Tier 1 — Automated Screening (runs on every note, real-time)**
- Entity-level extraction: medications, diagnoses, procedures (spaCy + scispaCy or medCAT)
- Section completeness checks: verify all SOAP sections present and non-empty
- Redundancy / note-bloat detection
- Basic structural validation (section ordering, formatting)
- Output: structured JSON with per-check pass/fail + extracted entities

**Tier 2 — LLM-as-a-Judge (runs on every note, async batch)**
- Checklist-based evaluation using PDQI-9-adapted criteria:
  - Accuracy / factual fidelity (transcript-grounded)
  - Completeness / thoroughness
  - Succinctness / relevance
  - Organization / structure
  - Internal consistency
  - Clinical appropriateness
- Binary pass/fail per criterion (NOT numeric scales)
- Chain-of-thought: require evaluation rationale BEFORE verdict
- Hallucination flagging via transcript-grounded NLI
- Flag notes scoring below threshold for Tier 3 review
- Output: structured JSON with per-criterion verdict, rationale, and overall recommendation

**Tier 3 — Human Expert Review Interface**
- Web UI displaying dialogue, generated SOAP note, and Tier 2 judge annotations side-by-side in three columns
- CRUD operations on judge annotations: accept / reject / modify / delete
- Capture expert reasoning traces alongside decisions
- Diff computation between expert edits and judge outputs (for judge calibration)
- Export review data for judge prompt refinement

### Tech Stack
- Python 3.12+
- uv (package management — reads pyproject.toml, generates uv.lock for reproducible installs)
- FastAPI (API layer)
- Pydantic v2 (structured I/O, strict validation)
- pydantic-settings (config from .env file — auto-reads .env, typed settings class)
- LiteLLM via OpenRouter (LLM calls — support Claude Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro as switchable backends via `openrouter/` prefix, single OPENROUTER_API_KEY)
- spaCy + scispaCy (Tier 1 NLP)
- Next.js + React + Tailwind + shadcn/ui (Tier 3 review UI — provides beautiful defaults; visual iteration in Cursor for the frontend phase)
- SQLite or DuckDB (local eval results store)
- pytest + pytest-asyncio (testing)

Model selection is config-driven via src/config.py using pydantic-settings (BaseSettings class that auto-reads .env). Model names use `openrouter/` prefix (e.g. `openrouter/anthropic/claude-sonnet-4-20250514`). Never hardcode a model name — always read from config. OPENROUTER_API_KEY lives in .env (gitignored).

### Project Structure
soap-eval/
├── src/
│   ├── tier1/           # Automated screening pipeline
│   │   ├── entities.py  # Entity extraction
│   │   ├── structure.py # Section completeness & validation
│   │   └── pipeline.py  # Orchestrator
│   ├── tier2/           # LLM-as-a-judge
│   │   ├── prompts/     # Judge prompt templates (versioned)
│   │   ├── judge.py     # Judge orchestrator
│   │   └── schemas.py   # Pydantic models for verdicts
│   ├── tier3/           # Expert review UI
│   │   ├── app.py       # Web application
│   │   └── components/  # UI components
│   ├── data/            # Data loading & preprocessing
│   │   ├── loaders.py   # Dataset-specific loaders
│   │   └── models.py    # Pydantic models for SOAP notes
│   ├── meta_eval/       # Meta-evaluation (evaluate the evaluator)
│   │   ├── agreement.py # Cohen's kappa, Krippendorff's alpha
│   │   └── calibrate.py # Judge calibration utilities
│   └── config.py        # Central configuration
├── data/
│   └── samples/         # Dataset samples (adesouza1, ACI, Omi)
│       ├── degraded/    # Synthetically degraded with failure labels
│       └── manifest.json
├── tests/
│   ├── test_tier1.py
│   ├── test_tier2.py
│   └── test_meta_eval.py
├── prompts/             # Versioned prompt templates
│   └── manifest.json    # Tracks active version per prompt
├── .env               # OPENROUTER_API_KEY (gitignored)
├── .gitignore
├── pyproject.toml
├── uv.lock            # Reproducible dependency lock
└── README.md

### Data Preparation
See /docs/DATA_PREPARATION.md for dataset downloads, synthetic degradation (hybrid programmatic + LLM), manifest structure, and test fixture expectations.

### Key Design Decisions & Tradeoffs

1. **Binary pass/fail over numeric scales** — Literature shows simpler judgments are more reliable and actionable. Numeric scales introduce rater drift and ambiguous midpoints.

2. **Reference-free evaluation as primary mode** — Production SOAP notes have no gold-standard reference. The system must evaluate quality using only the source transcript + internal consistency. Reference-based mode is secondary (for dev/test with datasets that include ground truth).

3. **Chain-of-thought before verdict** — Forces the judge to articulate reasoning, improving consistency and enabling human auditing of judge logic.

4. **Versioned prompt templates** — Judge prompts are the most sensitive component. Store as separate files with version tracking. Never hardcode.

5. **Explicit bias mitigations** — Position bias: N/A for single-note eval (but implement swapped-order for any pairwise comparisons). Verbosity bias: rubric explicitly scores succinctness. Self-preference: use binary judgments to reduce.

6. **Meta-evaluation built in from day one** — Include a calibration module that computes inter-rater agreement between judge and human expert. Target: >90% agreement on binary pass/fail. This is what separates a demo from a real eval system.

### Out of Scope
Do NOT implement any of the following. Reference in README as future work only:
- Online / live evaluation (real-time feedback loops, production monitoring)
- Generator self-correction (judge feedback improving the note-generation model)
- End-user edit capture (clinician edits flowing back into model training)
- Full dataset processing (process samples only, 10–20 examples; architecture must be dataset-agnostic)
- Deployment infrastructure (no Docker, CI/CD, or cloud; local-first)

### Craftsmanship Signals
- Type hints everywhere, Pydantic for all I/O boundaries
- Async where it matters (LLM calls), sync where it doesn't
- Comprehensive docstrings with clinical context
- Test coverage for each tier independently
- README that explains WHY, not just HOW — reference /docs/STRATEGY.md for the strategic rationale
- Clean git history with semantic commits
- README is a continuous artifact — start during scaffolding (setup + "Why" from /docs/STRATEGY.md), update incrementally per tier

### Reference Documents
All research and requirements live in /docs/:
- /docs/ASSESSMENT.md — assessment requirements
- /docs/AI_SOAP_NOTE_GENERATION_RESEARCH.md — SOAP note evaluation research
- /docs/EVALUATING_LLM_JUDGE_RESEARCH.md — LLM-as-a-judge frameworks
- /docs/DESIGN_RESEARCH_AND_DECISIONS.md — design decisions
- /docs/STRATEGY.md — strategic rationale (for README only)
- /docs/DATA_PREPARATION.md — dataset acquisition, synthetic degradation plan, test fixtures
Dataset samples in /data/samples/ (adesouza1, ACI, Omi).
Synthetically degraded samples with ground-truth failure labels in /data/samples/degraded/.

### Claude Code Workflow
- Explore first, then plan, then code
- Use Context7 `find-doc` skill + CLI for fresh library documentation (not the MCP)
- Use Agent Teams for parallel branches (e.g., Tier 1 and Tier 2 can scaffold in parallel)
- Keep each iteration in a fresh context window to avoid degradation past ~100K tokens ("the Dumb Zone")
- Verify via test suite at each stage — define validation criteria upfront in this file
- Emit sample JSON output after each tier (assessment deliverable: "sample output — JSON reports, charts, dashboards")
- For frontend (Tier 3 UI): scaffold structure with Claude Code, then switch to Cursor for visual iteration with built-in browser preview