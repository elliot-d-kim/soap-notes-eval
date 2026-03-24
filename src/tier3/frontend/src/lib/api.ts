/**
 * API client for the Tier 3 FastAPI backend.
 *
 * In demo mode (NEXT_PUBLIC_DEMO_MODE=true or no API_URL configured),
 * uses an in-memory implementation with bundled sample data.
 */

import { demoApi } from "./demo-api";

const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Types ---

export interface NoteData {
  note_id: string;
  source_dataset: string;
  transcript: string;
  note_text: string;
  raw: Record<string, unknown>;
  tier1_report: Tier1Report | null;
  tier2_report: Tier2Report | null;
}

export interface Tier1Report {
  note_id: string;
  passed: boolean;
  failure_types: string[];
  structure: {
    passed: boolean;
    checks: Array<{
      name: string;
      passed: boolean;
      details: string;
    }>;
  };
  entities: Record<string, {
    medications: string[];
    diagnoses: string[];
    procedures: string[];
    other: string[];
  }>;
}

export interface Tier2Report {
  note_id: string;
  model_used: string;
  prompt_version: string;
  criteria: Array<{
    criterion: string;
    rationale: string;
    verdict: string;
    evidence: string[];
  }>;
  hallucination_flags: Array<{
    entity: string;
    claim_in_note: string;
    grounding_verdict: string;
    explanation: string;
  }>;
  overall_verdict: string;
  overall_rationale: string;
  escalate_to_tier3: boolean;
}

export interface CriterionReview {
  criterion: string;
  original_verdict: string;
  original_rationale: string;
  expert_decision: "accept" | "reject" | "modify";
  expert_verdict: string | null;
  expert_reasoning: string;
  modified_at: string;
}

export interface HallucinationReview {
  entity: string;
  original_claim: string;
  original_grounding_verdict: string;
  expert_decision: "accept" | "reject" | "modify";
  expert_reasoning: string;
  modified_at: string;
}

export interface ReviewSession {
  id: string;
  note_id: string;
  reviewer_name: string;
  created_at: string;
  updated_at: string;
  criteria_reviews: CriterionReview[];
  hallucination_reviews: HallucinationReview[];
  overall_expert_verdict: string | null;
  overall_expert_reasoning: string;
  status: string;
}

export interface DiffEntry {
  field: string;
  criterion: string;
  judge_value: string;
  expert_value: string;
  change_type: string;
}

export interface SessionSummary {
  id: string;
  note_id: string;
  reviewer_name: string;
  status: string;
  created_at: string;
  updated_at: string;
}

// --- API calls ---

const liveApi = {
  // Notes
  listNotes: () => apiFetch<Array<{ note_id: string; source_dataset: string; transcript: string; note_text: string }>>("/api/notes"),
  getNote: (id: string) => apiFetch<NoteData>(`/api/notes/${id}`),

  // Sessions
  listSessions: () => apiFetch<SessionSummary[]>("/api/sessions"),
  createSession: (noteId: string, reviewerName = "Expert Reviewer") =>
    apiFetch<ReviewSession>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ note_id: noteId, reviewer_name: reviewerName }),
    }),
  getSession: (id: string) => apiFetch<ReviewSession>(`/api/sessions/${id}`),
  deleteSession: (id: string) =>
    apiFetch<void>(`/api/sessions/${id}`, { method: "DELETE" }),

  // Criterion reviews
  updateCriterion: (sessionId: string, criterion: string, data: {
    expert_decision: string;
    expert_verdict?: string | null;
    expert_reasoning?: string;
  }) =>
    apiFetch<ReviewSession>(`/api/sessions/${sessionId}/criteria/${criterion}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteCriterion: (sessionId: string, criterion: string) =>
    apiFetch<ReviewSession>(`/api/sessions/${sessionId}/criteria/${criterion}`, {
      method: "DELETE",
    }),

  // Hallucination reviews
  updateHallucination: (sessionId: string, entity: string, data: {
    expert_decision: string;
    expert_reasoning?: string;
  }) =>
    apiFetch<ReviewSession>(`/api/sessions/${sessionId}/hallucinations/${entity}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Overall verdict
  updateVerdict: (sessionId: string, data: {
    overall_expert_verdict: string;
    overall_expert_reasoning?: string;
    status?: string;
  }) =>
    apiFetch<ReviewSession>(`/api/sessions/${sessionId}/verdict`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Diffs & export
  getDiffs: (sessionId: string) =>
    apiFetch<DiffEntry[]>(`/api/sessions/${sessionId}/diffs`),
  exportSession: (sessionId: string) =>
    apiFetch<Record<string, unknown>>(`/api/sessions/${sessionId}/export`),
};

/**
 * Export the demo API in demo mode, or the live API otherwise.
 */
export const api = DEMO_MODE ? demoApi : liveApi;
