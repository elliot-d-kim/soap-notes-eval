"use client";

import type { Tier1Report } from "@/lib/api";

interface SoapNotePanelProps {
  noteText: string;
  tier1Report: Tier1Report | null;
}

const SECTION_COLORS: Record<string, string> = {
  subjective: "var(--color-accent-blue)",
  objective: "var(--color-accent-green)",
  assessment: "var(--color-accent-amber)",
  plan: "var(--color-accent-red)",
};

export function SoapNotePanel({ noteText, tier1Report }: SoapNotePanelProps) {
  if (!noteText) {
    return (
      <div className="panel h-full flex items-center justify-center">
        <p className="text-[var(--color-text-muted)] text-sm italic">
          No SOAP note available
        </p>
      </div>
    );
  }

  // Parse SOAP sections
  const sections = parseSoapSections(noteText);

  // Build a map of tier1 checks by section
  const checksBySection: Record<string, Array<{ name: string; passed: boolean; details: string }>> = {};
  if (tier1Report?.structure?.checks) {
    for (const check of tier1Report.structure.checks) {
      const parts = check.name.split(":");
      const section = parts[1]?.toLowerCase() || "general";
      if (!checksBySection[section]) checksBySection[section] = [];
      checksBySection[section].push(check);
    }
  }

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header flex items-center justify-between">
        <span>Generated SOAP Note</span>
        {tier1Report && (
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full normal-case tracking-normal ${
              tier1Report.passed ? "verdict-pass" : "verdict-fail"
            }`}
          >
            Tier 1: {tier1Report.passed ? "PASS" : "FAIL"}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {sections.map((section) => {
          const accentColor = SECTION_COLORS[section.name.toLowerCase()] || "var(--color-border-strong)";
          const checks = checksBySection[section.name.toLowerCase()] || [];
          const failedChecks = checks.filter((c) => !c.passed);

          return (
            <div
              key={section.name}
              className="rounded-md border border-[var(--color-border-subtle)] overflow-hidden"
            >
              {/* Section header */}
              <div
                className="px-3 py-2 flex items-center justify-between"
                style={{ borderLeft: `3px solid ${accentColor}` }}
              >
                <span
                  className="text-[11px] font-semibold uppercase tracking-wider"
                  style={{ color: accentColor }}
                >
                  {section.name}
                </span>
                {failedChecks.length > 0 && (
                  <span className="text-[10px] font-mono verdict-fail px-1.5 py-0.5 rounded">
                    {failedChecks.length} issue{failedChecks.length > 1 ? "s" : ""}
                  </span>
                )}
              </div>

              {/* Section content */}
              <div className="px-3 py-2 font-clinical text-[var(--color-text-primary)] bg-[var(--color-bg-primary)]/50">
                {section.content}
              </div>

              {/* Tier 1 issues */}
              {failedChecks.length > 0 && (
                <div className="px-3 py-2 border-t border-[var(--color-border-subtle)] bg-[var(--color-accent-red-dim)]/20 space-y-1">
                  {failedChecks.map((check) => (
                    <div key={check.name} className="flex items-start gap-2 text-[11px]">
                      <span className="text-[var(--color-accent-red)] mt-0.5 shrink-0">✕</span>
                      <span className="text-[var(--color-text-secondary)] font-mono">
                        {check.details || check.name}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {/* Entities summary */}
        {tier1Report?.entities && (
          <div className="mt-4 rounded-md border border-[var(--color-border-subtle)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[var(--color-border-subtle)]">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                Extracted Entities
              </span>
            </div>
            <div className="px-3 py-2 space-y-2">
              {Object.entries(tier1Report.entities).map(([section, ents]) => {
                const allEnts = [
                  ...ents.medications.map((m) => ({ type: "med", value: m })),
                  ...ents.diagnoses.map((d) => ({ type: "dx", value: d })),
                  ...ents.procedures.map((p) => ({ type: "proc", value: p })),
                ];
                if (allEnts.length === 0) return null;
                return (
                  <div key={section}>
                    <span className="text-[10px] font-mono text-[var(--color-text-muted)] uppercase">
                      {section}
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {allEnts.map((e, i) => (
                        <span
                          key={i}
                          className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                            e.type === "med"
                              ? "bg-[var(--color-accent-blue-dim)]/60 text-[var(--color-accent-blue)]"
                              : e.type === "dx"
                              ? "bg-[var(--color-accent-amber-dim)]/60 text-[var(--color-accent-amber)]"
                              : "bg-[var(--color-accent-green-dim)]/60 text-[var(--color-accent-green)]"
                          }`}
                        >
                          {e.value}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function parseSoapSections(text: string): Array<{ name: string; content: string }> {
  const sections: Array<{ name: string; content: string }> = [];
  const sectionPattern = /^(Subjective|Objective|Assessment|Plan)\s*:/im;
  const lines = text.split("\n");

  let currentSection: { name: string; lines: string[] } | null = null;

  for (const line of lines) {
    const match = line.match(sectionPattern);
    if (match) {
      if (currentSection) {
        sections.push({
          name: currentSection.name,
          content: currentSection.lines.join("\n").trim(),
        });
      }
      const afterColon = line.slice(match[0].length).trim();
      currentSection = {
        name: match[1],
        lines: afterColon ? [afterColon] : [],
      };
    } else if (currentSection) {
      currentSection.lines.push(line);
    }
  }

  if (currentSection) {
    sections.push({
      name: currentSection.name,
      content: currentSection.lines.join("\n").trim(),
    });
  }

  // Fallback: if no sections parsed, show as single block
  if (sections.length === 0) {
    sections.push({ name: "Note", content: text });
  }

  return sections;
}
