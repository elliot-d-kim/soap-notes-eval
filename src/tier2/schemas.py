"""Pydantic models for Tier 2 LLM-as-a-Judge verdict structures.

Every LLM call in Tier 2 is forced to return a structured verdict that
conforms to these schemas. Binary pass/fail per criterion (not numeric scales)
— consistent with the literature showing binary judgments are more reliable
and actionable than Likert scales.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Verdict(str, Enum):
    """Binary verdict for a single evaluation criterion."""

    PASS = "pass"
    FAIL = "fail"


class CriterionVerdict(BaseModel):
    """Verdict for a single PDQI-9-adapted evaluation criterion.

    Chain-of-thought is required: the rationale field must be populated
    BEFORE the verdict is recorded, ensuring the judge articulates its
    reasoning. This is enforced at the model level via validator.
    """

    criterion: str = Field(description="Name of the criterion being evaluated.")
    rationale: str = Field(
        description=(
            "Evaluation reasoning that supports the verdict. "
            "Must be populated before verdict is set (chain-of-thought enforcement)."
        )
    )
    verdict: Verdict = Field(description="Binary pass/fail verdict for this criterion.")
    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Specific text excerpts from the note or transcript that support the verdict. "
            "Required for FAIL verdicts to enable human auditing."
        ),
    )

    @model_validator(mode="after")
    def rationale_before_verdict(self) -> "CriterionVerdict":
        """Enforce that rationale is substantive (>10 chars) — not a placeholder."""
        if len(self.rationale.strip()) < 10:
            raise ValueError(
                f"Criterion '{self.criterion}': rationale must be substantive "
                "(≥10 characters). Chain-of-thought reasoning is required before verdict."
            )
        return self


class HallucinationFlag(BaseModel):
    """A single entity or claim flagged as potentially hallucinated."""

    entity: str = Field(description="The hallucinated text span.")
    claim_in_note: str = Field(description="The sentence in the note containing the entity.")
    grounding_verdict: Verdict = Field(
        description="FAIL = entity not found in transcript; PASS = entity is grounded."
    )
    explanation: str = Field(description="Why this entity was flagged.")


class Tier2Verdict(BaseModel):
    """Complete Tier 2 LLM-as-a-Judge verdict for a single SOAP note.

    PDQI-9-adapted criteria (binary pass/fail):
    1. accuracy         — factual fidelity to transcript
    2. completeness     — key findings not omitted
    3. succinctness     — no unnecessary verbosity/bloat
    4. organization     — clear SOAP structure followed
    5. consistency      — no contradictions between sections
    6. appropriateness  — clinically appropriate language and decisions
    """

    note_id: str = Field(description="Matches the SOAPNote.note_id being judged.")
    model_used: str = Field(description="LiteLLM model identifier used for this evaluation.")
    prompt_version: str = Field(description="Version string from prompts/manifest.json.")
    timestamp: str = Field(description="ISO 8601 timestamp of the evaluation.")

    # Per-criterion verdicts (must include all 6 PDQI-9 criteria)
    criteria: list[CriterionVerdict] = Field(
        min_length=1,
        description="One CriterionVerdict per PDQI-9-adapted evaluation criterion.",
    )

    # Hallucination analysis
    hallucination_flags: list[HallucinationFlag] = Field(
        default_factory=list,
        description="Entities or claims in the note not grounded in the transcript.",
    )

    # Overall recommendation
    overall_verdict: Verdict = Field(
        description=(
            "Aggregate verdict. FAIL if any criterion fails or hallucinations detected. "
            "PASS only if all criteria pass and no hallucinations are flagged."
        )
    )
    overall_rationale: str = Field(
        description="Summary of why the note passed or failed overall."
    )
    escalate_to_tier3: bool = Field(
        description="True if this note should be routed to human expert review (Tier 3).",
    )

    @model_validator(mode="after")
    def overall_verdict_consistent(self) -> "Tier2Verdict":
        """Overall verdict must be FAIL if any criterion fails or hallucinations exist."""
        any_criterion_failed = any(c.verdict == Verdict.FAIL for c in self.criteria)
        has_hallucinations = any(
            h.grounding_verdict == Verdict.FAIL for h in self.hallucination_flags
        )
        if (any_criterion_failed or has_hallucinations) and self.overall_verdict == Verdict.PASS:
            raise ValueError(
                "overall_verdict cannot be PASS when criterion failures or hallucinations exist."
            )
        return self

    def criterion_by_name(self, name: str) -> Optional[CriterionVerdict]:
        """Retrieve a specific criterion verdict by name."""
        for c in self.criteria:
            if c.criterion.lower() == name.lower():
                return c
        return None

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")
