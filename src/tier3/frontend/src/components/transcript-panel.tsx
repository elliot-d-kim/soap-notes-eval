"use client";

interface TranscriptPanelProps {
  transcript: string;
  noteId: string;
  sourceDataset: string;
}

export function TranscriptPanel({ transcript, noteId, sourceDataset }: TranscriptPanelProps) {
  if (!transcript) {
    return (
      <div className="panel h-full flex items-center justify-center">
        <p className="text-[var(--color-text-muted)] text-sm italic">
          No transcript available for this note
        </p>
      </div>
    );
  }

  const lines = transcript.split("\n").filter((l) => l.trim());

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header flex items-center justify-between">
        <span>Source Dialogue</span>
        <span className="text-[10px] font-mono text-[var(--color-text-muted)] normal-case tracking-normal">
          {sourceDataset} / {noteId}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {lines.map((line, i) => {
          const isDoctor = /^(doctor|physician|dr\.)/i.test(line.trim());
          const isPatient = /^patient/i.test(line.trim());
          const colonIdx = line.indexOf(":");
          const speaker = colonIdx > -1 ? line.slice(0, colonIdx).trim() : null;
          const content = colonIdx > -1 ? line.slice(colonIdx + 1).trim() : line.trim();

          return (
            <div
              key={i}
              className={`rounded-md px-3 py-2 text-sm font-clinical ${
                isDoctor
                  ? "bg-[var(--color-accent-blue-dim)]/40 border-l-2 border-[var(--color-accent-blue)]"
                  : isPatient
                  ? "bg-[var(--color-bg-tertiary)] border-l-2 border-[var(--color-border-strong)]"
                  : "bg-[var(--color-bg-tertiary)]/50"
              }`}
            >
              {speaker && (
                <span
                  className={`text-[11px] font-semibold uppercase tracking-wider block mb-1 ${
                    isDoctor
                      ? "text-[var(--color-accent-blue)]"
                      : "text-[var(--color-text-secondary)]"
                  }`}
                >
                  {speaker}
                </span>
              )}
              <span className="text-[var(--color-text-primary)] leading-relaxed">
                {content}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
