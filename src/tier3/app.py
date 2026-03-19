"""Tier 3 — FastAPI backend for the Human Expert Review Interface.

Serves the review API and provides CRUD for expert annotations on Tier 2
judge verdicts. Loads source data (dialogues + SOAP notes) and tier1/tier2
reports, exposes them alongside review sessions.

Run:
    cd soap-notes-eval && uv run uvicorn src.tier3.app:app --reload --port 8000
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    CriterionReview,
    CriterionReviewUpdate,
    DiffEntry,
    ExpertDecision,
    HallucinationReview,
    HallucinationReviewUpdate,
    OverallVerdictUpdate,
    ReviewExport,
    ReviewSession,
    ReviewSessionCreate,
    delete_session,
    init_db,
    list_sessions,
    load_session,
    save_session,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "samples"
OUTPUT_DIR = PROJECT_ROOT / "output"

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SOAP Note Expert Review",
    description="Tier 3 human expert review interface for SOAP note evaluation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


# ---------------------------------------------------------------------------
# Helpers — load source data
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON file, returning None if missing."""
    if path.exists():
        return json.loads(path.read_text())
    return None


def _normalize_source(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize different dataset formats into a common shape."""
    transcript = (
        data.get("transcript")
        or data.get("patient_convo")
        or ""
    )
    note_text = (
        data.get("note_text")
        or data.get("soap_notes")
        or ""
    )
    note_id = data.get("note_id", "")
    return {
        "transcript": transcript,
        "note_text": note_text,
        "note_id": note_id,
        "raw": data,
    }


def _list_available_notes() -> list[dict[str, Any]]:
    """List all available sample notes with their source data."""
    notes = []
    for f in sorted(DATA_DIR.glob("*.json")):
        data = _load_json(f)
        if data is None:
            continue
        note_id = f.stem
        normalized = _normalize_source(data)
        normalized["note_id"] = note_id
        normalized["source_dataset"] = note_id.split("_")[0]
        notes.append(normalized)
    return notes


# ---------------------------------------------------------------------------
# API: Source data
# ---------------------------------------------------------------------------


@app.get("/api/notes")
def get_notes() -> list[dict[str, Any]]:
    """List all available notes."""
    return _list_available_notes()


@app.get("/api/notes/{note_id}")
def get_note(note_id: str) -> dict[str, Any]:
    """Get a single note with source data, tier1, and tier2 reports."""
    source_path = DATA_DIR / f"{note_id}.json"
    source = _load_json(source_path)
    if source is None:
        raise HTTPException(404, f"Note '{note_id}' not found")

    normalized = _normalize_source(source)
    normalized["note_id"] = note_id
    normalized["source_dataset"] = note_id.split("_")[0]

    # Try to load tier1 / tier2 reports (could be per-note or sample)
    tier1 = _load_json(OUTPUT_DIR / f"tier1_{note_id}.json")
    if tier1 is None:
        tier1 = _load_json(OUTPUT_DIR / "tier1_sample_report.json")

    tier2 = _load_json(OUTPUT_DIR / f"tier2_{note_id}.json")
    if tier2 is None:
        tier2 = _load_json(OUTPUT_DIR / "tier2_sample_report.json")

    return {
        **normalized,
        "tier1_report": tier1,
        "tier2_report": tier2,
    }


# ---------------------------------------------------------------------------
# API: Review sessions CRUD
# ---------------------------------------------------------------------------


@app.get("/api/sessions")
def get_sessions() -> list[dict[str, Any]]:
    """List all review sessions."""
    return list_sessions()


@app.post("/api/sessions", status_code=201)
def create_session(body: ReviewSessionCreate) -> ReviewSession:
    """Create a new review session for a note, pre-populated with Tier 2 verdicts."""
    # Verify note exists
    source_path = DATA_DIR / f"{body.note_id}.json"
    if not source_path.exists():
        raise HTTPException(404, f"Note '{body.note_id}' not found")

    # Load tier2 report to pre-populate
    tier2 = _load_json(OUTPUT_DIR / f"tier2_{body.note_id}.json")
    if tier2 is None:
        tier2 = _load_json(OUTPUT_DIR / "tier2_sample_report.json")

    criteria_reviews = []
    hallucination_reviews = []

    if tier2:
        for c in tier2.get("criteria", []):
            criteria_reviews.append(CriterionReview(
                criterion=c["criterion"],
                original_verdict=c["verdict"],
                original_rationale=c.get("rationale", ""),
                expert_decision=ExpertDecision.accept,
                expert_reasoning="",
            ))
        for h in tier2.get("hallucination_flags", []):
            hallucination_reviews.append(HallucinationReview(
                entity=h["entity"],
                original_claim=h["claim_in_note"],
                original_grounding_verdict=h["grounding_verdict"],
                expert_decision=ExpertDecision.accept,
                expert_reasoning="",
            ))

    session = ReviewSession(
        note_id=body.note_id,
        reviewer_name=body.reviewer_name,
        criteria_reviews=criteria_reviews,
        hallucination_reviews=hallucination_reviews,
    )
    save_session(session)
    return session


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> ReviewSession:
    """Get a review session by ID."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return session


@app.delete("/api/sessions/{session_id}", status_code=204)
def remove_session(session_id: str) -> None:
    """Delete a review session."""
    if not delete_session(session_id):
        raise HTTPException(404, f"Session '{session_id}' not found")


# ---------------------------------------------------------------------------
# API: Criterion reviews
# ---------------------------------------------------------------------------


@app.put("/api/sessions/{session_id}/criteria/{criterion}")
def update_criterion(
    session_id: str, criterion: str, body: CriterionReviewUpdate
) -> ReviewSession:
    """Update expert decision for a specific criterion."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    found = False
    for cr in session.criteria_reviews:
        if cr.criterion == criterion:
            cr.expert_decision = body.expert_decision
            cr.expert_verdict = body.expert_verdict
            cr.expert_reasoning = body.expert_reasoning
            cr.modified_at = datetime.now(timezone.utc)
            found = True
            break

    if not found:
        raise HTTPException(404, f"Criterion '{criterion}' not found in session")

    session.updated_at = datetime.now(timezone.utc)
    save_session(session)
    return session


@app.delete("/api/sessions/{session_id}/criteria/{criterion}")
def delete_criterion(session_id: str, criterion: str) -> ReviewSession:
    """Remove a criterion review from the session."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    original_len = len(session.criteria_reviews)
    session.criteria_reviews = [
        cr for cr in session.criteria_reviews if cr.criterion != criterion
    ]
    if len(session.criteria_reviews) == original_len:
        raise HTTPException(404, f"Criterion '{criterion}' not found")

    session.updated_at = datetime.now(timezone.utc)
    save_session(session)
    return session


# ---------------------------------------------------------------------------
# API: Hallucination reviews
# ---------------------------------------------------------------------------


@app.put("/api/sessions/{session_id}/hallucinations/{entity}")
def update_hallucination(
    session_id: str, entity: str, body: HallucinationReviewUpdate
) -> ReviewSession:
    """Update expert decision for a hallucination flag."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    found = False
    for hr in session.hallucination_reviews:
        if hr.entity == entity:
            hr.expert_decision = body.expert_decision
            hr.expert_reasoning = body.expert_reasoning
            hr.modified_at = datetime.now(timezone.utc)
            found = True
            break

    if not found:
        raise HTTPException(404, f"Hallucination '{entity}' not found")

    session.updated_at = datetime.now(timezone.utc)
    save_session(session)
    return session


# ---------------------------------------------------------------------------
# API: Overall verdict
# ---------------------------------------------------------------------------


@app.put("/api/sessions/{session_id}/verdict")
def update_verdict(session_id: str, body: OverallVerdictUpdate) -> ReviewSession:
    """Update the overall expert verdict."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    session.overall_expert_verdict = body.overall_expert_verdict
    session.overall_expert_reasoning = body.overall_expert_reasoning
    session.status = body.status
    session.updated_at = datetime.now(timezone.utc)
    save_session(session)
    return session


# ---------------------------------------------------------------------------
# API: Diff computation & export
# ---------------------------------------------------------------------------


def _compute_diffs(session: ReviewSession) -> list[DiffEntry]:
    """Compute diffs between expert decisions and original judge output."""
    diffs: list[DiffEntry] = []
    for cr in session.criteria_reviews:
        if cr.expert_decision == ExpertDecision.reject:
            diffs.append(DiffEntry(
                field="verdict",
                criterion=cr.criterion,
                judge_value=cr.original_verdict,
                expert_value="rejected",
                change_type="rejected",
            ))
        elif cr.expert_decision == ExpertDecision.modify:
            diffs.append(DiffEntry(
                field="verdict",
                criterion=cr.criterion,
                judge_value=cr.original_verdict,
                expert_value=cr.expert_verdict or cr.original_verdict,
                change_type="verdict_changed",
            ))
        elif cr.expert_decision == ExpertDecision.accept and cr.expert_reasoning:
            diffs.append(DiffEntry(
                field="reasoning",
                criterion=cr.criterion,
                judge_value=cr.original_rationale,
                expert_value=cr.expert_reasoning,
                change_type="reasoning_added",
            ))
    return diffs


@app.get("/api/sessions/{session_id}/diffs")
def get_diffs(session_id: str) -> list[DiffEntry]:
    """Get diffs between expert and judge for a session."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return _compute_diffs(session)


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str) -> ReviewExport:
    """Export a review session with full context for calibration."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    source = _load_json(DATA_DIR / f"{session.note_id}.json") or {}
    tier1 = _load_json(OUTPUT_DIR / f"tier1_{session.note_id}.json")
    if tier1 is None:
        tier1 = _load_json(OUTPUT_DIR / "tier1_sample_report.json")
    tier2 = _load_json(OUTPUT_DIR / f"tier2_{session.note_id}.json")
    if tier2 is None:
        tier2 = _load_json(OUTPUT_DIR / "tier2_sample_report.json")

    return ReviewExport(
        session=session,
        source_data=source,
        tier1_report=tier1,
        tier2_report=tier2,
        diffs=_compute_diffs(session),
    )
