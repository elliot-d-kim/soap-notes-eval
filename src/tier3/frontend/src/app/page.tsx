"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { NoteData, ReviewSession, SessionSummary } from "@/lib/api";
import { TranscriptPanel } from "@/components/transcript-panel";
import { SoapNotePanel } from "@/components/soap-note-panel";
import { ReviewPanel } from "@/components/review-panel";

export default function Home() {
  // State
  const [notes, setNotes] = useState<Array<{ note_id: string; source_dataset: string; transcript: string; note_text: string }>>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [noteData, setNoteData] = useState<NoteData | null>(null);
  const [currentSession, setCurrentSession] = useState<ReviewSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    async function init() {
      try {
        const [notesData, sessionsData] = await Promise.all([
          api.listNotes(),
          api.listSessions(),
        ]);
        setNotes(notesData);
        setSessions(sessionsData);
        // Auto-select first note
        if (notesData.length > 0) {
          setSelectedNoteId(notesData[0].note_id);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to connect to API");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // Load note data when selection changes
  useEffect(() => {
    if (!selectedNoteId) return;
    setNoteData(null);
    api.getNote(selectedNoteId).then(setNoteData).catch(console.error);

    // Check if there's an existing session for this note
    const existingSession = sessions.find((s) => s.note_id === selectedNoteId);
    if (existingSession) {
      api.getSession(existingSession.id).then(setCurrentSession).catch(console.error);
    } else {
      setCurrentSession(null);
    }
  }, [selectedNoteId, sessions]);

  const handleStartReview = useCallback(async () => {
    if (!selectedNoteId) return;
    try {
      const session = await api.createSession(selectedNoteId);
      setCurrentSession(session);
      setSessions((prev) => [
        {
          id: session.id,
          note_id: session.note_id,
          reviewer_name: session.reviewer_name,
          status: session.status,
          created_at: session.created_at,
          updated_at: session.updated_at,
        },
        ...prev,
      ]);
    } catch (e) {
      console.error("Failed to create session:", e);
    }
  }, [selectedNoteId]);

  const handleExport = useCallback(async () => {
    if (!currentSession) return;
    try {
      const data = await api.exportSession(currentSession.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `review_${currentSession.note_id}_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed:", e);
    }
  }, [currentSession]);

  const handleDeleteSession = useCallback(async () => {
    if (!currentSession) return;
    try {
      await api.deleteSession(currentSession.id);
      setCurrentSession(null);
      setSessions((prev) => prev.filter((s) => s.id !== currentSession.id));
    } catch (e) {
      console.error("Delete failed:", e);
    }
  }, [currentSession]);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-[var(--color-accent-blue)] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[var(--color-text-muted)] text-sm font-mono">
            Connecting to review backend...
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-[var(--color-accent-red)] text-3xl mb-3">⚠</div>
          <p className="text-[var(--color-text-primary)] font-semibold mb-2">
            Cannot connect to API
          </p>
          <p className="text-[var(--color-text-muted)] text-sm mb-4">{error}</p>
          <p className="text-[var(--color-text-muted)] text-xs font-mono">
            Start the backend: uv run uvicorn src.tier3.app:app --reload --port 8000
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="h-12 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-secondary)] flex items-center px-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[var(--color-accent-green)] animate-pulse" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              SOAP Expert Review
            </span>
          </div>
          <span className="text-[var(--color-border-default)]">│</span>
          <span className="text-[10px] font-mono text-[var(--color-text-muted)]">Tier 3</span>
        </div>

        <div className="flex-1" />

        {/* Note selector */}
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-mono text-[var(--color-text-muted)] uppercase">
            Note:
          </label>
          <select
            value={selectedNoteId || ""}
            onChange={(e) => setSelectedNoteId(e.target.value)}
            className="bg-[var(--color-bg-tertiary)] border border-[var(--color-border-default)] rounded px-2 py-1 text-xs font-mono text-[var(--color-text-primary)] min-w-[160px]"
          >
            {notes.map((n) => (
              <option key={n.note_id} value={n.note_id}>
                {n.note_id} ({n.source_dataset})
              </option>
            ))}
          </select>

          {currentSession ? (
            <button
              onClick={handleDeleteSession}
              className="px-2.5 py-1 rounded text-[11px] font-semibold border border-[var(--color-accent-red)]/30 text-[var(--color-accent-red)] hover:bg-[var(--color-accent-red-dim)] transition-colors cursor-pointer"
            >
              Reset Review
            </button>
          ) : (
            <button
              onClick={handleStartReview}
              className="px-2.5 py-1 rounded text-[11px] font-semibold bg-[var(--color-accent-blue-dim)] text-[var(--color-accent-blue)] border border-[var(--color-accent-blue)]/30 hover:bg-[var(--color-accent-blue)]/20 transition-colors cursor-pointer"
            >
              Start Review
            </button>
          )}
        </div>
      </header>

      {/* Three-column layout */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left: Transcript */}
        <div className="w-1/3 border-r border-[var(--color-border-subtle)] p-2 overflow-hidden flex flex-col">
          <TranscriptPanel
            transcript={noteData?.transcript || ""}
            noteId={selectedNoteId || ""}
            sourceDataset={noteData?.source_dataset || ""}
          />
        </div>

        {/* Center: SOAP Note */}
        <div className="w-1/3 border-r border-[var(--color-border-subtle)] p-2 overflow-hidden flex flex-col">
          <SoapNotePanel
            noteText={noteData?.note_text || ""}
            tier1Report={noteData?.tier1_report || null}
          />
        </div>

        {/* Right: Review / Annotations */}
        <div className="w-1/3 p-2 overflow-hidden flex flex-col">
          {currentSession ? (
            <ReviewPanel
              session={currentSession}
              tier2Report={noteData?.tier2_report || null}
              onSessionUpdate={setCurrentSession}
              onExport={handleExport}
            />
          ) : (
            <div className="panel h-full flex items-center justify-center">
              <div className="text-center max-w-xs">
                <div className="text-4xl mb-3 opacity-20">📋</div>
                <p className="text-[var(--color-text-secondary)] text-sm mb-2">
                  No active review session
                </p>
                <p className="text-[var(--color-text-muted)] text-xs mb-4">
                  Select a note and click &ldquo;Start Review&rdquo; to begin annotating
                  Tier 2 judge verdicts.
                </p>
                {noteData?.tier2_report?.escalate_to_tier3 && (
                  <div className="verdict-fail text-[11px] font-mono px-2 py-1 rounded inline-block">
                    ⚑ Flagged for Tier 3 review
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Status bar */}
      <footer className="h-6 border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-secondary)] flex items-center px-4 text-[10px] font-mono text-[var(--color-text-muted)] shrink-0">
        <span>{notes.length} notes available</span>
        <span className="mx-2">·</span>
        <span>{sessions.length} review session{sessions.length !== 1 ? "s" : ""}</span>
        {currentSession && (
          <>
            <span className="mx-2">·</span>
            <span>
              Reviewing: {currentSession.note_id} ({currentSession.status})
            </span>
          </>
        )}
        <div className="flex-1" />
        <span>FastAPI :8000 → Next.js :3000</span>
      </footer>
    </div>
  );
}
