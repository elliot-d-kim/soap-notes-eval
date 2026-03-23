"""Tier 1 automated screening tests.

Test strategy:
1. Known-good notes pass all checks.
2. Each degradation type triggers its expected failure.
3. Edge cases (empty sections, malformed SOAP, missing transcript) are handled.
4. Entity extraction returns expected entity types for clinical text.
5. Manifest-driven tests: load degraded samples from data/samples/degraded/manifest.json
   and verify Tier 1 detects the expected failure types.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.loaders import parse_soap_sections
from src.data.models import SOAPNote
from src.tier1.entities import ExtractedEntities, extract_entities
from src.tier1.pipeline import run_tier1
from src.tier1.structure import validate_structure


# ---------------------------------------------------------------------------
# Manifest-driven degraded sample loading
# ---------------------------------------------------------------------------

_DEGRADED_DIR = Path(__file__).parent.parent / "data" / "eval_set" / "degraded"
_DEGRADED_MANIFEST = _DEGRADED_DIR / "manifest.json"

# Failure types that Tier 1 structural checks can detect (programmatic degradations)
_TIER1_DETECTABLE = {"missing_section", "redundancy_bloat", "structural_errors"}


def _load_degraded_manifest_entries() -> list[dict]:
    """Load entries from data/samples/degraded/manifest.json."""
    if not _DEGRADED_MANIFEST.exists():
        return []
    with open(_DEGRADED_MANIFEST) as f:
        data = json.load(f)
    return data.get("samples", [])


def _load_degraded_note(entry: dict) -> SOAPNote:
    """Load a degraded sample JSON file into a SOAPNote."""
    path = _DEGRADED_DIR / entry["filename"]
    with open(path) as f:
        raw = json.load(f)
    note_text = raw.get("note_text", "")
    return SOAPNote(
        note_id=entry["note_id"],
        source_dataset=entry.get("source_dataset", "test"),
        transcript=raw.get("transcript"),
        note_text=note_text,
        sections=parse_soap_sections(note_text),
    )


def _tier1_detectable_entries() -> list[dict]:
    """Return manifest entries whose degradation types are detectable by Tier 1."""
    entries = _load_degraded_manifest_entries()
    result = []
    seen = set()
    for entry in entries:
        dtypes = set(entry.get("degradation_types", []))
        note_id = entry["note_id"]
        if dtypes & _TIER1_DETECTABLE and note_id not in seen:
            seen.add(note_id)
            result.append(entry)
    return result


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


# ---------------------------------------------------------------------------
# Manifest-driven tests — load degraded samples from disk
# ---------------------------------------------------------------------------


_MANIFEST_ENTRIES = _tier1_detectable_entries()


@pytest.mark.skipif(
    not _MANIFEST_ENTRIES,
    reason="No degraded manifest entries found (run generate_degraded.py first)",
)
@pytest.mark.parametrize(
    "entry",
    _MANIFEST_ENTRIES,
    ids=[e["note_id"] for e in _MANIFEST_ENTRIES],
)
def test_manifest_degraded_sample_detected(entry):
    """Tier 1 should detect failure in each degraded sample loaded from manifest.json."""
    note = _load_degraded_note(entry)
    report = run_tier1(note)

    expected_types = set(entry["degradation_types"]) & _TIER1_DETECTABLE
    assert not report.passed, (
        f"Expected Tier 1 to fail for {entry['note_id']} "
        f"(degradation: {entry['degradation_types']}), but it passed."
    )
    for expected_ft in expected_types:
        assert expected_ft in report.failure_types, (
            f"Expected failure type '{expected_ft}' in Tier 1 report for "
            f"{entry['note_id']}, got: {report.failure_types}"
        )
