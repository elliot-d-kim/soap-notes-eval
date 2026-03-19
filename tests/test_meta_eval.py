"""Meta-evaluation tests — agreement metrics and judge calibration.

Tests that:
1. Agreement metrics compute correctly on known label pairs.
2. Perfect agreement yields kappa=1.0 and percent_agreement=1.0.
3. Zero agreement yields kappa≤0 and percent_agreement=0.0.
4. Calibration logic correctly identifies detection rates per failure type.
5. Edge cases (all same label, single sample) are handled.
"""

from __future__ import annotations

import pytest

from src.meta_eval.agreement import AgreementMetrics, compute_agreement, compute_per_criterion_agreement
from src.meta_eval.calibrate import CalibrationResult, FailureTypeResult, calibrate_judge
from src.tier2.schemas import (
    CriterionVerdict,
    Tier2Verdict,
    Verdict,
)


# ---------------------------------------------------------------------------
# Agreement metric tests
# ---------------------------------------------------------------------------


def test_perfect_agreement():
    """Perfect agreement should yield percent_agreement=1.0 and kappa=1.0."""
    labels = ["pass", "fail", "pass", "pass", "fail"]
    result = compute_agreement(labels, labels)

    assert result.percent_agreement == 1.0
    assert result.cohens_kappa == pytest.approx(1.0)
    assert result.true_pass == 3
    assert result.true_fail == 2
    assert result.judge_pass_human_fail == 0
    assert result.judge_fail_human_pass == 0


def test_zero_agreement():
    """Complete disagreement should yield percent_agreement=0.0 and kappa<0."""
    judge = ["pass", "pass", "pass", "pass"]
    human = ["fail", "fail", "fail", "fail"]
    result = compute_agreement(judge, human)

    assert result.percent_agreement == 0.0
    assert result.cohens_kappa <= 0.0


def test_partial_agreement():
    """3/4 agreement should yield percent_agreement=0.75."""
    judge = ["pass", "pass", "fail", "pass"]
    human = ["pass", "fail", "fail", "pass"]
    result = compute_agreement(judge, human)

    assert result.percent_agreement == pytest.approx(0.75)
    assert result.judge_pass_human_fail == 1  # judge said pass, human said fail
    assert result.judge_fail_human_pass == 0


def test_agreement_meets_target():
    """Agreement above the configured target should set meets_target=True."""
    # 10/10 perfect agreement
    labels = ["pass"] * 5 + ["fail"] * 5
    result = compute_agreement(labels, labels)
    assert result.meets_target is True


def test_agreement_below_target():
    """Agreement below 90% target should set meets_target=False."""
    judge = ["pass"] * 8 + ["fail"] * 2
    human = ["fail"] * 8 + ["pass"] * 2  # complete inversion
    result = compute_agreement(judge, human)
    assert result.meets_target is False


def test_empty_labels_raises():
    """Empty label lists should raise ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        compute_agreement([], [])


def test_mismatched_lengths_raises():
    """Mismatched label list lengths should raise ValueError."""
    with pytest.raises(ValueError, match="same length"):
        compute_agreement(["pass", "fail"], ["pass"])


def test_all_same_label_handled():
    """When all labels are identical, agreement should be 1.0 (kappa undefined → 1.0)."""
    labels = ["pass", "pass", "pass"]
    result = compute_agreement(labels, labels)
    assert result.percent_agreement == 1.0
    # Kappa is set to 1.0 when all labels match
    assert result.cohens_kappa == pytest.approx(1.0)


def test_agreement_to_dict():
    """AgreementMetrics.to_dict() should be JSON-serialisable."""
    import json

    labels = ["pass", "fail", "pass"]
    result = compute_agreement(labels, labels)
    d = result.to_dict()
    json.dumps(d)  # should not raise
    assert "percent_agreement" in d
    assert "cohens_kappa" in d


def test_per_criterion_agreement():
    """Per-criterion agreement should compute separate metrics for each criterion."""
    judge = [
        {"accuracy": "pass", "completeness": "fail"},
        {"accuracy": "pass", "completeness": "pass"},
    ]
    human = [
        {"accuracy": "pass", "completeness": "pass"},
        {"accuracy": "fail", "completeness": "pass"},
    ]
    results = compute_per_criterion_agreement(judge, human)

    assert "accuracy" in results
    assert "completeness" in results
    # accuracy: judge=[pass,pass], human=[pass,fail] → 1/2 agreement
    assert results["accuracy"].percent_agreement == pytest.approx(0.5)
    # completeness: judge=[fail,pass], human=[pass,pass] → 1/2 agreement
    assert results["completeness"].percent_agreement == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Calibration tests
# ---------------------------------------------------------------------------


def _make_verdict(note_id: str, verdict: str, escalate: bool = False) -> Tier2Verdict:
    """Create a minimal Tier2Verdict for calibration testing."""
    return Tier2Verdict(
        note_id=note_id,
        model_used="test-model",
        prompt_version="v001",
        timestamp="2026-03-19T00:00:00Z",
        criteria=[
            CriterionVerdict(
                criterion="accuracy",
                rationale="Test evaluation rationale for testing purposes.",
                verdict=Verdict(verdict),
            )
        ],
        hallucination_flags=[],
        overall_verdict=Verdict(verdict),
        overall_rationale="Test overall rationale.",
        escalate_to_tier3=escalate,
    )


def test_calibration_perfect_detection():
    """Judge correctly flags all degraded notes and passes all good notes."""
    verdicts = [
        _make_verdict("good_001", "pass"),
        _make_verdict("good_002", "pass"),
        _make_verdict("degraded_001", "fail"),
        _make_verdict("degraded_002", "fail"),
    ]
    manifest_entries = [
        {"note_id": "good_001", "degradation_types": []},
        {"note_id": "good_002", "degradation_types": []},
        {"note_id": "degraded_001", "degradation_types": ["missing_section"]},
        {"note_id": "degraded_002", "degradation_types": ["redundancy_bloat"]},
    ]
    result = calibrate_judge(verdicts, manifest_entries)

    assert result.total_notes == 4
    assert result.total_good == 2
    assert result.total_degraded == 2
    assert result.overall_agreement.percent_agreement == 1.0


def test_calibration_missed_degradation():
    """Judge misses a degraded note — should lower detection rate."""
    verdicts = [
        _make_verdict("good_001", "pass"),
        _make_verdict("degraded_001", "pass"),  # missed — judge says PASS on degraded note
        _make_verdict("degraded_002", "fail"),
    ]
    manifest_entries = [
        {"note_id": "good_001", "degradation_types": []},
        {"note_id": "degraded_001", "degradation_types": ["missing_section"]},
        {"note_id": "degraded_002", "degradation_types": ["missing_section"]},
    ]
    result = calibrate_judge(verdicts, manifest_entries)

    assert result.overall_agreement.percent_agreement == pytest.approx(2 / 3)
    missing_section_result = result.failure_type_results.get("missing_section")
    assert missing_section_result is not None
    assert missing_section_result.n_notes == 2
    assert missing_section_result.detected == 1
    assert missing_section_result.missed == 1
    assert missing_section_result.detection_rate == pytest.approx(0.5)


def test_calibration_failure_type_results():
    """Each failure type should have its own detection rate."""
    verdicts = [
        _make_verdict("note_ms", "fail"),    # missing_section — correctly flagged
        _make_verdict("note_rb", "pass"),    # redundancy_bloat — missed
        _make_verdict("note_se", "fail"),    # structural_errors — correctly flagged
    ]
    manifest_entries = [
        {"note_id": "note_ms", "degradation_types": ["missing_section"]},
        {"note_id": "note_rb", "degradation_types": ["redundancy_bloat"]},
        {"note_id": "note_se", "degradation_types": ["structural_errors"]},
    ]
    result = calibrate_judge(verdicts, manifest_entries)

    assert result.failure_type_results["missing_section"].detection_rate == 1.0
    assert result.failure_type_results["redundancy_bloat"].detection_rate == 0.0
    assert result.failure_type_results["structural_errors"].detection_rate == 1.0


def test_calibration_no_overlap_raises():
    """Calibration with no overlapping note IDs should raise ValueError."""
    verdicts = [_make_verdict("note_a", "pass")]
    manifest_entries = [{"note_id": "note_b", "degradation_types": []}]

    with pytest.raises(ValueError, match="No overlapping note IDs"):
        calibrate_judge(verdicts, manifest_entries)


def test_calibration_to_dict():
    """CalibrationResult.to_dict() should be JSON-serialisable."""
    import json

    verdicts = [
        _make_verdict("good_001", "pass"),
        _make_verdict("bad_001", "fail"),
    ]
    manifest_entries = [
        {"note_id": "good_001", "degradation_types": []},
        {"note_id": "bad_001", "degradation_types": ["missing_section"]},
    ]
    result = calibrate_judge(verdicts, manifest_entries)
    d = result.to_dict()
    json.dumps(d)  # should not raise
    assert "overall_agreement" in d
    assert "failure_type_results" in d
