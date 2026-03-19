# Strategy

Strategic rationale for the DeepScribe SOAP Note Evaluation Suite. Referenced by CLAUDE.md for README generation. This file is not operational context for the coding agent — it explains *why* the system is designed the way it is.

## Evaluation-first signals engineering maturity

DeepScribe's core product is AI-generated clinical notes. Demonstrating deep fluency in how to evaluate that output — not just generate it — directly addresses the highest-leverage problem the team faces. Most candidates will build a generator. This builds the system that tells whether the generator is any good.

## The tiered architecture mirrors real production systems

The Tier 1 → 2 → 3 escalation pattern (cheap/fast screening → expensive/thorough judgment → human-in-the-loop calibration) is how mature ML teams actually operate. It shows awareness of cost-quality tradeoffs at scale, not just "call GPT-4 on everything."

## Meta-evaluation is the differentiator

Including a calibration module that measures judge-vs-human agreement (Cohen's kappa, targeted >90% binary agreement) demonstrates understanding of a problem most candidates do not even consider: how do you know your evaluator is trustworthy?

## Domain expert UX shows product thinking

The Tier 3 review interface — three-column layout, CRUD on annotations, reasoning capture — shows awareness that the bottleneck in clinical AI is not compute but expert time. Making evaluation frictionless for non-technical clinicians is where the real business value compounds.

## Literature-grounded decisions build trust

Every architectural choice maps to a specific finding from the research: binary scales from the LLM-as-a-judge literature, PDQI-9 from clinical quality research, bias mitigations from meta-evaluation studies. This is not a vibe-coded prototype — it is a researched system.