# DeepScribe AI Coding Assessment

At DeepScribe, we build AI products that generate clinical documentation for real patient encounters. These systems must reliably reflect what was said, capture critical information, and avoid hallucination. This assignment is your opportunity to show how you'd approach these challenges.

You have two options to choose from: 1) Evals Suite, 2) Choose your own adventure.

---

## Option 1: Evals Suite

**Context:** You’re given 100 SOAP notes, each paired with the source transcript and a ground-truth clinician-edited note. Your task is to build an evaluations suite that can evaluate notes and flag issues using scalable, statistically sound methods.

### Core Requirements

Your framework should identify problems such as:

- **Missing critical findings** - facts from the transcript that were omitted from the generated note.
- **Hallucinated or unsupported facts** - information in the note that isn’t grounded in the transcript.
- **Clinical accuracy issues** - medically incorrect or misleading statements

### Goals

At DeepScribe, we need to:

1. **Move fast** - We need to be able to quickly measure and incorporate the latest models and PR changes, without waiting days/weeks.
2. **Understand production quality** - It’s important for us to measure our note quality in the wild, so we can quickly detect any regressions or areas where notes may have lower quality. 

### Evaluation Approaches

Consider the tradeoffs between different evaluation approaches:

1. **Reference-Based vs Non Reference-Based**: Some evals require ground truth datasets which can be expensive to curate, whereas other evals can run in an unsupervised fashion which are easier to scale.
2. **LLM-as-a-judge vs Deterministic Evals** - LLM-as-a-judge evals are very powerful, but they are also slower and costlier to run compared to deterministic metrics.

There are no wrong answers here - we’d encourage you to be creative and think outside the box. Be sure that the approach you take is focusing on the [Goals](https://www.notion.so/Goals-32697c7359838060ab2af1ea169807be?pvs=21) outlined above. Also consider how you can measure the quality of the eval itself - e.g. how do you know if the eval is working?

### Deliverable

You need to have working code - implement a minimal eval suite and provide a write-up explaining your approach and justify how your metric(s) could be used to for goals 1 and 2. For bonus points (not required), you can add a dashboard summarizing your findings across all the notes.

See [Datasets](https://www.notion.so/Datasets-32697c73598380479da0c2c46eb6b9c5?pvs=21) below - you can use these as a starting point or create your own synthetic dataset.

---

## Option 2: Choose Your Own Adventure

Already built something related to applied LLMs? Have an idea for improving AI-generated clinical output that doesn’t fit the above? Go for it!

Your project should:

- Showcase your expertise with applied LLMs
- Be scoped so that you can make meaningful progress in no more than 3-5 hours max
- Be your own work, not from a team project or proprietary codebase.

---

## Datasets

Here are some datasets that you can use for SOAP notes & transcripts, there are many more to be found on the internet too.

| Dataset | Link |
| --- | --- |
| **adesouza1/soap_notes** | https://huggingface.co/datasets/adesouza1/soap_notes |
| **MTS-Dialog** | https://github.com/abachaa/MTS-Dialog |
| **Omi-Health SOAP Dataset** | https://huggingface.co/datasets/omi-health/medical-dialogue-to-soap-summary |

---

## Deliverables

Please submit a GitHub repo (or equivalent) that includes:

- Your code and data processing scripts
- A README with clear setup instructions and a description of your approach. The README should contain a short write-up comparing different approaches and tradeoffs you considered. **In the README, please highlight at least one area of the project that demonstrates your craftsmanship and that you paid particularly close attention to.**
- Sample output (JSON reports, charts, dashboards, etc.)

We recommend using Python (preferred) or Typescript, but let us know if you’d prefer to use something else. Feel free to use LLM APIs (OpenAI, Claude, open-source). You are also free to leverage AI coding tools, as long as you understand everything that’s being generated and are prepared to explain it in an interview.

---

## What We’re Evaluating

| Skill | What We're Looking For |
| --- | --- |
| **LLM Expertise** | Sophisticated use of prompting, evaluation, retrieval, or fine-tuning |
| **ML Foundations** | Deep understanding of ML fundamentals |
| **Software Craft** | Clarity, reproducibility, robustness |
| **Communication** | Clear problem framing, thoughtful tradeoffs, readable docs |
| **Execution** | End-to-end thinking, polish, ability to ship something usable |

**Your craftsmanship:** We know it's possible to get a baseline solution from an LLM, but we're interested in *your* unique contribution. In your README, please highlight one to three areas of the project you paid close attention to. We want to see what you are proud of—whether it's a refined UX, a robust backend design, optimized prompt engineering, or another detail you honed.