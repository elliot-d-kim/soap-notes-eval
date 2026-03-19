"""Judge calibration utilities for meta-evaluation.

Compares LLM judge verdicts against ground-truth failure labels from the
degradation manifest. This is the core meta-evaluation loop:

  1. Run the judge on degraded notes (ground truth: known failure type).
  2. Check whether the judge correctly identified the failure.
  3. Report precision, recall, and per-failure-type accuracy.

This answers: "Does the judge catch what it claims to catch?"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.meta_eval.agreement import AgreementMetrics, compute_agreement
from src.tier2.schemas import Tier2Verdict, Verdict


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass
class CalibrationResult:
    """Result of comparing judge verdicts against degradation manifest ground truth."""

    total_notes: int
    total_degraded: int
    total_good: int

    # Overall agreement (judge verdict vs ground truth: PASS for good, FAIL for degraded)
    overall_agreement: AgreementMetrics

    # Per-failure-type detection rates
    failure_type_results: dict[str, "FailureTypeResult"] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_notes": self.total_notes,
            "total_degraded": self.total_degraded,
            "total_good": self.total_good,
            "overall_agreement": self.overall_agreement.to_dict(),
            "failure_type_results": {
                ft: r.to_dict() for ft, r in self.failure_type_results.items()
            },
        }


@dataclass
class FailureTypeResult:
    """Detection rate for a specific degradation failure type."""

    failure_type: str
    n_notes: int  # number of notes with this failure type
    detected: int  # judge correctly flagged as FAIL
    missed: int  # judge incorrectly gave PASS (false negative)
    detection_rate: float  # detected / n_notes

    def to_dict(self) -> dict:
        return {
            "failure_type": self.failure_type,
            "n_notes": self.n_notes,
            "detected": self.detected,
            "missed": self.missed,
            "detection_rate": round(self.detection_rate, 4),
        }


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


def load_degradation_manifest(manifest_path: str | Path) -> list[dict]:
    """Load the degraded samples manifest from data/samples/degraded/manifest.json."""
    manifest_path = Path(manifest_path)
    with open(manifest_path) as f:
        data = json.load(f)
    return data.get("samples", [])


# ---------------------------------------------------------------------------
# Core calibration
# ---------------------------------------------------------------------------


def calibrate_judge(
    verdicts: list[Tier2Verdict],
    manifest_entries: list[dict],
) -> CalibrationResult:
    """Compare judge verdicts against ground-truth manifest labels.

    Args:
        verdicts: Judge verdicts for a set of notes (good + degraded).
        manifest_entries: Entries from degradation manifest with note_id and
                         degradation_types (or empty list for good notes).

    Returns:
        CalibrationResult with detection rates per failure type and overall agreement.
    """
    # Build ground-truth map: note_id → is_degraded
    gt_map: dict[str, list[str]] = {}
    for entry in manifest_entries:
        note_id = entry["note_id"]
        gt_map[note_id] = entry.get("degradation_types", [])

    # Build verdict map
    verdict_map: dict[str, Tier2Verdict] = {v.note_id: v for v in verdicts}

    # Only evaluate notes present in both maps
    common_ids = sorted(set(gt_map) & set(verdict_map))

    if not common_ids:
        raise ValueError("No overlapping note IDs between verdicts and manifest entries.")

    judge_labels: list[str] = []
    human_labels: list[str] = []

    # Failure type tracking
    ft_detected: dict[str, int] = {}
    ft_total: dict[str, int] = {}

    for note_id in common_ids:
        degradation_types = gt_map[note_id]
        verdict = verdict_map[note_id]

        # Ground truth: FAIL if degraded, PASS if good
        gt_label = "fail" if degradation_types else "pass"
        judge_label = verdict.overall_verdict.value

        human_labels.append(gt_label)
        judge_labels.append(judge_label)

        # Per-failure-type tracking
        for ft in degradation_types:
            ft_total[ft] = ft_total.get(ft, 0) + 1
            if judge_label == "fail":
                ft_detected[ft] = ft_detected.get(ft, 0) + 1
            else:
                # Ensure the key exists even with 0 detections
                ft_detected.setdefault(ft, 0)

    overall_agreement = compute_agreement(judge_labels, human_labels)

    # Per-failure-type results
    failure_type_results = {}
    for ft, total in ft_total.items():
        detected = ft_detected.get(ft, 0)
        failure_type_results[ft] = FailureTypeResult(
            failure_type=ft,
            n_notes=total,
            detected=detected,
            missed=total - detected,
            detection_rate=detected / total if total > 0 else 0.0,
        )

    n_degraded = sum(1 for nid in common_ids if gt_map[nid])
    n_good = len(common_ids) - n_degraded

    return CalibrationResult(
        total_notes=len(common_ids),
        total_degraded=n_degraded,
        total_good=n_good,
        overall_agreement=overall_agreement,
        failure_type_results=failure_type_results,
    )


def calibrate_from_files(
    verdicts_path: str | Path,
    manifest_path: str | Path,
) -> CalibrationResult:
    """Load verdicts and manifest from disk, then run calibration.

    Args:
        verdicts_path: Path to a JSON file containing a list of Tier2Verdict dicts.
        manifest_path: Path to the degraded samples manifest.json.

    Returns:
        CalibrationResult.
    """
    with open(verdicts_path) as f:
        raw_verdicts = json.load(f)

    verdicts = [Tier2Verdict.model_validate(v) for v in raw_verdicts]
    manifest_entries = load_degradation_manifest(manifest_path)

    return calibrate_judge(verdicts, manifest_entries)
