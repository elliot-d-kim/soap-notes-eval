"""Tier 1 orchestrator — automated screening pipeline.

Runs all Tier 1 checks (entity extraction + structural validation) on a SOAP
note and produces a structured JSON-serialisable report.

Tier 1 is synchronous and fast (~50–200 ms per note) — designed to run on
every note in real-time before the async Tier 2 LLM judge.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.data.models import SOAPNote, SOAPSections
from src.tier1.entities import ExtractedEntities, extract_entities, extract_entities_from_sections
from src.tier1.structure import StructureReport, validate_structure


# ---------------------------------------------------------------------------
# Report models
# ---------------------------------------------------------------------------


@dataclass
class Tier1Report:
    """Complete Tier 1 screening report for a single SOAP note."""

    note_id: str
    source_dataset: str
    timestamp: str

    # Structural validation
    structure: StructureReport

    # Entity extraction (per section)
    entities_per_section: dict[str, ExtractedEntities]

    # Overall
    passed: bool
    failure_types: list[str]  # high-level failure categories for Tier 2 routing

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "source_dataset": self.source_dataset,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "failure_types": self.failure_types,
            "structure": self.structure.to_dict(),
            "entities": {
                sec: ents.to_dict()
                for sec, ents in self.entities_per_section.items()
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Failure-type mapping
# ---------------------------------------------------------------------------

# Map Tier 1 check names to high-level failure categories used for routing
_CHECK_TO_FAILURE_TYPE: dict[str, str] = {
    "section_present:subjective": "missing_section",
    "section_present:objective": "missing_section",
    "section_present:assessment": "missing_section",
    "section_present:plan": "missing_section",
    "section_length:subjective": "missing_section",
    "section_length:objective": "missing_section",
    "section_length:assessment": "missing_section",
    "section_length:plan": "missing_section",
    "section_ordering": "structural_errors",
    "redundancy_bloat": "redundancy_bloat",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_tier1(note: SOAPNote) -> Tier1Report:
    """Run all Tier 1 checks on a SOAP note and return a structured report.

    Args:
        note: The SOAP note to evaluate.

    Returns:
        Tier1Report with per-check pass/fail, extracted entities, and overall verdict.
    """
    # Structural validation
    structure_report = validate_structure(note)

    # Entity extraction per section
    sections_dict = {
        "subjective": note.sections.subjective,
        "objective": note.sections.objective,
        "assessment": note.sections.assessment,
        "plan": note.sections.plan,
    }
    entities = extract_entities_from_sections(sections_dict)

    # Derive failure types from failed checks
    failure_types: list[str] = []
    for check in structure_report.failed_checks:
        ft = _CHECK_TO_FAILURE_TYPE.get(check.name)
        if ft and ft not in failure_types:
            failure_types.append(ft)

    passed = structure_report.passed

    return Tier1Report(
        note_id=note.note_id,
        source_dataset=note.source_dataset,
        timestamp=datetime.now(timezone.utc).isoformat(),
        structure=structure_report,
        entities_per_section=entities,
        passed=passed,
        failure_types=failure_types,
    )


def run_tier1_batch(notes: list[SOAPNote]) -> list[Tier1Report]:
    """Run Tier 1 on a list of notes, returning one report per note."""
    return [run_tier1(note) for note in notes]


def save_report(report: Tier1Report, output_dir: str | Path = "output") -> Path:
    """Save a Tier 1 report to JSON in the output directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"tier1_{report.note_id}.json"
    path.write_text(report.to_json())
    return path
