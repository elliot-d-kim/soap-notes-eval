"use client";

import { useState } from "react";
import type { ReviewSession, DiffEntry, Tier2Report } from "@/lib/api";
import { api } from "@/lib/api";

interface ReviewPanelProps {
  session: ReviewSession;
  tier2Report: Tier2Report | null;
  onSessionUpdate: (session: ReviewSession) => void;
  onExport: () => void;
}

type Decision = "accept" | "reject" | "modify";

const DECISION_STYLES: Record<Decision, { label: string; className: string; icon: string }> = {
  accept: {
    label: "Accept",
    className: "bg-[var(--color-accent-green-dim)] text-[var(--color-accent-green)] border-[var(--color-accent-green)]/30",
    icon: "✓",
  },
  reject: {
    label: "Reject",
    className: "bg-[var(--color-accent-red-dim)] text-[var(--color-accent-red)] border-[var(--color-accent-red)]/30",
    icon: "✕",
  },
  modify: {
    label: "Modify",
    className: "bg-[var(--color-accent-amber-dim)] text-[var(--color-accent-amber)] border-[var(--color-accent-amber)]/30",
    icon: "✎",
  },
};

export function ReviewPanel({ session, tier2Report, onSessionUpdate, onExport }: ReviewPanelProps) {
  const [diffs, setDiffs] = useState<DiffEntry[]>([]);
  const [showDiffs, setShowDiffs] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);

  const loadDiffs = async () => {
    const d = await api.getDiffs(session.id);
    setDiffs(d);
    setShowDiffs(true);
  };

  const handleCriterionUpdate = async (
    criterion: string,
    decision: Decision,
    expertVerdict?: string,
    reasoning?: string
  ) => {
    setSaving(criterion);
    try {
      const updated = await api.updateCriterion(session.id, criterion, {
        expert_decision: decision,
        expert_verdict: expertVerdict || null,
        expert_reasoning: reasoning || "",
      });
      onSessionUpdate(updated);
    } finally {
      setSaving(null);
    }
  };

  const handleCriterionDelete = async (criterion: string) => {
    setSaving(criterion);
    try {
      const updated = await api.deleteCriterion(session.id, criterion);
      onSessionUpdate(updated);
    } finally {
      setSaving(null);
    }
  };

  const handleHallucinationUpdate = async (
    entity: string,
    decision: Decision,
    reasoning?: string
  ) => {
    setSaving(entity);
    try {
      const updated = await api.updateHallucination(session.id, entity, {
        expert_decision: decision,
        expert_reasoning: reasoning || "",
      });
      onSessionUpdate(updated);
    } finally {
      setSaving(null);
    }
  };

  const handleOverallVerdict = async (verdict: string, reasoning: string, status: string) => {
    setSaving("overall");
    try {
      const updated = await api.updateVerdict(session.id, {
        overall_expert_verdict: verdict,
        overall_expert_reasoning: reasoning,
        status,
      });
      onSessionUpdate(updated);
    } finally {
      setSaving(null);
    }
  };

  const modifiedCount = session.criteria_reviews.filter(
    (c) => c.expert_decision !== "accept"
  ).length;

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header flex items-center justify-between">
        <span>Expert Review</span>
        <div className="flex items-center gap-2">
          {modifiedCount > 0 && (
            <span className="text-[10px] font-mono verdict-modified px-1.5 py-0.5 rounded normal-case tracking-normal">
              {modifiedCount} change{modifiedCount > 1 ? "s" : ""}
            </span>
          )}
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded normal-case tracking-normal ${
              session.status === "completed"
                ? "verdict-pass"
                : "bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)]"
            }`}
          >
            {session.status}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Tier 2 overall context */}
        {tier2Report && (
          <div className="px-4 py-3 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-tertiary)]/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                Judge Verdict
              </span>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                  tier2Report.overall_verdict === "pass" ? "verdict-pass" : "verdict-fail"
                }`}
              >
                {tier2Report.overall_verdict.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-[var(--color-text-secondary)] font-clinical leading-relaxed">
              {tier2Report.overall_rationale}
            </p>
            <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-[var(--color-text-muted)]">
              <span>Model: {tier2Report.model_used}</span>
              <span>Prompt: {tier2Report.prompt_version}</span>
            </div>
          </div>
        )}

        {/* Criteria reviews */}
        <div className="px-4 py-3 space-y-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
            Criteria ({session.criteria_reviews.length})
          </div>

          {session.criteria_reviews.map((cr) => (
            <CriterionCard
              key={cr.criterion}
              review={cr}
              saving={saving === cr.criterion}
              onUpdate={(decision, verdict, reasoning) =>
                handleCriterionUpdate(cr.criterion, decision, verdict, reasoning)
              }
              onDelete={() => handleCriterionDelete(cr.criterion)}
            />
          ))}
        </div>

        {/* Hallucination reviews */}
        {session.hallucination_reviews.length > 0 && (
          <div className="px-4 py-3 space-y-3 border-t border-[var(--color-border-subtle)]">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Hallucination Flags ({session.hallucination_reviews.length})
            </div>

            {session.hallucination_reviews.map((hr) => (
              <HallucinationCard
                key={hr.entity}
                review={hr}
                saving={saving === hr.entity}
                onUpdate={(decision, reasoning) =>
                  handleHallucinationUpdate(hr.entity, decision, reasoning)
                }
              />
            ))}
          </div>
        )}

        {/* Overall expert verdict */}
        <div className="px-4 py-3 border-t border-[var(--color-border-subtle)]">
          <OverallVerdictForm
            session={session}
            saving={saving === "overall"}
            onSave={handleOverallVerdict}
          />
        </div>

        {/* Diffs section */}
        <div className="px-4 py-3 border-t border-[var(--color-border-subtle)]">
          <button
            onClick={loadDiffs}
            className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-accent-blue)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
          >
            {showDiffs ? "Refresh Diffs" : "Show Diffs vs Judge"}
          </button>
          {showDiffs && diffs.length > 0 && (
            <div className="mt-2 space-y-2">
              {diffs.map((d, i) => (
                <div
                  key={i}
                  className="rounded border border-[var(--color-border-subtle)] px-3 py-2 bg-[var(--color-bg-primary)]/50"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-mono font-semibold text-[var(--color-accent-amber)]">
                      {d.criterion}
                    </span>
                    <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
                      {d.change_type}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                    <div>
                      <span className="text-[var(--color-accent-red)] text-[10px]">− Judge:</span>
                      <span className="text-[var(--color-text-secondary)] ml-1">{d.judge_value}</span>
                    </div>
                    <div>
                      <span className="text-[var(--color-accent-green)] text-[10px]">+ Expert:</span>
                      <span className="text-[var(--color-text-primary)] ml-1">{d.expert_value}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {showDiffs && diffs.length === 0 && (
            <p className="mt-2 text-[11px] text-[var(--color-text-muted)] italic">
              No differences — all judge verdicts accepted as-is.
            </p>
          )}
        </div>
      </div>

      {/* Footer actions */}
      <div className="px-4 py-3 border-t border-[var(--color-border-subtle)] flex items-center gap-2">
        <button
          onClick={onExport}
          className="flex-1 px-3 py-2 rounded-md text-[12px] font-semibold uppercase tracking-wider bg-[var(--color-accent-blue-dim)] text-[var(--color-accent-blue)] border border-[var(--color-accent-blue)]/30 hover:bg-[var(--color-accent-blue)]/20 transition-colors cursor-pointer"
        >
          Export Review JSON
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CriterionCard({
  review,
  saving,
  onUpdate,
  onDelete,
}: {
  review: ReviewSession["criteria_reviews"][0];
  saving: boolean;
  onUpdate: (decision: Decision, verdict?: string, reasoning?: string) => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [reasoning, setReasoning] = useState(review.expert_reasoning);
  const [modifiedVerdict, setModifiedVerdict] = useState(review.expert_verdict || "");

  const style = DECISION_STYLES[review.expert_decision as Decision] || DECISION_STYLES.accept;

  return (
    <div
      className={`rounded-md border overflow-hidden transition-all ${
        saving ? "opacity-60" : ""
      } ${
        review.expert_decision === "accept"
          ? "border-[var(--color-border-subtle)]"
          : review.expert_decision === "reject"
          ? "border-[var(--color-accent-red)]/30"
          : "border-[var(--color-accent-amber)]/30"
      }`}
    >
      {/* Header */}
      <div
        className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-[var(--color-bg-tertiary)]/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
              review.original_verdict === "pass" ? "verdict-pass" : "verdict-fail"
            }`}
          >
            {review.original_verdict.toUpperCase()}
          </span>
          <span className="text-sm font-semibold text-[var(--color-text-primary)] capitalize">
            {review.criterion}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${style.className}`}>
            {style.icon} {style.label}
          </span>
          <span className="text-[var(--color-text-muted)] text-xs">{expanded ? "▴" : "▾"}</span>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-[var(--color-border-subtle)]">
          {/* Original rationale */}
          <div className="px-3 py-2 bg-[var(--color-bg-primary)]/50">
            <span className="text-[10px] font-mono text-[var(--color-text-muted)] uppercase">
              Judge Rationale
            </span>
            <p className="text-xs text-[var(--color-text-secondary)] mt-1 font-clinical leading-relaxed">
              {review.original_rationale}
            </p>
          </div>

          {/* Decision buttons */}
          <div className="px-3 py-2 flex items-center gap-1.5 border-t border-[var(--color-border-subtle)]">
            {(["accept", "reject", "modify"] as Decision[]).map((d) => {
              const s = DECISION_STYLES[d];
              const isActive = review.expert_decision === d;
              return (
                <button
                  key={d}
                  onClick={() => onUpdate(d, d === "modify" ? modifiedVerdict : undefined, reasoning)}
                  disabled={saving}
                  className={`px-2.5 py-1.5 rounded text-[11px] font-semibold border transition-all cursor-pointer ${
                    isActive
                      ? s.className
                      : "border-[var(--color-border-subtle)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-border-strong)]"
                  }`}
                >
                  {s.icon} {s.label}
                </button>
              );
            })}
            <div className="flex-1" />
            <button
              onClick={onDelete}
              disabled={saving}
              className="px-2 py-1.5 rounded text-[11px] border border-[var(--color-border-subtle)] text-[var(--color-text-muted)] hover:text-[var(--color-accent-red)] hover:border-[var(--color-accent-red)]/30 transition-all cursor-pointer"
              title="Remove this criterion from review"
            >
              ✕ Delete
            </button>
          </div>

          {/* Modify verdict (if modify mode) */}
          {review.expert_decision === "modify" && (
            <div className="px-3 py-2 border-t border-[var(--color-border-subtle)]">
              <label className="text-[10px] font-mono text-[var(--color-text-muted)] uppercase block mb-1">
                Modified Verdict
              </label>
              <select
                value={modifiedVerdict}
                onChange={(e) => {
                  setModifiedVerdict(e.target.value);
                  onUpdate("modify", e.target.value, reasoning);
                }}
                className="w-full bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] rounded px-2 py-1.5 text-sm text-[var(--color-text-primary)] font-mono"
              >
                <option value="pass">PASS</option>
                <option value="fail">FAIL</option>
              </select>
            </div>
          )}

          {/* Expert reasoning */}
          <div className="px-3 py-2 border-t border-[var(--color-border-subtle)]">
            <label className="text-[10px] font-mono text-[var(--color-text-muted)] uppercase block mb-1">
              Expert Reasoning
            </label>
            <textarea
              value={reasoning}
              onChange={(e) => setReasoning(e.target.value)}
              onBlur={() =>
                onUpdate(
                  review.expert_decision as Decision,
                  review.expert_decision === "modify" ? modifiedVerdict : undefined,
                  reasoning
                )
              }
              rows={3}
              placeholder="Why do you agree/disagree with this verdict?"
              className="w-full bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] rounded px-2 py-1.5 text-xs text-[var(--color-text-primary)] font-clinical resize-y placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent-blue)]/50"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function HallucinationCard({
  review,
  saving,
  onUpdate,
}: {
  review: ReviewSession["hallucination_reviews"][0];
  saving: boolean;
  onUpdate: (decision: Decision, reasoning?: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [reasoning, setReasoning] = useState(review.expert_reasoning);

  return (
    <div
      className={`rounded-md border border-[var(--color-accent-red)]/20 overflow-hidden transition-all ${
        saving ? "opacity-60" : ""
      }`}
    >
      <div
        className="px-3 py-2 flex items-start justify-between cursor-pointer hover:bg-[var(--color-bg-tertiary)]/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono verdict-fail px-1.5 py-0.5 rounded">
              HALLUCINATION
            </span>
            <span className="text-xs font-semibold text-[var(--color-text-primary)]">
              {review.entity}
            </span>
          </div>
          <p className="text-[11px] font-mono text-[var(--color-text-secondary)] truncate">
            &ldquo;{review.original_claim}&rdquo;
          </p>
        </div>
        <span className="text-[var(--color-text-muted)] text-xs ml-2">{expanded ? "▴" : "▾"}</span>
      </div>

      {expanded && (
        <div className="border-t border-[var(--color-border-subtle)]">
          <div className="px-3 py-2 flex items-center gap-1.5">
            {(["accept", "reject"] as Decision[]).map((d) => {
              const s = DECISION_STYLES[d];
              const isActive = review.expert_decision === d;
              const label = d === "accept" ? "Confirm Flag" : "Dismiss Flag";
              return (
                <button
                  key={d}
                  onClick={() => onUpdate(d, reasoning)}
                  disabled={saving}
                  className={`px-2.5 py-1.5 rounded text-[11px] font-semibold border transition-all cursor-pointer ${
                    isActive
                      ? s.className
                      : "border-[var(--color-border-subtle)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
                  }`}
                >
                  {s.icon} {label}
                </button>
              );
            })}
          </div>
          <div className="px-3 py-2 border-t border-[var(--color-border-subtle)]">
            <label className="text-[10px] font-mono text-[var(--color-text-muted)] uppercase block mb-1">
              Expert Reasoning
            </label>
            <textarea
              value={reasoning}
              onChange={(e) => setReasoning(e.target.value)}
              onBlur={() => onUpdate(review.expert_decision as Decision, reasoning)}
              rows={2}
              placeholder="Is this actually a hallucination?"
              className="w-full bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] rounded px-2 py-1.5 text-xs text-[var(--color-text-primary)] font-clinical resize-y placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent-blue)]/50"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function OverallVerdictForm({
  session,
  saving,
  onSave,
}: {
  session: ReviewSession;
  saving: boolean;
  onSave: (verdict: string, reasoning: string, status: string) => void;
}) {
  const [verdict, setVerdict] = useState(session.overall_expert_verdict || "");
  const [reasoning, setReasoning] = useState(session.overall_expert_reasoning || "");

  return (
    <div className="space-y-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
        Overall Expert Verdict
      </div>
      <div className="flex gap-2">
        {["pass", "fail"].map((v) => (
          <button
            key={v}
            onClick={() => setVerdict(v)}
            className={`px-3 py-1.5 rounded text-[11px] font-semibold border transition-all cursor-pointer ${
              verdict === v
                ? v === "pass"
                  ? "verdict-pass border-[var(--color-accent-green)]/30"
                  : "verdict-fail border-[var(--color-accent-red)]/30"
                : "border-[var(--color-border-subtle)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            {v.toUpperCase()}
          </button>
        ))}
      </div>
      <textarea
        value={reasoning}
        onChange={(e) => setReasoning(e.target.value)}
        rows={3}
        placeholder="Overall assessment of this SOAP note..."
        className="w-full bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] rounded px-2 py-1.5 text-xs text-[var(--color-text-primary)] font-clinical resize-y placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent-blue)]/50"
      />
      <div className="flex gap-2">
        <button
          onClick={() => onSave(verdict, reasoning, "in_progress")}
          disabled={saving || !verdict}
          className="px-3 py-1.5 rounded text-[11px] font-semibold border border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer disabled:opacity-40"
        >
          Save Draft
        </button>
        <button
          onClick={() => onSave(verdict, reasoning, "completed")}
          disabled={saving || !verdict}
          className="px-3 py-1.5 rounded text-[11px] font-semibold bg-[var(--color-accent-green-dim)] text-[var(--color-accent-green)] border border-[var(--color-accent-green)]/30 hover:bg-[var(--color-accent-green)]/20 transition-colors cursor-pointer disabled:opacity-40"
        >
          Complete Review
        </button>
      </div>
    </div>
  );
}
