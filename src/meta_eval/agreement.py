"""Inter-rater agreement metrics for meta-evaluation.

Implements Cohen's kappa and Krippendorff's alpha for measuring agreement
between the LLM judge and human expert labels.

Target: >90% agreement on binary pass/fail (see config.agreement_target).

These metrics are the foundation for answering: "Is the judge trustworthy?"
Without measuring judge-vs-human agreement, the eval system is a black box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from sklearn.metrics import cohen_kappa_score

try:
    import krippendorff
    _KRIPPENDORFF_AVAILABLE = True
except ImportError:
    _KRIPPENDORFF_AVAILABLE = False

from src.config import settings


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class AgreementMetrics:
    """Inter-rater agreement between two raters (e.g., judge vs human)."""

    n_samples: int

    # Percent agreement (simplest metric)
    percent_agreement: float

    # Cohen's kappa — accounts for chance agreement
    # Range: [-1, 1]; ≥0.80 = strong agreement, ≥0.61 = moderate
    cohens_kappa: float
    kappa_interpretation: str

    # Krippendorff's alpha — more general, handles missing data
    # Range: [-1, 1]; ≥0.80 = acceptable reliability
    krippendorffs_alpha: float | None  # None if library unavailable

    # Confusion matrix components (binary: PASS=1, FAIL=0)
    true_pass: int  # Both judge and human say PASS
    true_fail: int  # Both say FAIL
    judge_pass_human_fail: int  # False positive (judge more lenient)
    judge_fail_human_pass: int  # False negative (judge more strict)

    meets_target: bool  # percent_agreement >= settings.agreement_target

    def to_dict(self) -> dict:
        return {
            "n_samples": self.n_samples,
            "percent_agreement": round(self.percent_agreement, 4),
            "cohens_kappa": round(self.cohens_kappa, 4),
            "kappa_interpretation": self.kappa_interpretation,
            "krippendorffs_alpha": (
                round(self.krippendorffs_alpha, 4)
                if self.krippendorffs_alpha is not None
                else None
            ),
            "confusion": {
                "true_pass": self.true_pass,
                "true_fail": self.true_fail,
                "judge_pass_human_fail": self.judge_pass_human_fail,
                "judge_fail_human_pass": self.judge_fail_human_pass,
            },
            "meets_target": self.meets_target,
            "target": settings.agreement_target,
        }


# ---------------------------------------------------------------------------
# Kappa interpretation
# ---------------------------------------------------------------------------

_KAPPA_THRESHOLDS = [
    (0.81, "almost_perfect"),
    (0.61, "substantial"),
    (0.41, "moderate"),
    (0.21, "fair"),
    (0.00, "slight"),
    (float("-inf"), "poor_or_negative"),
]


def _interpret_kappa(kappa: float) -> str:
    for threshold, label in _KAPPA_THRESHOLDS:
        if kappa >= threshold:
            return label
    return "poor_or_negative"


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_agreement(
    judge_labels: list[str],
    human_labels: list[str],
    label_map: dict[str, int] | None = None,
) -> AgreementMetrics:
    """Compute inter-rater agreement between judge and human labels.

    Args:
        judge_labels: LLM judge verdicts (e.g., ["pass", "fail", "pass", ...]).
        human_labels: Human expert labels (same length, same label space).
        label_map: Optional mapping from string label to int. Defaults to
                   {"pass": 1, "fail": 0}.

    Returns:
        AgreementMetrics with kappa, alpha, and confusion matrix.

    Raises:
        ValueError: If label lists have different lengths or are empty.
    """
    if len(judge_labels) != len(human_labels):
        raise ValueError(
            f"Label lists must be same length: "
            f"judge={len(judge_labels)}, human={len(human_labels)}"
        )
    if not judge_labels:
        raise ValueError("Label lists cannot be empty.")

    if label_map is None:
        label_map = {"pass": 1, "fail": 0}

    # Normalise to lowercase strings
    j = [str(l).lower() for l in judge_labels]
    h = [str(l).lower() for l in human_labels]

    # Convert to integers for sklearn
    j_int = [label_map.get(l, 0) for l in j]
    h_int = [label_map.get(l, 0) for l in h]

    n = len(j_int)

    # Percent agreement
    agreements = sum(a == b for a, b in zip(j_int, h_int))
    percent_agreement = agreements / n

    # Cohen's kappa
    if len(set(j_int + h_int)) < 2:
        # All labels are identical — kappa is undefined, treat as perfect
        kappa = 1.0
    else:
        kappa = float(cohen_kappa_score(h_int, j_int))

    # Krippendorff's alpha (nominal)
    # Undefined when all labels are identical (only one value in domain) — treat as 1.0.
    alpha = None
    if _KRIPPENDORFF_AVAILABLE:
        reliability_data = np.array([j_int, h_int], dtype=float)
        if len(set(j_int + h_int)) < 2:
            alpha = 1.0
        else:
            alpha = float(krippendorff.alpha(reliability_data=reliability_data, level_of_measurement="nominal"))

    # Confusion matrix
    tp = sum(a == 1 and b == 1 for a, b in zip(j_int, h_int))
    tf = sum(a == 0 and b == 0 for a, b in zip(j_int, h_int))
    jp_hf = sum(a == 1 and b == 0 for a, b in zip(j_int, h_int))
    jf_hp = sum(a == 0 and b == 1 for a, b in zip(j_int, h_int))

    return AgreementMetrics(
        n_samples=n,
        percent_agreement=percent_agreement,
        cohens_kappa=kappa,
        kappa_interpretation=_interpret_kappa(kappa),
        krippendorffs_alpha=alpha,
        true_pass=tp,
        true_fail=tf,
        judge_pass_human_fail=jp_hf,
        judge_fail_human_pass=jf_hp,
        meets_target=percent_agreement >= settings.agreement_target,
    )


def compute_per_criterion_agreement(
    judge_criteria: list[dict[str, str]],
    human_criteria: list[dict[str, str]],
) -> dict[str, AgreementMetrics]:
    """Compute agreement metrics per PDQI-9 criterion.

    Args:
        judge_criteria: List of dicts with "criterion" and "verdict" keys, one per note.
                        Example: [{"accuracy": "pass", "completeness": "fail", ...}, ...]
        human_criteria: Same structure with human labels.

    Returns:
        Dict mapping criterion name → AgreementMetrics.
    """
    if not judge_criteria or not human_criteria:
        return {}

    # Gather all criterion names
    all_criteria = set()
    for record in judge_criteria + human_criteria:
        all_criteria.update(record.keys())

    results = {}
    for criterion in sorted(all_criteria):
        j_labels = [r.get(criterion, "fail") for r in judge_criteria]
        h_labels = [r.get(criterion, "fail") for r in human_criteria]
        results[criterion] = compute_agreement(j_labels, h_labels)

    return results
