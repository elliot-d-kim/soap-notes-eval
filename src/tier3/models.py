"""Pydantic models and SQLite data-access layer for Tier 3 expert review.

Stores expert review sessions: each session references a note_id and contains
per-criterion expert decisions (accept/reject/modify) with reasoning traces,
plus diff metadata against the original Tier 2 judge output.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExpertDecision(str, Enum):
    accept = "accept"
    reject = "reject"
    modify = "modify"


# ---------------------------------------------------------------------------
# Pydantic models — API layer
# ---------------------------------------------------------------------------

class CriterionReview(BaseModel):
    """Expert review of a single Tier 2 criterion verdict."""
    criterion: str
    original_verdict: str
    original_rationale: str
    expert_decision: ExpertDecision
    expert_verdict: str | None = None  # only if modified
    expert_reasoning: str = ""
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HallucinationReview(BaseModel):
    """Expert review of a single hallucination flag."""
    entity: str
    original_claim: str
    original_grounding_verdict: str
    expert_decision: ExpertDecision
    expert_reasoning: str = ""
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewSession(BaseModel):
    """A complete expert review session for one note."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    note_id: str
    reviewer_name: str = "Expert Reviewer"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    criteria_reviews: list[CriterionReview] = []
    hallucination_reviews: list[HallucinationReview] = []
    overall_expert_verdict: str | None = None
    overall_expert_reasoning: str = ""
    status: str = "in_progress"  # in_progress | completed


class ReviewSessionCreate(BaseModel):
    """Request body for creating a review session."""
    note_id: str
    reviewer_name: str = "Expert Reviewer"


class CriterionReviewUpdate(BaseModel):
    """Request body for updating a criterion review."""
    expert_decision: ExpertDecision
    expert_verdict: str | None = None
    expert_reasoning: str = ""


class HallucinationReviewUpdate(BaseModel):
    """Request body for updating a hallucination review."""
    expert_decision: ExpertDecision
    expert_reasoning: str = ""


class OverallVerdictUpdate(BaseModel):
    """Request body for updating the overall expert verdict."""
    overall_expert_verdict: str
    overall_expert_reasoning: str = ""
    status: str = "in_progress"


class DiffEntry(BaseModel):
    """A single diff between expert and judge output."""
    field: str
    criterion: str
    judge_value: str
    expert_value: str
    change_type: str  # "verdict_changed" | "reasoning_added" | "rejected" | "accepted"


class ReviewExport(BaseModel):
    """Export format for judge prompt refinement and meta-eval calibration."""
    session: ReviewSession
    source_data: dict[str, Any]
    tier1_report: dict[str, Any] | None
    tier2_report: dict[str, Any] | None
    diffs: list[DiffEntry]
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# SQLite data-access layer
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).resolve().parent / "reviews.db"


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS review_sessions (
            id TEXT PRIMARY KEY,
            note_id TEXT NOT NULL,
            reviewer_name TEXT NOT NULL DEFAULT 'Expert Reviewer',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            overall_expert_verdict TEXT,
            overall_expert_reasoning TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'in_progress'
        );

        CREATE TABLE IF NOT EXISTS criterion_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
            criterion TEXT NOT NULL,
            original_verdict TEXT NOT NULL,
            original_rationale TEXT NOT NULL DEFAULT '',
            expert_decision TEXT NOT NULL,
            expert_verdict TEXT,
            expert_reasoning TEXT DEFAULT '',
            modified_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hallucination_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
            entity TEXT NOT NULL,
            original_claim TEXT NOT NULL,
            original_grounding_verdict TEXT NOT NULL,
            expert_decision TEXT NOT NULL,
            expert_reasoning TEXT DEFAULT '',
            modified_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def save_session(session: ReviewSession) -> None:
    """Insert or replace a full review session."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO review_sessions
           (id, note_id, reviewer_name, created_at, updated_at,
            overall_expert_verdict, overall_expert_reasoning, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session.id, session.note_id, session.reviewer_name,
         session.created_at.isoformat(), now,
         session.overall_expert_verdict, session.overall_expert_reasoning,
         session.status),
    )
    # Clear and re-insert criterion reviews
    conn.execute("DELETE FROM criterion_reviews WHERE session_id = ?", (session.id,))
    for cr in session.criteria_reviews:
        conn.execute(
            """INSERT INTO criterion_reviews
               (session_id, criterion, original_verdict, original_rationale,
                expert_decision, expert_verdict, expert_reasoning, modified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session.id, cr.criterion, cr.original_verdict, cr.original_rationale,
             cr.expert_decision, cr.expert_verdict, cr.expert_reasoning,
             cr.modified_at.isoformat()),
        )
    # Clear and re-insert hallucination reviews
    conn.execute("DELETE FROM hallucination_reviews WHERE session_id = ?", (session.id,))
    for hr in session.hallucination_reviews:
        conn.execute(
            """INSERT INTO hallucination_reviews
               (session_id, entity, original_claim, original_grounding_verdict,
                expert_decision, expert_reasoning, modified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session.id, hr.entity, hr.original_claim, hr.original_grounding_verdict,
             hr.expert_decision, hr.expert_reasoning, hr.modified_at.isoformat()),
        )
    conn.commit()
    conn.close()


def load_session(session_id: str) -> ReviewSession | None:
    """Load a review session by ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM review_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None

    criteria = conn.execute(
        "SELECT * FROM criterion_reviews WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()

    hallucinations = conn.execute(
        "SELECT * FROM hallucination_reviews WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()

    conn.close()

    return ReviewSession(
        id=row["id"],
        note_id=row["note_id"],
        reviewer_name=row["reviewer_name"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        overall_expert_verdict=row["overall_expert_verdict"],
        overall_expert_reasoning=row["overall_expert_reasoning"] or "",
        status=row["status"],
        criteria_reviews=[
            CriterionReview(
                criterion=c["criterion"],
                original_verdict=c["original_verdict"],
                original_rationale=c["original_rationale"] or "",
                expert_decision=c["expert_decision"],
                expert_verdict=c["expert_verdict"],
                expert_reasoning=c["expert_reasoning"] or "",
                modified_at=datetime.fromisoformat(c["modified_at"]),
            )
            for c in criteria
        ],
        hallucination_reviews=[
            HallucinationReview(
                entity=h["entity"],
                original_claim=h["original_claim"],
                original_grounding_verdict=h["original_grounding_verdict"],
                expert_decision=h["expert_decision"],
                expert_reasoning=h["expert_reasoning"] or "",
                modified_at=datetime.fromisoformat(h["modified_at"]),
            )
            for h in hallucinations
        ],
    )


def list_sessions() -> list[dict[str, Any]]:
    """List all review sessions (summary only)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, note_id, reviewer_name, status, created_at, updated_at "
        "FROM review_sessions ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id: str) -> bool:
    """Delete a review session. Returns True if deleted."""
    conn = get_db()
    cursor = conn.execute("DELETE FROM review_sessions WHERE id = ?", (session_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
