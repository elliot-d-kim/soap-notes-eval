"""Shared pytest fixtures for SOAP note evaluation suite tests."""

from __future__ import annotations

import pytest

from src.data.models import DegradedSOAPNote, SOAPNote, SOAPSections


# ---------------------------------------------------------------------------
# Known-good SOAP note
# ---------------------------------------------------------------------------

GOOD_NOTE_TEXT = """\
Subjective:
Patient is a 45-year-old female presenting with a 3-day history of productive cough,
fever (38.5°C), and mild shortness of breath. She reports no prior lung conditions.
Currently taking lisinopril 10mg daily for hypertension.

Objective:
Temp 38.5°C, HR 92 bpm, BP 128/82 mmHg, O2 sat 97% on room air.
Lung auscultation reveals crackles in the right lower lobe.
CXR shows right lower lobe infiltrate.

Assessment:
1. Community-acquired pneumonia, right lower lobe
2. Hypertension, well-controlled

Plan:
1. Azithromycin 500mg PO x1, then 250mg daily x 4 days
2. Amoxicillin-clavulanate 875mg BID x 5 days
3. Follow up in 5-7 days or sooner if worsening
4. Return precautions: worsening dyspnea, high fever, hemoptysis
"""

GOOD_TRANSCRIPT = """\
Doctor: Good morning. What brings you in today?
Patient: I've had this cough for 3 days now and I feel really hot and short of breath.
Doctor: Any chest pain? Bringing up any mucus?
Patient: Yes, greenish mucus. No chest pain.
Doctor: Any prior lung problems or recent travel?
Patient: No. I do take lisinopril for my blood pressure.
Doctor: Let me listen to your lungs. [examines] I hear crackles on the right side.
Your temperature is 38.5. I'd like to get a chest X-ray.
Patient: Okay.
Doctor: The X-ray shows an infection in the right lower lobe. You have pneumonia.
I'll prescribe antibiotics — azithromycin and amoxicillin-clavulanate.
Follow up in a week or sooner if you feel worse.
"""


@pytest.fixture
def good_note() -> SOAPNote:
    """A complete, well-formed SOAP note that should pass all checks."""
    from src.data.loaders import parse_soap_sections

    return SOAPNote(
        note_id="test_good_001",
        source_dataset="test",
        transcript=GOOD_TRANSCRIPT,
        note_text=GOOD_NOTE_TEXT,
        sections=parse_soap_sections(GOOD_NOTE_TEXT),
    )


# ---------------------------------------------------------------------------
# Degraded fixtures — one per failure type
# ---------------------------------------------------------------------------


@pytest.fixture
def missing_section_note() -> DegradedSOAPNote:
    """Note with the Assessment section entirely removed."""
    from src.data.loaders import parse_soap_sections

    note_text = """\
Subjective:
Patient is a 45-year-old female presenting with a 3-day history of productive cough,
fever (38.5°C), and mild shortness of breath.

Objective:
Temp 38.5°C, HR 92 bpm, BP 128/82 mmHg, O2 sat 97% on room air.
Lung auscultation reveals crackles in the right lower lobe.

Plan:
1. Azithromycin 500mg PO x1, then 250mg daily x 4 days
2. Amoxicillin-clavulanate 875mg BID x 5 days
"""
    return DegradedSOAPNote(
        note_id="test_missing_section_001",
        source_dataset="test",
        transcript=GOOD_TRANSCRIPT,
        note_text=note_text,
        sections=parse_soap_sections(note_text),
        degradation_types=["missing_section"],
        original_note_id="test_good_001",
        degradation_details={"removed_section": "assessment"},
    )


@pytest.fixture
def redundancy_bloat_note() -> DegradedSOAPNote:
    """Note with extensive duplicate sentences and filler in the Plan."""
    from src.data.loaders import parse_soap_sections

    note_text = """\
Subjective:
Patient is a 45-year-old female presenting with a 3-day history of productive cough,
fever (38.5°C), and mild shortness of breath.

Objective:
Temp 38.5°C, HR 92 bpm, BP 128/82 mmHg, O2 sat 97% on room air.

Assessment:
1. Community-acquired pneumonia, right lower lobe
2. Hypertension, well-controlled

Plan:
1. Azithromycin 500mg PO x1, then 250mg daily x 4 days
2. Amoxicillin-clavulanate 875mg BID x 5 days
3. Follow up in 5-7 days or sooner if worsening
1. Azithromycin 500mg PO x1, then 250mg daily x 4 days
2. Amoxicillin-clavulanate 875mg BID x 5 days
3. Follow up in 5-7 days or sooner if worsening
Additionally, the patient was counseled extensively regarding the above-mentioned items.
The patient verbalized understanding and agreement with the plan as discussed.
Additionally, the patient was counseled extensively regarding the above-mentioned items.
The patient verbalized understanding and agreement with the plan as discussed.
"""
    return DegradedSOAPNote(
        note_id="test_redundancy_001",
        source_dataset="test",
        transcript=GOOD_TRANSCRIPT,
        note_text=note_text,
        sections=parse_soap_sections(note_text),
        degradation_types=["redundancy_bloat"],
        original_note_id="test_good_001",
        degradation_details={"duplicated_section": "plan"},
    )


@pytest.fixture
def structural_errors_note() -> DegradedSOAPNote:
    """Note with Plan appearing before Assessment (wrong order)."""
    from src.data.loaders import parse_soap_sections

    note_text = """\
Subjective:
Patient is a 45-year-old female presenting with a 3-day history of productive cough,
fever (38.5°C), and mild shortness of breath.

Objective:
Temp 38.5°C, HR 92 bpm, BP 128/82 mmHg, O2 sat 97% on room air.

Plan:
1. Azithromycin 500mg PO x1, then 250mg daily x 4 days
2. Amoxicillin-clavulanate 875mg BID x 5 days

Assessment:
1. Community-acquired pneumonia, right lower lobe
2. Hypertension, well-controlled
"""
    return DegradedSOAPNote(
        note_id="test_structural_001",
        source_dataset="test",
        transcript=GOOD_TRANSCRIPT,
        note_text=note_text,
        sections=parse_soap_sections(note_text),
        degradation_types=["structural_errors"],
        original_note_id="test_good_001",
        degradation_details={"swap": "plan_before_assessment"},
    )


@pytest.fixture
def empty_section_note() -> SOAPNote:
    """Edge case: note with empty Objective section."""
    from src.data.loaders import parse_soap_sections

    note_text = """\
Subjective:
Patient is a 45-year-old female presenting with a 3-day history of cough.

Objective:

Assessment:
1. Community-acquired pneumonia

Plan:
1. Azithromycin 500mg daily x 5 days
"""
    return SOAPNote(
        note_id="test_empty_section_001",
        source_dataset="test",
        transcript=GOOD_TRANSCRIPT,
        note_text=note_text,
        sections=parse_soap_sections(note_text),
    )


@pytest.fixture
def missing_transcript_note() -> SOAPNote:
    """Edge case: note without a source transcript."""
    from src.data.loaders import parse_soap_sections

    return SOAPNote(
        note_id="test_no_transcript_001",
        source_dataset="test",
        transcript=None,
        note_text=GOOD_NOTE_TEXT,
        sections=parse_soap_sections(GOOD_NOTE_TEXT),
    )


@pytest.fixture
def malformed_soap_note() -> SOAPNote:
    """Edge case: note with no recognisable SOAP section headers."""
    note_text = "The patient came in today. They were feeling unwell. We prescribed antibiotics."
    return SOAPNote(
        note_id="test_malformed_001",
        source_dataset="test",
        transcript=GOOD_TRANSCRIPT,
        note_text=note_text,
        sections=SOAPSections(subjective=note_text),
    )
