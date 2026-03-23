"""Emit a sample Tier 2 judge report to output/tier2_sample_report.json."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import load_samples_from_manifest
from src.tier2.judge import judge_note


async def main() -> None:
    manifest = Path("data/eval_set/manifest.json")
    if not manifest.exists():
        print("Run data/samples/download.py and generate_degraded.py first.")
        sys.exit(1)

    notes = [n for n in load_samples_from_manifest(manifest) if n.transcript]
    if not notes:
        print("No notes with transcripts found.")
        sys.exit(1)

    note = notes[0]
    print(f"Judging note: {note.note_id} ({note.source_dataset})")

    verdict = await judge_note(note)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "tier2_sample_report.json"
    output_path.write_text(json.dumps(verdict.to_dict(), indent=2))
    print(f"Tier 2 sample report → {output_path}")
    print(f"  overall  : {verdict.overall_verdict.value}")
    print(f"  escalate : {verdict.escalate_to_tier3}")
    print(f"  model    : {verdict.model_used}")


if __name__ == "__main__":
    asyncio.run(main())
