# Evaluating AI SOAP Note Generation: A Comprehensive Technical Guide

<aside>
📋

**Research Charter**

- **Motivation:** Provide a comprehensive, decision-ready reference for designing evaluation systems for AI-generated SOAP notes — directly applicable to eval design work.
- **Questions this research addresses:**
    - What dimensions should SOAP note evaluation cover?
    - What metrics and scoring rubrics exist in the literature?
    - How do you handle semantic equivalence vs. lexical divergence?
    - What are the trade-offs between automated metrics and human/clinician evaluation?
    - How do you build scalable eval pipelines (LLM-as-judge, checklist-based, reference-free)?
    - What are known failure modes and edge cases specific to SOAP notes?
- **Relevant strategic decisions:** Evaluation dimension prioritization, automated vs. human eval trade-offs, pipeline architecture choices
- **Scope:** Technical/engineering focus — metrics, rubrics, pipeline architecture, failure modes. Not a product review.
</aside>

---

## 1. The Evaluation Landscape

<aside>
📊

**At a Glance**

| Approach | Strengths | Weaknesses | Best For |
| --- | --- | --- | --- |
| **Automated metrics** (ROUGE, BERTScore) | Fast, cheap, reproducible | Poor correlation with clinical quality; penalize valid paraphrases | Coarse regression testing, CI gates |
| **Clinical NER / entity F1** | Captures factual content; domain-specific | Misses reasoning quality, note structure | Fact extraction validation |
| **Validated rubrics** (PDQI-9, PDSQI-9) | Psychometrically validated; multi-dimensional | Expensive; requires expert reviewers; ~10 min/note | Gold-standard benchmarking |
| **LLM-as-a-Judge** | Scalable; high ICC with humans; ~22 sec/eval | Can miss hallucinations; requires careful calibration | Continuous monitoring at scale |
| **Checklist-based** (feedback-derived) | Grounded in real clinician concerns; interpretable | Coverage limited by feedback corpus | Production quality gates |
</aside>

Evaluating AI-generated SOAP notes is a multi-dimensional problem that sits at the intersection of NLP evaluation, clinical documentation standards, and patient safety. The core tension is between **scalability** (automated metrics that run in milliseconds) and **clinical validity** (expert review that captures nuances automated systems miss).

Traditional NLP metrics like ROUGE and BERTScore were designed for general summarization and demonstrate poor correlation with human judgment in medical contexts. A 2025 PMC pilot study found that neither standard automatic metrics nor LLM judges reliably detect factual errors and semantic distortions (hallucinations) in medical summaries — the Pearson correlation between automated quality scores and expert opinions reached only 0.688 for relevance.[[1]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12786185/) The field has consequently moved toward multi-layered evaluation strategies that combine automated screening with structured human review.

---

## 2. Evaluation Dimensions

A robust SOAP note evaluation framework must assess quality across multiple orthogonal dimensions. Drawing from the PDQI-9, PDSQI-9, and recent literature, the key dimensions are:

### 2.1 Accuracy & Factual Fidelity

The most safety-critical dimension. Does the note faithfully represent what occurred in the encounter? This encompasses:

- **Fabrication** — generating information not present in the source (e.g., inventing a medication the patient doesn't take)
- **Negation errors** — contradicting what was actually said (e.g., "patient denies chest pain" when they reported it)
- **Contextual errors** — mixing topics or misattributing information between problems
- **Causality errors** — speculating about causes without source support

The CREOLA framework (Asgari et al., 2025) analyzed 12,999 clinician-annotated sentences across 18 experimental configurations and observed a **1.47% hallucination rate** and a **3.45% omission rate**. Critically, 44% of hallucinations were classified as "major" (could impact diagnosis/management if uncorrected), compared to only 16.7% of omissions.[[2]](https://www.nature.com/articles/s41746-025-01670-7) Hallucinations were most common in the **Plan section** (21%), which is especially concerning since this section contains direct clinical instructions.

### 2.2 Completeness & Thoroughness

Does the note capture all clinically relevant information? The PDQI-9 study across 97 encounters found that AI ambient notes scored *higher* than physician-authored notes on Thoroughness (4.22 vs. 3.80, p < 0.001) — AI tends to over-include rather than under-include.[[3]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12586549/) However, omission remains the more *frequent* error type overall (3.45% vs. 1.47% for hallucinations).[[2]](https://www.nature.com/articles/s41746-025-01670-7)

Completeness checking can be operationalized through:

- **Section-level coverage** — verifying each SOAP section contains expected content
- **Problem-level coverage** — ensuring every discussed problem has a corresponding Assessment and Plan entry
- **Entity-level coverage** — checking that key clinical entities (medications, diagnoses, procedures) from the transcript appear in the note

### 2.3 Succinctness & Relevance

Is the note concise without sacrificing essential information? The PDQI-9 study found physician notes significantly outperformed AI on Succinctness (4.40 vs. 3.72, p < 0.001).[[3]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12586549/) "Note bloat" — verbose, redundant documentation — is a well-documented AI scribe failure mode. Evaluating succinctness requires balancing two competing objectives: high completeness recall and minimal redundancy.

### 2.4 Organization & Structure

Is information correctly placed within the SOAP framework? AI notes scored higher on Organization (4.19 vs. 4.01, p = 0.03) in the PDQI-9 study.[[3]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12586549/) However, section misplacement remains a known failure — subjective observations appearing in the Objective section, or assessment findings leaking into the Plan.[[4]](https://rocketdiscoverycentre.ca/wp-content/uploads/2025/02/SOAP_Note_Quality_Assessment__arXiv_-1.pdf)

The SOAP structure itself encodes clinical reasoning: Subjective and Objective inform Assessment, which drives Plan. Evaluating whether this logical chain is preserved requires understanding the *relationships* between sections, not just their individual content.

### 2.5 Internal Consistency

Do different parts of the note contradict each other? Physician notes scored higher on Internal Consistency (4.47 vs. 4.31, p = 0.004).[[3]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12586549/) This dimension is particularly important for multi-problem notes where cross-references between Assessment items and Plan items must align.

### 2.6 Clinical Appropriateness

Is the note's language, reasoning, and content appropriate for the clinical specialty? This includes correct use of medical terminology, appropriate level of detail for the specialty, and documentation that supports billing and compliance requirements.

---

## 3. Metrics & Measurement Approaches

<aside>
📊

**At a Glance**

| Metric | Type | What It Measures | Correlation w/ Human Judgment |
| --- | --- | --- | --- |
| ROUGE-L | N-gram overlap | Longest common subsequence recall | Low in clinical text |
| ROUGE-2 | N-gram overlap | Bigram overlap (phrasal similarity) | Low–moderate |
| METEOR | Alignment-based | Fluency + stemming + synonyms | Moderate |
| BERTScore | Embedding similarity | Contextual semantic overlap | Weak in medical NLP (per Galileo AI) |
| ClinicalBERT F1 | Domain embedding | Clinical concept alignment | Higher than general BERTScore |
| CHRF++ | Character n-gram | Surface-level coherence | Moderate |
| NER Entity F1 | Entity extraction | Clinical entity recall/precision | High for factual content |
| PDQI-9 / PDSQI-9 | Human rubric | Multi-dimensional quality | Gold standard (ICC 0.867) |
| Checklist score | Binary Q&A | Feedback-derived quality criteria | Significant alignment with preferences |
</aside>

### 3.1 Traditional Automated Metrics

**ROUGE** (Recall-Oriented Understudy for Gisting Evaluation) measures n-gram overlap between generated and reference text. ROUGE-L captures longest common subsequence, while ROUGE-2 captures bigram overlap. In the scalable SOAP note generation framework (arXiv 2506.10328), ROUGE-2 better reflected phrasal and semantic overlap than ROUGE-L for clinical content.[[5]](https://arxiv.org/html/2506.10328v1)

**BERTScore** uses contextual embeddings to compute token-level cosine similarity. While it captures paraphrases better than ROUGE, performance is "highly domain-dependent" — correlations are weak in medical NLP contexts (59% vs. 47–50% for BLEU/ROUGE in personalized text, but these gains diminish in clinical domains).[[6]](https://galileo.ai/blog/bert-score-explained-guide)

**ClinicalBERT F1** uses embeddings from models pre-trained on clinical text (e.g., ClinicalBERT, BioBERT). The scalable SOAP framework found ClinicalBERT scores better captured clinical concept alignment than general BERTScore, with the gap between the two highlighting how "clinically tuned models capture semantic relevance more effectively."[[5]](https://arxiv.org/html/2506.10328v1)

**Key limitation:** All reference-based metrics require gold-standard notes, which are expensive to produce and themselves variable in quality. The PDQI-9 study found that even physician-authored "Gold" notes contained hallucinations 20% of the time.[[3]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12586549/)

### 3.2 Entity-Level Evaluation

Named Entity Recognition (NER) provides a more granular, clinically meaningful evaluation layer. By extracting clinical entities — medications, dosages, diagnoses, procedures, lab values — from both the source transcript and the generated note, you can compute entity-level precision, recall, and F1.

GPT-4 achieved F1 scores of 0.97 on clinical information extraction tasks, outperforming smaller models.[[7]](https://pmc.ncbi.nlm.nih.gov/articles/PMC11743751/) BioBERT achieved NER F1 scores of 0.926 for drug name extraction from clinical notes.[[8]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12099357/) Spark NLP clinical models achieved NER precision peaks of 0.989 for procedures.[[9]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12449662/)

Entity-level eval is particularly useful for detecting:

- **Omitted medications** — a missed med in the Plan is clinically dangerous
- **Fabricated diagnoses** — an entity in the note absent from the transcript
- **Dosage errors** — wrong numbers attached to correct medication names

### 3.3 Validated Human Evaluation Rubrics

**PDQI-9** (Physician Documentation Quality Instrument) is the most widely used validated rubric. It evaluates 9 dimensions on a 5-point Likert scale: Accurate, Thorough, Useful, Organized, Comprehensible, Succinct, Synthesized, Internally Consistent, and Up-to-date. The instrument demonstrated excellent internal consistency (ICC 0.867).[[3]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12586549/)

**PDSQI-9** (Provider Documentation Summarization Quality Instrument) is an LLM-centric adaptation of PDQI-9, developed via semi-Delphi consensus. It adds "Cited" (source attribution) and "Stigmatizing" dimensions while replacing "Up-to-date" with hallucination-specific evaluation. It was validated with 200 multi-document EHR summaries scored by 7 physician evaluators.[[10]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12589481/)

**Q-Note** is another validated instrument (Burke et al., 2014) with more granular criteria, but PDQI-9 is preferred for its flexibility across clinical settings.

The KidsAbility pediatric study used a simplified 5-criterion rubric (Clear, Complete, Concise, Relevant, Organized) on a 3-point scale, finding that AI-generated notes (with human editing) achieved quality comparable to human-authored notes (mean 13.12 vs. 11.49 out of 15, though ANOVA p = 0.45 — not statistically significant).[[4]](https://rocketdiscoverycentre.ca/wp-content/uploads/2025/02/SOAP_Note_Quality_Assessment__arXiv_-1.pdf)

---

## 4. Scalable Evaluation Pipelines

<aside>
📊

**At a Glance**

| Pipeline Approach | ICC w/ Humans | Cost/Eval | Time/Eval | Key Finding |
| --- | --- | --- | --- | --- |
| GPT-o3-mini 5-shot | 0.818 | $0.05 | 22 sec | Best single-LLM judge |
| Multi-agent (o3-mini orchestrator) | 0.768 | $0.16 | 69 sec | Marginal gain over single LLM |
| Feedback-derived checklists | Significant (p ≤ 0.05) | Low | Low | Outperforms zero-shot checklists |
</aside>

### 4.1 LLM-as-a-Judge

The PDSQI-9 study (Croxford et al., 2025) represents the most rigorous evaluation of LLM-as-a-Judge for clinical summarization to date. Key findings:[[10]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12589481/)

**GPT-o3-mini with 5-shot prompting** achieved the best performance — ICC of 0.818 (95% CI 0.772–0.854) with a median score difference of 0 from human evaluators. This represents a **96% reduction in evaluation time** (22 sec vs. 600 sec) and a **99.9% reduction in cost** ($0.05 vs. $50 per evaluation).

**Reasoning models outperformed non-reasoning models** across the board, particularly on attributes requiring advanced reasoning and domain expertise. GPT-o3-mini (zero-shot) already achieved ICC 0.803, and few-shot examples provided modest additional gains.

**Fine-tuning dramatically improved small models.** Llama 3.1 8B went from ICC 0.332 (zero-shot) to 0.560 after SFT + DPO — making even small open-source models viable for on-premise deployment in HIPAA-compliant environments.

**Multi-agent frameworks offered marginal gains** (ICC 0.768) over the best single-model approach, at 3× the cost and 3× the latency. The added complexity is hard to justify unless specific evaluation attributes require diverse perspectives.

**Critical limitation:** Neither automated metrics nor LLM judges reliably detect hallucinations. The PMC pilot study concluded that "completely automating the evaluation of medical summaries remains challenging" — hallucination detection specifically requires dedicated methods beyond general quality scoring.[[1]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12786185/)

### 4.2 Checklist-Based Evaluation

The "From Feedback to Checklists" paper (Zhou et al., EMNLP 2025 Industry) from Abridge introduces a compelling approach: **distilling real clinician feedback into structured binary checklists** that can be scored by LLM evaluators.[[11]](https://arxiv.org/html/2507.17717v1)

The pipeline:

1. **Collect** free-form clinician feedback from a deployed AI scribe system (~22K encounters)
2. **Generate** candidate checklist questions by prompting an LLM with batched feedback
3. **Refine** through deduplication, applicability tagging, LLM enforceability testing, and coverage/diversity optimization
4. **Score** notes by having an LLM answer each yes/no question; the checklist score = proportion of "Yes" answers

The resulting 25-question checklist for the Assessment & Plan section demonstrated:

- **Better predictive power** for human ratings (accuracy 0.70 vs. 0.62 for baseline)
- **Significant correlation** with expert preferences (p ≤ 0.05), unlike the baseline checklist
- **Robustness** to quality-degrading perturbations (perturbation Δ of 2.30 vs. 0.91 for baseline)
- Sensitivity to missing information, poor organization, redundancy, and hallucinations

This approach is particularly powerful because it grounds evaluation in **what clinicians actually care about**, rather than abstract quality dimensions. Example checklist questions include:

- *"Is there an accurate and specific patient management plan for each condition mentioned?"*
- *"Does the A&P include only relevant clinical reasoning, without repeating HPI information?"*
- *"Is the A&P free of incorrectly attributing patient statements to physician recommendations?"*

### 4.3 Reference-Free Evaluation

Reference-free methods evaluate note quality without gold-standard comparisons — critical for production deployment where reference notes don't exist. Approaches include:

- **Transcript-grounded factuality checking** — verifying each note sentence is evidenced in the source transcript (the CREOLA approach)[[2]](https://www.nature.com/articles/s41746-025-01670-7)
- **Internal consistency checking** — detecting contradictions within the note
- **NLI-based hallucination detection** — using Natural Language Inference models to check if note claims are entailed by the transcript
- **Quality estimation models** — trained on human quality scores to predict quality from the note alone

Kadkhodaieelyaderani et al. (Interspeech 2024) described a "simple yet robust approach to performing reference-free estimation of the quality of automatically-generated clinical notes derived from doctor-patient conversations."

---

## 5. Failure Modes & Edge Cases

<aside>
⚠️

**At a Glance**

| Failure Mode | Frequency | Severity | SOAP Section Most Affected |
| --- | --- | --- | --- |
| Negation errors | 30% of hallucinations | Very High | Plan, Assessment |
| Section misplacement | Common | Moderate | S↔O, A↔P boundaries |
| Medication errors | "Most significant" | Very High | Plan |
| Demographic bias | Under-studied | High | Transcription layer |
</aside>

### 5.1 Hallucination Taxonomy

The CREOLA framework provides the most detailed clinical hallucination taxonomy to date:[[2]](https://www.nature.com/articles/s41746-025-01670-7)

- **Fabrication (43%):** Information generated without any basis in the transcript. Most common in the Plan section, where the model invents follow-up instructions or medication changes.
- **Negation (30%):** The model contradicts what was said. These are the most clinically dangerous — a note saying "patient denies allergies" when the patient reported an allergy can cause direct harm.
- **Contextual (17%):** Mixing information between unrelated topics or problems within the same encounter.
- **Causality (10%):** Speculating about cause-effect relationships not discussed in the encounter.

### 5.2 Omission Patterns

Omissions are more frequent than hallucinations but less often clinically major. Major omissions were most common in:

- **Current issues (55%)** — missing details about the presenting problem
- **PMFS (35%)** — past medical history, medications, family/social history
- **Information and Plan (10%)** — missing discussed management steps

### 5.3 Medication & Treatment Errors

The patient safety study from UCSF/Stanford (Dai et al., 2025) analyzing real-world AI scribe feedback found that medication and treatment errors were the **most significant patient safety risk** — wrong medication names, incorrect dosages, fabricated prescriptions, or omitted critical medications.[[12]](https://arxiv.org/abs/2512.04118) A Stanford/Harvard study found AI generated "severe" errors in 22% of medical cases.

### 5.4 Demographic Bias in Transcription

AI scribes rely on speech recognition, which introduces a pre-documentation failure mode: transcription accuracy varies by accent, dialect, and language proficiency. Researchers at Columbia have warned that "patients with non-standard accents, limited English proficiency, or those from marginalized communities may receive inadequate documentation." This is a systemic issue that compounds documentation errors — an eval system should test for performance disparities across demographic groups.

### 5.5 The "Semantic Equivalence" Problem

AI-generated notes frequently use different phrasing than a human would, while capturing the same clinical meaning. This is a fundamental challenge for evaluation: traditional metrics penalize valid paraphrases. For example, "patient reports shortness of breath" and "dyspnea on exertion per patient" are semantically equivalent but lexically different.

Transformer-based clinical STS (Semantic Textual Similarity) models — particularly ClinicalBERT and BioBERT — better capture this equivalence than general-purpose models. The ClinicalSTS shared task (n2c2/OHNLP) used 1,642 pairs of de-identified clinical text snippets annotated on a 0–5 scale, demonstrating that domain-specific fine-tuning significantly improves semantic similarity measurement.

---

## 6. Designing an Eval System: Architecture Recommendations

### 6.1 Tiered Evaluation Architecture

Based on the research, the optimal approach is a **tiered evaluation pipeline** that balances cost, speed, and clinical validity:

**Tier 1 — Automated Screening (every note, real-time)**

- Entity-level extraction and comparison (medications, diagnoses, procedures)
- Section completeness checks (are all SOAP sections populated?)
- Redundancy detection (duplicate sentences or near-duplicates)
- Basic structural validation (information in correct sections)

**Tier 2 — LLM-as-a-Judge (every note, near-real-time)**

- Checklist-based evaluation using feedback-derived questions
- PDSQI-9-style quality scoring across key dimensions
- Hallucination flagging via transcript-grounded NLI
- Flag notes scoring below quality thresholds for Tier 3 review

**Tier 3 — Human Expert Review (flagged notes + random sample)**

- Full PDQI-9/PDSQI-9 rubric evaluation
- Clinical safety assessment (major/minor error classification)
- Feedback collection to improve Tier 2 checklists
- Regular calibration between human reviewers

### 6.2 Key Design Decisions

| Decision | Recommendation | Rationale |
| --- | --- | --- |
| **Which LLM for judging?** | GPT-o3-mini (5-shot) or equivalent reasoning model | Best ICC (0.818), low cost ($0.05/eval), fast (22 sec) |
| **Section-specific or whole-note?** | Section-specific, especially for A&P | Error patterns differ by section; A&P is highest-risk |
| **Hallucination detection approach?** | NLI-based + entity cross-reference + dedicated detector | General quality metrics miss hallucinations; need dedicated layer |

### 6.3 Iterative Improvement Loop

The CREOLA study demonstrated that **iterative prompt/workflow refinement** guided by structured evaluation can dramatically reduce errors:[[2]](https://www.nature.com/articles/s41746-025-01670-7)

- Major hallucinations reduced by 75% (4 → 1) through prompt engineering
- Major omissions reduced by 58% (24 → 10) with style guidance and "unknown" option
- Function-call experiments eliminated major omissions entirely (61 → 0) over 4 iterations

The eval system should be designed as a **feedback loop**: evaluation results feed back into prompt engineering, fine-tuning, and checklist refinement. The checklist pipeline from Zhou et al. explicitly supports this — as new clinician feedback arrives, the checklist can be regenerated to cover emerging failure modes.

---

## 7. Open Questions

- [ ]  **Hallucination detection at scale** — Current metrics (including LLM judges) are unreliable for hallucination detection. Dedicated fact-verification models for clinical text are needed.
- [ ]  **Cross-specialty generalization** — Most evaluation work focuses on primary care. Specialty-specific rubrics and checklists may be necessary for specialized documentation.
- [ ]  **Longitudinal consistency** — How should eval systems handle notes that reference prior encounters? Multi-document consistency checking is largely unexplored.
- [ ]  **Calibrating "acceptable" error rates** — Human notes contain ~1 error and ~4 omissions per note. What threshold should AI systems meet?
- [ ]  **Real-world outcome correlation** — Does higher eval scores actually translate to better clinical outcomes? The link between documentation quality and patient safety is assumed but under-measured.
- [ ]  **Dynamic checklists** — How to continuously update evaluation criteria as AI systems improve and new failure modes emerge?

---

## References

1. [Evaluating Medical Text Summaries Using Automatic Evaluation Metrics and LLM-as-a-Judge Approach](https://pmc.ncbi.nlm.nih.gov/articles/PMC12786185/) — Pilot study on metrics vs. expert correlation. June 1, 2025 ⭐
2. [A Framework to Assess Clinical Safety and Hallucination Rates of LLMs for Medical Text Summarisation](https://www.nature.com/articles/s41746-025-01670-7) — CREOLA framework; largest manual evaluation of LLM clinical notes (12,999 sentences). Asgari et al., npj Digital Medicine. May 13, 2025 ⭐
3. [Assessing the Quality of AI-Generated Clinical Notes: Validated Evaluation of an LLM Ambient Scribe](https://pmc.ncbi.nlm.nih.gov/articles/PMC12586549/) — PDQI-9 applied to 97 encounters across 5 specialties. Palm et al., Frontiers in AI. October 22, 2025 ⭐
4. [Assessment of AI-Generated Pediatric Rehabilitation SOAP-Note Quality](https://rocketdiscoverycentre.ca/wp-content/uploads/2025/02/SOAP_Note_Quality_Assessment__arXiv_-1.pdf) — 432-note blind evaluation; custom rubric. Amenyo et al., arXiv. January 30, 2025
5. [Towards Scalable SOAP Note Generation: A Weakly Supervised Multimodal Framework](https://arxiv.org/html/2506.10328v1) — ClinicalBERT F1, METEOR, CHRF++ for SOAP eval. arXiv. June 12, 2025
6. [BERTScore in AI: Enhancing Text Evaluation](https://galileo.ai/blog/bert-score-explained-guide) — Domain-dependent limitations of BERTScore. Galileo AI. Accessed March 16, 2026
7. [Clinical Entity Augmented Retrieval for Clinical Information Extraction](https://pmc.ncbi.nlm.nih.gov/articles/PMC11743751/) — GPT-4 achieves F1 0.97 on clinical extraction. PMC. January 1, 2025
8. [Evaluating LLMs for NER in Ophthalmology Clinical Notes](https://pmc.ncbi.nlm.nih.gov/articles/PMC12099357/) — BioBERT NER F1 benchmarks. PMC. June 1, 2025
9. [Exploring NER Potential in Clinical Decision Support](https://pmc.ncbi.nlm.nih.gov/articles/PMC12449662/) — Spark NLP clinical NER precision 0.989. PMC. July 1, 2025
10. [Evaluating Clinical AI Summaries with LLMs as Judges](https://pmc.ncbi.nlm.nih.gov/articles/PMC12589481/) — PDSQI-9 + LLM-as-a-Judge framework; GPT-o3-mini ICC 0.818. Croxford et al., npj Digital Medicine. November 5, 2025 ⭐
11. [From Feedback to Checklists: Grounded Evaluation of AI-Generated Clinical Notes](https://arxiv.org/html/2507.17717v1) — Feedback-derived checklist pipeline from Abridge; 22K encounters. Zhou et al., EMNLP 2025 Industry. July 23, 2025 ⭐
12. [Patient Safety Risks from AI Scribes: Signals from End-User Feedback](https://arxiv.org/abs/2512.04118) — Real-world safety analysis from UCSF. Dai et al., arXiv. December 1, 2025
13. [Expert Evaluation of LLMs for Clinical Dialogue Summarization](https://pmc.ncbi.nlm.nih.gov/articles/PMC11707028/) — ROUGE vs. human evaluation comparison. PMC. January 1, 2025
14. [2025 Expert Consensus on Retrospective Evaluation of LLM Applications in Clinical Scenarios](https://www.sciencedirect.com/science/article/pii/S2667102625001044) — Standardized evaluation framework for medical LLMs. ScienceDirect. January 1, 2025 **(Emerging)**
15. [Clinical SOAP Notes Completeness Checking Using Machine Learning](https://jmai.amegroups.org/article/view/10223/html) — ML for section-level completeness. JMAI. January 1, 2025
16. [Fact-Controlled Diagnosis of Hallucinations in Medical Text Summarization](https://arxiv.org/html/2506.00448v1) — Leave-N-Out and Natural Hallucination datasets. arXiv. June 1, 2025 **(Emerging)**
17. [Scaling Note Quality Assessment with AI and GPT-4](https://catalyst.nejm.org/doi/full/10.1056/CAT.23.0283) — NYU Langone system-wide note quality assessment. NEJM Catalyst. April 17, 2024 ⭐
18. [Towards an Automated SOAP Note: Classifying Utterances from Medical Conversations](http://proceedings.mlr.press/v126/schloss20a/schloss20a.pdf) — Utterance-level SOAP classification baseline. PMLR. January 1, 2020