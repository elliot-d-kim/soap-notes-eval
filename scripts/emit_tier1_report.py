"""Emit a sample Tier 1 report to output/tier1_sample_report.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import load_samples_from_manifest
from src.tier1.pipeline import run_tier1


def main() -> None:
    manifest = Path("data/eval_set/manifest.json")
    if not manifest.exists():
        print("Run data/samples/download.py and generate_degraded.py first.")
        sys.exit(1)

    notes = list(load_samples_from_manifest(manifest))
    if not notes:
        print("No samples found in manifest.")
        sys.exit(1)

    report = run_tier1(notes[0])

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "tier1_sample_report.json"
    output_path.write_text(report.to_json())
    print(f"Tier 1 sample report → {output_path}")
    print(f"  note_id : {report.note_id}")
    print(f"  passed  : {report.passed}")
    print(f"  failures: {report.failure_types}")


if __name__ == "__main__":
    main()
