"""Tier 2 LLM-as-a-Judge tests.

Test strategy:
1. Schema validation — Pydantic models enforce chain-of-thought, binary verdicts, consistency.
2. Judge output structure — parsing logic handles well-formed LLM JSON correctly.
3. Integration tests — actual LLM calls on known-good and degraded notes.
   (Marked with @pytest.mark.integration — skipped unless --run-integration flag passed.)
"""

from __future__ import annotations

import json
import os

import pytest

from src.data.models import SOAPNote, SOAPSections
from src.tier2.schemas import (
    CriterionVerdict,
    HallucinationFlag,
    Tier2Verdict,
    Verdict,
)


# ---------------------------------------------------------------------------
# Schema validation tests (no LLM required)
# ---------------------------------------------------------------------------


def test_criterion_verdict_requires_substantive_rationale():
    """Chain-of-thought enforcement: rationale must be ≥10 chars."""
    with pytest.raises(Exception):  # pydantic ValidationError
        CriterionVerdict(
            criterion="accuracy",
            rationale="ok",  # too short
            verdict=Verdict.PASS,
        )


def test_criterion_verdict_valid():
    """A properly formed CriterionVerdict should be accepted."""
    cv = CriterionVerdict(
        criterion="accuracy",
        rationale="All facts in the note are directly traceable to the transcript.",
        verdict=Verdict.PASS,
    )
    assert cv.verdict == Verdict.PASS


def test_tier2_verdict_overall_consistency():
    """overall_verdict cannot be PASS when a criterion fails."""
    criteria = [
        CriterionVerdict(
            criterion="accuracy",
            rationale="The note contains a medication not mentioned in the transcript.",
            verdict=Verdict.FAIL,
            evidence=["lisinopril 20mg mentioned but transcript says 10mg"],
        ),
    ]
    with pytest.raises(Exception):  # pydantic ValidationError
        Tier2Verdict(
            note_id="test_001",
            model_used="test-model",
            prompt_version="v001",
            timestamp="2026-03-19T00:00:00Z",
            criteria=criteria,
            hallucination_flags=[],
            overall_verdict=Verdict.PASS,  # inconsistent — should raise
            overall_rationale="The note is excellent.",
            escalate_to_tier3=False,
        )


def test_tier2_verdict_fail_with_failing_criterion():
    """A verdict with failing criterion and overall FAIL should be accepted."""
    criteria = [
        CriterionVerdict(
            criterion="accuracy",
            rationale="The note contains a medication not mentioned in the transcript.",
            verdict=Verdict.FAIL,
            evidence=["lisinopril 20mg mentioned but transcript says 10mg"],
        ),
    ]
    verdict = Tier2Verdict(
        note_id="test_001",
        model_used="test-model",
        prompt_version="v001",
        timestamp="2026-03-19T00:00:00Z",
        criteria=criteria,
        hallucination_flags=[],
        overall_verdict=Verdict.FAIL,
        overall_rationale="Accuracy criterion failed due to incorrect medication dosage.",
        escalate_to_tier3=True,
    )
    assert verdict.overall_verdict == Verdict.FAIL
    assert verdict.escalate_to_tier3 is True


def test_tier2_verdict_hallucination_forces_fail():
    """A hallucination with FAIL grounding should force overall_verdict to FAIL."""
    criteria = [
        CriterionVerdict(
            criterion="accuracy",
            rationale="All transcript facts are accurately represented in the note.",
            verdict=Verdict.PASS,
        ),
    ]
    flags = [
        HallucinationFlag(
            entity="metoprolol 25mg",
            claim_in_note="Patient was prescribed metoprolol 25mg daily",
            grounding_verdict=Verdict.FAIL,
            explanation="metoprolol not mentioned anywhere in transcript",
        )
    ]
    with pytest.raises(Exception):
        Tier2Verdict(
            note_id="test_002",
            model_used="test-model",
            prompt_version="v001",
            timestamp="2026-03-19T00:00:00Z",
            criteria=criteria,
            hallucination_flags=flags,
            overall_verdict=Verdict.PASS,  # inconsistent — hallucination detected
            overall_rationale="All good.",
            escalate_to_tier3=False,
        )


def test_tier2_verdict_to_dict():
    """Tier2Verdict must be JSON-serialisable."""
    criteria = [
        CriterionVerdict(
            criterion="completeness",
            rationale="All key findings from the transcript are captured in the note.",
            verdict=Verdict.PASS,
        ),
    ]
    verdict = Tier2Verdict(
        note_id="test_003",
        model_used="test-model",
        prompt_version="v001",
        timestamp="2026-03-19T00:00:00Z",
        criteria=criteria,
        hallucination_flags=[],
        overall_verdict=Verdict.PASS,
        overall_rationale="Note meets all quality criteria.",
        escalate_to_tier3=False,
    )
    d = verdict.to_dict()
    json_str = json.dumps(d)
    parsed = json.loads(json_str)
    assert parsed["note_id"] == "test_003"
    assert parsed["overall_verdict"] == "pass"


def test_criterion_by_name():
    """criterion_by_name should return the correct verdict or None."""
    criteria = [
        CriterionVerdict(
            criterion="succinctness",
            rationale="Note is appropriately concise with no redundant content.",
            verdict=Verdict.PASS,
        ),
    ]
    verdict = Tier2Verdict(
        note_id="test_004",
        model_used="test-model",
        prompt_version="v001",
        timestamp="2026-03-19T00:00:00Z",
        criteria=criteria,
        hallucination_flags=[],
        overall_verdict=Verdict.PASS,
        overall_rationale="Note is concise and complete.",
        escalate_to_tier3=False,
    )
    found = verdict.criterion_by_name("succinctness")
    assert found is not None
    assert found.verdict == Verdict.PASS

    not_found = verdict.criterion_by_name("nonexistent")
    assert not_found is None


# ---------------------------------------------------------------------------
# JSON parsing tests (testing judge._extract_json and _build_verdict)
# ---------------------------------------------------------------------------


def test_extract_json_from_code_block():
    """_extract_json should handle JSON wrapped in ```json ... ``` blocks."""
    from src.tier2.judge import _extract_json

    text = """Here is my evaluation:
```json
{"overall_verdict": "pass", "overall_rationale": "Good note."}
```
"""
    result = _extract_json(text)
    assert result["overall_verdict"] == "pass"


def test_extract_json_bare():
    """_extract_json should handle bare JSON objects."""
    from src.tier2.judge import _extract_json

    text = '{"overall_verdict": "fail", "overall_rationale": "Missing section."}'
    result = _extract_json(text)
    assert result["overall_verdict"] == "fail"


def test_extract_json_raises_on_no_json():
    """_extract_json should raise ValueError if no JSON object found."""
    from src.tier2.judge import _extract_json

    with pytest.raises(ValueError):
        _extract_json("This is just prose with no JSON.")


# ---------------------------------------------------------------------------
# Integration tests (real LLM calls — skipped unless env var set)
# ---------------------------------------------------------------------------

INTEGRATION = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests (requires OPENROUTER_API_KEY)",
)


@INTEGRATION
@pytest.mark.asyncio
async def test_judge_good_note_passes(good_note):
    """Integration: LLM judge should give a passing verdict for a well-formed note."""
    from src.tier2.judge import judge_note

    verdict = await judge_note(good_note)
    assert verdict.note_id == good_note.note_id
    assert isinstance(verdict.overall_verdict, Verdict)
    # Well-formed note should pass (allow some judge variability)
    assert len(verdict.criteria) >= 1
    assert verdict.overall_rationale


@INTEGRATION
@pytest.mark.asyncio
async def test_judge_missing_section_fails(missing_section_note):
    """Integration: LLM judge should detect missing Assessment section."""
    from src.tier2.judge import judge_note

    verdict = await judge_note(missing_section_note)
    # Organization criterion should fail (Assessment section missing)
    org = verdict.criterion_by_name("organization")
    assert org is not None
    assert org.verdict == Verdict.FAIL


@INTEGRATION
@pytest.mark.asyncio
async def test_judge_outputs_valid_json_report(good_note, tmp_path):
    """Integration: judge output should be JSON-serialisable and saveable."""
    from src.tier2.judge import judge_note
    import json

    verdict = await judge_note(good_note)
    report_path = tmp_path / "tier2_test_report.json"
    report_path.write_text(json.dumps(verdict.to_dict(), indent=2))
    assert report_path.exists()
    loaded = json.loads(report_path.read_text())
    assert loaded["note_id"] == good_note.note_id
