"""Tier 1 automated screening tests.

Test strategy:
1. Known-good notes pass all checks.
2. Each degradation type triggers its expected failure.
3. Edge cases (empty sections, malformed SOAP, missing transcript) are handled.
4. Entity extraction returns expected entity types for clinical text.
"""

from __future__ import annotations

import pytest

from src.tier1.entities import ExtractedEntities, extract_entities
from src.tier1.pipeline import run_tier1
from src.tier1.structure import validate_structure


# ---------------------------------------------------------------------------
# Known-good note — should pass all checks
# ---------------------------------------------------------------------------


def test_good_note_passes_all_structure_checks(good_note):
    """A well-formed SOAP note should pass every structural check."""
    report = validate_structure(good_note)
    assert report.passed, (
        f"Expected all checks to pass, but these failed:\n"
        + "\n".join(f"  - {c.name}: {c.details}" for c in report.failed_checks)
    )


def test_good_note_tier1_passes(good_note):
    """Full Tier 1 pipeline run on a good note should produce a passing report."""
    report = run_tier1(good_note)
    assert report.passed
    assert report.failure_types == []


def test_good_note_entities_extracted(good_note):
    """Entity extraction on a known clinical note should find medications and diagnoses."""
    entities = extract_entities(good_note.note_text)
    all_ents = [e.lower() for e in entities.all_entities()]

    # At minimum we expect some clinical entities
    assert len(entities.all_entities()) >= 1, "Expected at least one clinical entity"


def test_good_note_per_section_entities(good_note):
    """Entity extraction should produce non-empty results for at least the plan section."""
    report = run_tier1(good_note)
    plan_entities = report.entities_per_section.get("plan")
    assert plan_entities is not None
    assert isinstance(plan_entities, ExtractedEntities)


# ---------------------------------------------------------------------------
# Missing section — should detect missing_section failure
# ---------------------------------------------------------------------------


def test_missing_section_fails_presence_check(missing_section_note):
    """A note with Assessment removed should fail the section_present:assessment check."""
    report = validate_structure(missing_section_note)
    assert not report.passed

    failed_names = [c.name for c in report.failed_checks]
    assert "section_present:assessment" in failed_names, (
        f"Expected 'section_present:assessment' in failed checks, got: {failed_names}"
    )


def test_missing_section_tier1_failure_type(missing_section_note):
    """Tier 1 pipeline should report 'missing_section' failure type."""
    report = run_tier1(missing_section_note)
    assert not report.passed
    assert "missing_section" in report.failure_types


# ---------------------------------------------------------------------------
# Redundancy bloat — should detect redundancy_bloat failure
# ---------------------------------------------------------------------------


def test_redundancy_bloat_fails_check(redundancy_bloat_note):
    """A note with heavily duplicated content should fail the redundancy check."""
    report = validate_structure(redundancy_bloat_note)

    failed_names = [c.name for c in report.failed_checks]
    assert "redundancy_bloat" in failed_names, (
        f"Expected 'redundancy_bloat' in failed checks, got: {failed_names}"
    )


def test_redundancy_bloat_tier1_failure_type(redundancy_bloat_note):
    """Tier 1 pipeline should report 'redundancy_bloat' failure type."""
    report = run_tier1(redundancy_bloat_note)
    assert "redundancy_bloat" in report.failure_types


# ---------------------------------------------------------------------------
# Structural errors — should detect wrong section order
# ---------------------------------------------------------------------------


def test_structural_errors_fails_ordering_check(structural_errors_note):
    """A note with Plan before Assessment should fail the section_ordering check."""
    report = validate_structure(structural_errors_note)

    failed_names = [c.name for c in report.failed_checks]
    assert "section_ordering" in failed_names, (
        f"Expected 'section_ordering' in failed checks, got: {failed_names}"
    )


def test_structural_errors_tier1_failure_type(structural_errors_note):
    """Tier 1 pipeline should report 'structural_errors' failure type."""
    report = run_tier1(structural_errors_note)
    assert "structural_errors" in report.failure_types


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_section_fails_gracefully(empty_section_note):
    """A note with an empty Objective section should fail presence/length check, not crash."""
    report = run_tier1(empty_section_note)
    assert not report.passed
    # Verify it flagged missing section, not an unhandled exception
    assert "missing_section" in report.failure_types


def test_missing_transcript_handled(missing_transcript_note):
    """A note without a transcript should still pass Tier 1 structural checks if well-formed."""
    report = run_tier1(missing_transcript_note)
    # Structure checks don't require a transcript
    assert report.passed


def test_malformed_soap_detects_missing_sections(malformed_soap_note):
    """A note with no SOAP headers should be detected as missing multiple sections."""
    report = run_tier1(malformed_soap_note)
    assert not report.passed
    assert "missing_section" in report.failure_types


def test_empty_text_entity_extraction():
    """Entity extraction on empty text should return empty results without crashing."""
    result = extract_entities("")
    assert result.all_entities() == []


def test_tier1_report_is_serializable(good_note):
    """Tier 1 report must be JSON-serialisable (required for output/tier1_sample_report.json)."""
    import json

    report = run_tier1(good_note)
    json_str = report.to_json()
    parsed = json.loads(json_str)
    assert parsed["note_id"] == good_note.note_id
    assert "structure" in parsed
    assert "entities" in parsed
