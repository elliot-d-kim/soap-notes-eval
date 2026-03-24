/**
 * Demo API — in-memory implementation of the same interface as api.ts.
 * Used when deployed to Vercel (no FastAPI backend).
 * Review sessions persist in memory for the duration of the page session.
 */

import demoNotes from "@/data/demo-notes.json";
import demoTier1 from "@/data/demo-tier1.json";
import demoTier2 from "@/data/demo-tier2.json";
import type {
  NoteData,
  Tier1Report,
  Tier2Report,
  ReviewSession,
  SessionSummary,
  CriterionReview,
  HallucinationReview,
  DiffEntry,
} from "./api";

// --- In-memory session store ---
const sessions: Map<string, ReviewSession> = new Map();
let sessionCounter = 0;

function now(): string {
  return new Date().toISOString();
}

// --- Demo API ---

export const demoApi = {
  listNotes: async (): Promise<
    Array<{
      note_id: string;
      source_dataset: string;
      transcript: string;
      note_text: string;
    }>
  > => {
    return demoNotes;
  },

  getNote: async (id: string): Promise<NoteData> => {
    const note = demoNotes.find((n) => n.note_id === id);
    if (!note) throw new Error(`Note '${id}' not found`);

    // Use the tier1 report if the note matches, otherwise null
    const tier1: Tier1Report | null =
      (demoTier1 as Tier1Report).note_id === id
        ? (demoTier1 as Tier1Report)
        : null;

    // Use the tier2 sample report for all notes (demo purposes)
    const tier2: Tier2Report | null = demoTier2 as Tier2Report;

    return {
      note_id: note.note_id,
      source_dataset: note.source_dataset,
      transcript: note.transcript,
      note_text: note.note_text,
      raw: {},
      tier1_report: tier1,
      tier2_report: tier2,
    };
  },

  listSessions: async (): Promise<SessionSummary[]> => {
    return Array.from(sessions.values()).map((s) => ({
      id: s.id,
      note_id: s.note_id,
      reviewer_name: s.reviewer_name,
      status: s.status,
      created_at: s.created_at,
      updated_at: s.updated_at,
    }));
  },

  createSession: async (
    noteId: string,
    reviewerName = "Expert Reviewer"
  ): Promise<ReviewSession> => {
    const tier2 = demoTier2 as Tier2Report;
    const criteria_reviews: CriterionReview[] = (tier2.criteria || []).map(
      (c) => ({
        criterion: c.criterion,
        original_verdict: c.verdict,
        original_rationale: c.rationale || "",
        expert_decision: "accept" as const,
        expert_verdict: null,
        expert_reasoning: "",
        modified_at: now(),
      })
    );
    const hallucination_reviews: HallucinationReview[] = (
      tier2.hallucination_flags || []
    ).map((h) => ({
      entity: h.entity,
      original_claim: h.claim_in_note,
      original_grounding_verdict: h.grounding_verdict,
      expert_decision: "accept" as const,
      expert_reasoning: "",
      modified_at: now(),
    }));

    const session: ReviewSession = {
      id: `demo-${++sessionCounter}`,
      note_id: noteId,
      reviewer_name: reviewerName,
      created_at: now(),
      updated_at: now(),
      criteria_reviews,
      hallucination_reviews,
      overall_expert_verdict: null,
      overall_expert_reasoning: "",
      status: "in_progress",
    };
    sessions.set(session.id, session);
    return session;
  },

  getSession: async (id: string): Promise<ReviewSession> => {
    const s = sessions.get(id);
    if (!s) throw new Error(`Session '${id}' not found`);
    return s;
  },

  deleteSession: async (id: string): Promise<void> => {
    sessions.delete(id);
  },

  updateCriterion: async (
    sessionId: string,
    criterion: string,
    data: {
      expert_decision: string;
      expert_verdict?: string | null;
      expert_reasoning?: string;
    }
  ): Promise<ReviewSession> => {
    const session = sessions.get(sessionId);
    if (!session) throw new Error(`Session '${sessionId}' not found`);

    const cr = session.criteria_reviews.find(
      (c) => c.criterion === criterion
    );
    if (!cr) throw new Error(`Criterion '${criterion}' not found`);

    cr.expert_decision = data.expert_decision as "accept" | "reject" | "modify";
    cr.expert_verdict = data.expert_verdict ?? cr.expert_verdict;
    cr.expert_reasoning = data.expert_reasoning ?? cr.expert_reasoning;
    cr.modified_at = now();
    session.updated_at = now();
    return session;
  },

  deleteCriterion: async (
    sessionId: string,
    criterion: string
  ): Promise<ReviewSession> => {
    const session = sessions.get(sessionId);
    if (!session) throw new Error(`Session '${sessionId}' not found`);
    session.criteria_reviews = session.criteria_reviews.filter(
      (c) => c.criterion !== criterion
    );
    session.updated_at = now();
    return session;
  },

  updateHallucination: async (
    sessionId: string,
    entity: string,
    data: {
      expert_decision: string;
      expert_reasoning?: string;
    }
  ): Promise<ReviewSession> => {
    const session = sessions.get(sessionId);
    if (!session) throw new Error(`Session '${sessionId}' not found`);

    const hr = session.hallucination_reviews.find((h) => h.entity === entity);
    if (!hr) throw new Error(`Hallucination '${entity}' not found`);

    hr.expert_decision = data.expert_decision as "accept" | "reject" | "modify";
    hr.expert_reasoning = data.expert_reasoning ?? hr.expert_reasoning;
    hr.modified_at = now();
    session.updated_at = now();
    return session;
  },

  updateVerdict: async (
    sessionId: string,
    data: {
      overall_expert_verdict: string;
      overall_expert_reasoning?: string;
      status?: string;
    }
  ): Promise<ReviewSession> => {
    const session = sessions.get(sessionId);
    if (!session) throw new Error(`Session '${sessionId}' not found`);

    session.overall_expert_verdict = data.overall_expert_verdict;
    session.overall_expert_reasoning =
      data.overall_expert_reasoning ?? session.overall_expert_reasoning;
    session.status = data.status ?? session.status;
    session.updated_at = now();
    return session;
  },

  getDiffs: async (sessionId: string): Promise<DiffEntry[]> => {
    const session = sessions.get(sessionId);
    if (!session) throw new Error(`Session '${sessionId}' not found`);

    const diffs: DiffEntry[] = [];
    for (const cr of session.criteria_reviews) {
      if (cr.expert_decision === "reject") {
        diffs.push({
          field: "verdict",
          criterion: cr.criterion,
          judge_value: cr.original_verdict,
          expert_value: "rejected",
          change_type: "rejected",
        });
      } else if (cr.expert_decision === "modify") {
        diffs.push({
          field: "verdict",
          criterion: cr.criterion,
          judge_value: cr.original_verdict,
          expert_value: cr.expert_verdict || cr.original_verdict,
          change_type: "verdict_changed",
        });
      } else if (cr.expert_decision === "accept" && cr.expert_reasoning) {
        diffs.push({
          field: "reasoning",
          criterion: cr.criterion,
          judge_value: cr.original_rationale,
          expert_value: cr.expert_reasoning,
          change_type: "reasoning_added",
        });
      }
    }
    return diffs;
  },

  exportSession: async (
    sessionId: string
  ): Promise<Record<string, unknown>> => {
    const session = sessions.get(sessionId);
    if (!session) throw new Error(`Session '${sessionId}' not found`);
    return {
      session,
      source_data: demoNotes.find((n) => n.note_id === session.note_id) || {},
      tier1_report: demoTier1,
      tier2_report: demoTier2,
      diffs: await demoApi.getDiffs(sessionId),
    };
  },
};
