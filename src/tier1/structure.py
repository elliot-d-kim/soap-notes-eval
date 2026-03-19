"""Section completeness and structural validation for Tier 1.

Checks:
1. Section presence — all four SOAP sections must exist and be non-empty.
2. Section ordering — S → O → A → P is the expected canonical order.
3. Minimum content thresholds — each section must have meaningful content.
4. Redundancy / note-bloat detection — duplicate sentences and padding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.data.models import SOAPNote, SOAPSections


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass
class SectionCheck:
    """Result of a single structural check."""

    name: str
    passed: bool
    details: str = ""


@dataclass
class StructureReport:
    """Aggregated result of all structural checks for one SOAP note."""

    note_id: str
    checks: list[SectionCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[SectionCheck]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "details": c.details}
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CANONICAL_ORDER = ["subjective", "objective", "assessment", "plan"]

# Minimum word count per section to be considered non-trivial
_MIN_WORDS: dict[str, int] = {
    "subjective": 10,
    "objective": 5,
    "assessment": 5,
    "plan": 5,
}

# Fraction of sentences that are duplicates to flag bloat.
# 0.20 catches notes with even a single duplicated section (e.g., Plan repeated)
# while avoiding false positives on notes with incidental wording overlaps.
_REDUNDANCY_THRESHOLD = 0.20


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_section_presence(sections: SOAPSections) -> list[SectionCheck]:
    """Verify each SOAP section is present and non-empty."""
    results = []
    for sec in _CANONICAL_ORDER:
        text = getattr(sections, sec)
        present = bool(text and text.strip())
        results.append(
            SectionCheck(
                name=f"section_present:{sec}",
                passed=present,
                details="" if present else f"'{sec}' section is missing or empty",
            )
        )
    return results


def _check_section_content_length(sections: SOAPSections) -> list[SectionCheck]:
    """Verify each section has meaningful content (above minimum word threshold)."""
    results = []
    for sec in _CANONICAL_ORDER:
        text = getattr(sections, sec) or ""
        word_count = len(text.split())
        min_required = _MIN_WORDS[sec]
        passed = word_count >= min_required
        results.append(
            SectionCheck(
                name=f"section_length:{sec}",
                passed=passed,
                details=(
                    ""
                    if passed
                    else f"'{sec}' has {word_count} words (minimum {min_required})"
                ),
            )
        )
    return results


def _check_section_ordering(note_text: str) -> SectionCheck:
    """Verify SOAP sections appear in canonical S → O → A → P order.

    Detects structural errors such as Plan appearing before Assessment.
    """
    header_re = re.compile(
        r"(?:^|\n)\s*"
        r"(?P<section>Subjective|Objective|Assessment|Plan|"
        r"S(?=\s*:)|O(?=\s*:)|A(?=\s*:)|P(?=\s*:))"
        r"\s*[:\-]",
        re.IGNORECASE | re.MULTILINE,
    )

    # Map detected headers to canonical section names
    _header_map = {
        "s": "subjective", "subjective": "subjective",
        "o": "objective", "objective": "objective",
        "a": "assessment", "assessment": "assessment",
        "p": "plan", "plan": "plan",
    }

    found_order: list[str] = []
    for m in header_re.finditer(note_text):
        label = m.group("section").lower()
        canonical = _header_map.get(label)
        if canonical and canonical not in found_order:
            found_order.append(canonical)

    if len(found_order) < 2:
        return SectionCheck(
            name="section_ordering",
            passed=True,
            details="Insufficient section headers detected to assess ordering",
        )

    # Check that the found order is a subsequence of canonical order
    expected_positions = {sec: i for i, sec in enumerate(_CANONICAL_ORDER)}
    actual_positions = [expected_positions[s] for s in found_order if s in expected_positions]
    ordered = actual_positions == sorted(actual_positions)

    return SectionCheck(
        name="section_ordering",
        passed=ordered,
        details=(
            ""
            if ordered
            else f"Sections appear out of order: {' → '.join(found_order)}"
        ),
    )


def _check_redundancy(sections: SOAPSections) -> SectionCheck:
    """Detect duplicate sentences or note bloat within the full note."""
    all_sentences: list[str] = []

    for sec in _CANONICAL_ORDER:
        text = getattr(sections, sec) or ""
        # Simple sentence split on period/newline
        sentences = [
            s.strip()
            for s in re.split(r"[.\n]+", text)
            if len(s.strip()) > 10
        ]
        all_sentences.extend(sentences)

    if not all_sentences:
        return SectionCheck(name="redundancy_bloat", passed=True)

    normalized = [re.sub(r"\s+", " ", s.lower()) for s in all_sentences]
    unique = set(normalized)
    duplicate_fraction = 1.0 - len(unique) / len(normalized)

    passed = duplicate_fraction < _REDUNDANCY_THRESHOLD
    return SectionCheck(
        name="redundancy_bloat",
        passed=passed,
        details=(
            ""
            if passed
            else (
                f"{duplicate_fraction:.0%} of sentences are duplicates "
                f"(threshold: {_REDUNDANCY_THRESHOLD:.0%})"
            )
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_structure(note: SOAPNote) -> StructureReport:
    """Run all structural checks on a SOAP note.

    Args:
        note: The SOAP note to validate.

    Returns:
        StructureReport with per-check results and an overall pass/fail.
    """
    report = StructureReport(note_id=note.note_id)
    report.checks.extend(_check_section_presence(note.sections))
    report.checks.extend(_check_section_content_length(note.sections))
    report.checks.append(_check_section_ordering(note.note_text))
    report.checks.append(_check_redundancy(note.sections))
    return report
