"""Dataset-specific loaders for SOAP note evaluation.

Each loader normalises a source dataset's raw fields into the canonical
SOAPNote model, preserving original field names in metadata.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

from src.data.models import SOAPNote, SOAPSections


# ---------------------------------------------------------------------------
# Section parsing helpers
# ---------------------------------------------------------------------------

_SECTION_PATTERNS = {
    "subjective": re.compile(
        r"(?:^|\n)\s*(?:S(?:ubjective)?|Chief Complaint|CC|HPI)\s*[:\-]\s*",
        re.IGNORECASE,
    ),
    "objective": re.compile(
        r"(?:^|\n)\s*O(?:bjective)?\s*[:\-]\s*", re.IGNORECASE
    ),
    "assessment": re.compile(
        r"(?:^|\n)\s*A(?:ssessment)?\s*[:\-]\s*", re.IGNORECASE
    ),
    "plan": re.compile(r"(?:^|\n)\s*P(?:lan)?\s*[:\-]\s*", re.IGNORECASE),
}

_SECTION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:S(?:ubjective)?|O(?:bjective)?|A(?:ssessment)?|P(?:lan)?|"
    r"Chief Complaint|CC|HPI)\s*[:\-]\s*",
    re.IGNORECASE,
)


def parse_soap_sections(note_text: str) -> SOAPSections:
    """Extract SOAP sections from free-text note using header pattern matching.

    Handles common variants: 'S:', 'Subjective:', 'S -', etc.
    Returns SOAPSections with None for any missing section.
    """
    if not note_text or not note_text.strip():
        return SOAPSections()

    # Find all header positions
    headers_found: list[tuple[str, int, int]] = []  # (label, start, end)
    for label, pattern in _SECTION_PATTERNS.items():
        for m in pattern.finditer(note_text):
            headers_found.append((label, m.start(), m.end()))

    if not headers_found:
        # No section headers detected — treat entire note as subjective
        return SOAPSections(subjective=note_text.strip())

    headers_found.sort(key=lambda x: x[1])

    sections: dict[str, str] = {}
    for i, (label, _, content_start) in enumerate(headers_found):
        if i + 1 < len(headers_found):
            content_end = headers_found[i + 1][1]
        else:
            content_end = len(note_text)
        content = note_text[content_start:content_end].strip()
        if content:
            sections[label] = content

    return SOAPSections(**sections)


# ---------------------------------------------------------------------------
# File-based loader (for pre-downloaded JSON samples)
# ---------------------------------------------------------------------------


def load_samples_from_manifest(manifest_path: str | Path) -> Iterator[SOAPNote]:
    """Load all good (non-degraded) samples referenced in manifest.json."""
    manifest_path = Path(manifest_path)
    with open(manifest_path) as f:
        manifest = json.load(f)

    samples_dir = manifest_path.parent
    for entry in manifest.get("samples", []):
        if entry.get("label") != "good":
            continue
        sample_file = samples_dir / entry["filename"]
        if not sample_file.exists():
            continue
        with open(sample_file) as f:
            raw = json.load(f)
        note_text = raw.get("note_text", raw.get("note", raw.get("soap_note", "")))
        yield SOAPNote(
            note_id=entry["note_id"],
            source_dataset=entry["source_dataset"],
            transcript=raw.get("transcript", raw.get("dialogue", raw.get("conversation"))),
            note_text=note_text,
            sections=parse_soap_sections(note_text),
            ground_truth_note=raw.get("ground_truth_note"),
            metadata=entry.get("metadata", {}),
        )


def load_note_from_file(path: str | Path, note_id: str, source_dataset: str) -> SOAPNote:
    """Load a single SOAP note JSON file into the canonical model."""
    path = Path(path)
    with open(path) as f:
        raw = json.load(f)
    note_text = raw.get("note_text", raw.get("note", raw.get("soap_note", "")))
    return SOAPNote(
        note_id=note_id,
        source_dataset=source_dataset,
        transcript=raw.get("transcript", raw.get("dialogue", raw.get("conversation"))),
        note_text=note_text,
        sections=parse_soap_sections(note_text),
        ground_truth_note=raw.get("ground_truth_note"),
        metadata={k: v for k, v in raw.items() if k not in ("note_text", "note", "soap_note", "transcript", "dialogue", "conversation", "ground_truth_note")},
    )
