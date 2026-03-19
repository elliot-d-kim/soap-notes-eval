# Design Research and Decisions

## Summary

### Evaluation Methods Overview

- **Traditional NLP metrics** (ROUGE, BERT score): Fast and cheap but challenged quality for clinical applications
- **LLM as a judge**: Promising approach given DeepScribe's domain; can be combined with other methods for a blend of fast/cheap indicators and robust evaluation
- **Validated rubrics**: Formal rubrics mentioned as gold standard for benchmarking
- **Entity-level evaluation**: Clinical name entity relationships could be part of the solution

### Key Evaluation Dimensions

- Accuracy and factual fidelity
- Completeness and thoroughness (automated methods outperform humans here)
- Succinctness and relevance (AI susceptible to note bloat)
- Organization and structure
- Internal consistency
- Clinical appropriateness

### Critical Failure Modes Identified

- **Hallucination taxonomy**: Fabrication, negation, contextual errors
- **Omissions**: More frequent than hallucinations; most common in current issues, past medical history, and plan sections
- **Medication errors**: UCSF/Stanford study found AI generated severe errors in 22% of medical cases; wrong medications, incorrect dosages, fabricated prescriptions
- **Negation errors, section misplacement, demographic bias**

### Reference-Free vs Reference-Based Evaluation

- **Reference-free**: Critical for production deployment where gold standard notes don't exist
    - Transcript-grounded factuality checking
    - Internal consistency checking via NLI models
    - Quality estimation models trained on human scores
- **Reference-based**: Requires expensive ground truth datasets

### Datasets Analyzed

- **MTS Dialogue** (1.7K conversations): Synthetic conversations created from clinical notes; too long for older API token limits but manageable with modern models
- **ACI Bench**: Contains 87 complete dialogues and clinical notes
- **Omi Health dataset** (10K synthetic dialogues): Generated via GPT-4 using NotChat framework; includes SOAP summaries but all AI-generated

### Research Gap Identified

- No published head-to-head comparison of frontier commercial LLMs (GPT-4o, Claude Sonnet 4.5, Gemini) on clinical note generation tasks like MTS Dialogue
- Most studies use older models (GPT-3, GPT-4) or smaller open-source models
- Only 7% of medical summarization LLM studies conduct external validation; 3% perform patient safety assessments

### Proposed Evaluation System Architecture

**Tiered approach balancing cost, speed, and clinical validity**: 

**Tier 1 - Automated Screening** (every note, real-time):

- Entity-level extraction for medications, diagnoses, procedures
- Section completeness checks
- Redundancy detection
- Basic structural validation

**Tier 2 - LLM as a Judge** (every note, not real-time):

- Checklist-based evaluation using feedback-derived questions
- PDQI-9 style quality scoring
- Hallucination flagging via transcript-grounded NLI
- Flag notes below quality thresholds for Tier 3

**Tier 3 - Human Expert Review**:

- Review flagged notes and random samples

### Meta-Evaluation Challenge

- **Core problem**: Need to evaluate the evaluator itself
- **Solution requires**:
    - Dataset of both good and bad AI-generated SOAP notes
    - Human expert validation as ground truth
    - Cannot rely solely on existing datasets (only contain good examples)

### LLM as Judge Best Practices (from literature review)

**Metrics and validation**:

- Strong LLM judges reach ~80% agreement with human evaluators, matching human-to-human consistency
- Human baseline: Two human raters showed 0.563 correlation; improved to 0.843 with better rubric design
- Use Cohen's kappa or Krippendorff's Alpha for inter-rater agreement

**Prompt engineering critical factors**:

- **Binary pass/fail > numeric scales**: Simpler, more actionable, forces clarity on what matters
- **Chain-of-thought evaluation**: Include evaluation rationale field before final score
- **Small integer scales** (1-5) with descriptive anchors outperform continuous ranges
- **Few-shot examples with critiques**: Must include detailed domain expert reasoning

**Known biases to mitigate**:

- Position bias: Run pairwise comparisons twice with swapped order
- Verbosity bias: Explicitly include conciseness in rubric
- Self-preference bias: Use narrower scales or binary judgments

**Iterative refinement process**: 

1. Domain expert reviews dataset and provides pass/fail + detailed critiques
2. Build LLM judge using expert critiques as few-shot examples
3. Compare LLM judge output against domain expert on new samples
4. Refine prompt until acceptable agreement (>90% target) 
5. Apply judge at scale and perform error analysis
6. Repeat when system changes materially

### Critical Implementation Insight: User Interface for Domain Experts

- **Primary bottleneck**: Making evaluation easy for non-technical health professionals
- **Proposed UI design**:
    - Display dialogue, generated SOAP note, and LLM judge annotations side-by-side
    - Allow domain experts to accept/reject/modify/delete judge annotations via CRUD operations
    - Capture expert reasoning traces alongside scores
    - Use diffs between expert edits and judge outputs to improve judge
- **Reference**: Hamal Hussein's evaluation guide emphasizes removing all friction from domain expert review process; building custom web apps often necessary

### Data Generation Strategy

- Need both good and bad examples to test evaluator
- Existing datasets (MTS Dialogue, Omi Health) only provide good SOAP notes
- Must generate intentionally flawed notes or use early-iteration model outputs

### Scope Considerations for Assessment

**In scope**:

- Offline evaluation system with tiered architecture
- LLM as judge implementation with PDQI-9 criteria
- UI for domain expert review and judge calibration

**Out of scope** (noted as valuable but beyond time constraints):

- Online/live evaluation with real-time feedback loops
- Generator LLM using judge feedback to self-correct notes
- Flywheel capturing end-user edits (like Whisper's dictionary learning)

### Modern Context Advantages

- Token limits no longer constrain full dialogue processing (GPT-5.2: 272K context vs GPT-4 legacy: 8.2K)
- Frontier models (Claude Sonnet 4.5, GPT-5.4) significantly improved over GPT-03 used in most studies
- Structured generation and prompt caching reduce implementation overhead

### Key Philosophical Insight

- Evaluation system design is fundamentally about **organizing information rather than compressing it**
- Real business value comes from carefully examining data, not just automating judgment
- Domain expert involvement cannot be eliminated but can be made more efficient through good tooling
- Building evaluation infrastructure that enables fast manual inspection is characteristic of great AI research