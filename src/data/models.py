"""Pydantic models for SOAP note data structures.

SOAP = Subjective, Objective, Assessment, Plan — the canonical clinical note format.
These models are used as I/O contracts throughout the pipeline.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SOAPSections(BaseModel):
    """The four sections of a SOAP clinical note.

    All sections are optional at the model level so that partially-formed
    notes (a key failure mode) can be represented and detected by Tier 1.
    """

    subjective: Optional[str] = Field(
        default=None,
        description=(
            "Patient's reported symptoms, history, and chief complaint. "
            "Drawn from patient statements in the transcript."
        ),
    )
    objective: Optional[str] = Field(
        default=None,
        description=(
            "Measurable findings: vitals, exam results, lab values, imaging. "
            "Should reflect only directly observed/measured data."
        ),
    )
    assessment: Optional[str] = Field(
        default=None,
        description=(
            "Clinical interpretation: diagnoses, differential diagnoses, "
            "and clinician's reasoning about the findings."
        ),
    )
    plan: Optional[str] = Field(
        default=None,
        description=(
            "Treatment plan: medications, referrals, follow-ups, patient education. "
            "Must be grounded in the assessment."
        ),
    )


class SOAPNote(BaseModel):
    """A complete SOAP note with its source transcript and metadata.

    This is the primary input unit for the evaluation pipeline.
    Both transcript and note are required for transcript-grounded evaluation;
    transcript may be None for reference-free-only evaluation modes.
    """

    note_id: str = Field(description="Unique identifier for this note.")
    source_dataset: str = Field(
        description="Dataset this sample came from (e.g., 'adesouza1', 'ACI-Bench', 'omi-health')."
    )
    transcript: Optional[str] = Field(
        default=None,
        description="Raw doctor-patient dialogue that the note was generated from.",
    )
    note_text: str = Field(description="Full text of the generated SOAP note.")
    sections: SOAPSections = Field(
        description="Parsed SOAP sections extracted from note_text."
    )
    ground_truth_note: Optional[str] = Field(
        default=None,
        description="Clinician-edited gold standard note, if available (reference-based eval only).",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Source-specific fields (row index, split, original field names, etc.).",
    )


class DegradedSOAPNote(SOAPNote):
    """A synthetically degraded SOAP note with ground-truth failure labels.

    Used as test fixtures: the pipeline must detect the labeled failure types.
    Multiple failure types can be present in a single note (e.g., both
    missing_section and hallucinated_entities).
    """

    degradation_types: list[str] = Field(
        description=(
            "List of failure labels applied. Valid values: "
            "'missing_section', 'omitted_findings', 'redundancy_bloat', "
            "'structural_errors', 'hallucinated_entities', 'internal_contradiction'."
        )
    )
    original_note_id: str = Field(
        description="note_id of the clean source note this was derived from."
    )
    degradation_details: dict = Field(
        default_factory=dict,
        description="Structured record of what was changed and how (for test assertions).",
    )
