"""Generate synthetically degraded SOAP note variants with labeled failure types.

Hybrid approach:
- Programmatic (no LLM): missing_section, omitted_findings, redundancy_bloat, structural_errors
- LLM-assisted (uses LiteLLM): hallucinated_entities, internal_contradiction

Run from project root:
    python data/samples/generate_degraded.py

Reads good samples from data/samples/manifest.json.
Writes degraded variants to data/samples/degraded/.
Writes data/samples/degraded/manifest.json with ground-truth labels.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import settings
from src.data.loaders import parse_soap_sections

SAMPLES_DIR = Path(__file__).parent
DEGRADED_DIR = SAMPLES_DIR / "degraded"
DEGRADED_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]


def _save_degraded(record: dict, note_id: str) -> Path:
    path = DEGRADED_DIR / f"{note_id}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path.relative_to(SAMPLES_DIR.parents[1])}")
    return path


# ---------------------------------------------------------------------------
# Programmatic degradations
# ---------------------------------------------------------------------------


def degrade_missing_section(record: dict, note_id: str) -> dict | None:
    """Drop the Assessment section entirely."""
    sections = parse_soap_sections(record.get("note_text", ""))
    if not sections.assessment:
        return None  # Nothing to remove

    # Remove assessment from note text
    degraded_text = re.sub(
        r"(?:^|\n)\s*A(?:ssessment)?\s*[:\-]\s*.*?(?=(?:\n\s*(?:S|O|A|P)(?:ubjective|bjective|ssessment|lan)?\s*[:\-])|$)",
        "\n",
        record.get("note_text", ""),
        flags=re.IGNORECASE | re.DOTALL,
    )

    result = copy.deepcopy(record)
    result["note_text"] = degraded_text.strip()
    result["_degradation_types"] = ["missing_section"]
    result["_degradation_details"] = {"removed_section": "assessment"}
    result["_original_note_id"] = record.get("_note_id", note_id.replace("_missing_section", ""))
    return result


def degrade_omitted_findings(record: dict, note_id: str) -> dict | None:
    """Remove sentences containing clinical keywords from the Subjective section."""
    sections = parse_soap_sections(record.get("note_text", ""))
    if not sections.subjective:
        return None

    sentences = _split_sentences(sections.subjective)
    if len(sentences) < 2:
        return None  # Not enough content to omit from

    # Remove sentences containing key clinical terms
    _clinical_keywords = re.compile(
        r"\b(pain|fever|cough|dyspnea|shortness|nausea|fatigue|weakness|"
        r"swelling|headache|dizziness|symptom|complaint|history)\b",
        re.IGNORECASE,
    )

    removed = []
    kept = []
    for sent in sentences:
        if _clinical_keywords.search(sent) and len(removed) < 2:
            removed.append(sent)
        else:
            kept.append(sent)

    if not removed:
        # Remove the second sentence regardless
        removed = [sentences[1]]
        kept = [sentences[0]] + sentences[2:]

    degraded_subjective = " ".join(kept)
    degraded_text = record.get("note_text", "").replace(sections.subjective, degraded_subjective)

    result = copy.deepcopy(record)
    result["note_text"] = degraded_text
    result["_degradation_types"] = ["omitted_findings"]
    result["_degradation_details"] = {"omitted_sentences": removed}
    result["_original_note_id"] = record.get("_note_id", note_id)
    return result


def degrade_redundancy_bloat(record: dict, note_id: str) -> dict | None:
    """Duplicate sentences in the Plan section and pad with filler."""
    sections = parse_soap_sections(record.get("note_text", ""))
    if not sections.plan:
        return None

    sentences = _split_sentences(sections.plan)
    if not sentences:
        return None

    # Duplicate all plan sentences + add filler
    bloated_plan = (
        sections.plan
        + "\n"
        + "\n".join(sentences)  # duplicate
        + "\nAdditionally, the patient was counseled extensively regarding the above-mentioned items."
        + "\nThe patient verbalized understanding and agreement with the plan as discussed."
    )

    degraded_text = record.get("note_text", "").replace(sections.plan, bloated_plan)

    result = copy.deepcopy(record)
    result["note_text"] = degraded_text
    result["_degradation_types"] = ["redundancy_bloat"]
    result["_degradation_details"] = {"duplicated_section": "plan", "filler_added": True}
    result["_original_note_id"] = record.get("_note_id", note_id)
    return result


def degrade_structural_errors(record: dict, note_id: str) -> dict | None:
    """Swap Plan before Assessment (out-of-order sections)."""
    sections = parse_soap_sections(record.get("note_text", ""))
    if not sections.assessment or not sections.plan:
        return None

    note_text = record.get("note_text", "")

    # Find assessment and plan blocks in the text
    assessment_match = re.search(
        r"((?:^|\n)\s*A(?:ssessment)?\s*[:\-]\s*)(.*?)(?=(?:\n\s*P(?:lan)?\s*[:\-])|$)",
        note_text, re.IGNORECASE | re.DOTALL,
    )
    plan_match = re.search(
        r"((?:^|\n)\s*P(?:lan)?\s*[:\-]\s*)(.*?)$",
        note_text, re.IGNORECASE | re.DOTALL,
    )

    if not assessment_match or not plan_match:
        return None

    # Build swapped version: put Plan before Assessment
    before_assessment = note_text[:assessment_match.start()]
    plan_block = plan_match.group(0).strip()
    assessment_block = assessment_match.group(0).strip()

    degraded_text = before_assessment.strip() + "\n\n" + plan_block + "\n\n" + assessment_block

    result = copy.deepcopy(record)
    result["note_text"] = degraded_text
    result["_degradation_types"] = ["structural_errors"]
    result["_degradation_details"] = {"swap": "plan_before_assessment"}
    result["_original_note_id"] = record.get("_note_id", note_id)
    return result


# ---------------------------------------------------------------------------
# LLM-assisted degradations
# ---------------------------------------------------------------------------

_HALLUCINATION_PROMPT = """\
You are helping test a clinical note evaluation system. Take this SOAP note and inject 1-2 clinically plausible but HALLUCINATED medications or diagnoses — things that sound realistic but are NOT mentioned in the transcript below.

TRANSCRIPT:
{transcript}

SOAP NOTE:
{note_text}

Instructions:
- Add 1 hallucinated medication (with plausible dosage) to the Plan section.
- Add 1 hallucinated diagnosis to the Assessment section.
- Keep all original content — only ADD, don't remove.
- The additions must NOT appear anywhere in the transcript.

Return ONLY the modified SOAP note text, no commentary.
"""

_CONTRADICTION_PROMPT = """\
You are helping test a clinical note evaluation system. Introduce a subtle but clear INTERNAL CONTRADICTION into this SOAP note — the kind that a quality evaluator should catch.

SOAP NOTE:
{note_text}

Instructions:
- Create a contradiction between the Subjective and Assessment sections.
  Example: Subjective says "no fever" but Assessment says "febrile illness".
- Keep the change subtle but detectable.
- Return ONLY the modified SOAP note text, no commentary.
"""


async def degrade_hallucinated_entities_llm(record: dict, note_id: str) -> dict | None:
    """Use LLM to inject hallucinated entities into the note."""
    import litellm
    litellm.suppress_debug_info = True
    from litellm import acompletion

    note_text = record.get("note_text", "")
    transcript = record.get("transcript", "")

    if not note_text:
        return None

    prompt = _HALLUCINATION_PROMPT.format(
        transcript=transcript or "(no transcript)",
        note_text=note_text,
    )

    try:
        response = await acompletion(
            model=settings.active_judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
            api_key=settings.litellm_api_key,
        )
        degraded_text = response.choices[0].message.content.strip()

        result = copy.deepcopy(record)
        result["note_text"] = degraded_text
        result["_degradation_types"] = ["hallucinated_entities"]
        result["_degradation_details"] = {"method": "llm_injection"}
        result["_original_note_id"] = record.get("_note_id", note_id)
        return result
    except Exception as e:
        print(f"  WARNING: LLM hallucination degradation failed — {e}")
        return None


async def degrade_internal_contradiction_llm(record: dict, note_id: str) -> dict | None:
    """Use LLM to introduce an internal contradiction into the note."""
    import litellm
    litellm.suppress_debug_info = True
    from litellm import acompletion

    note_text = record.get("note_text", "")
    if not note_text:
        return None

    prompt = _CONTRADICTION_PROMPT.format(note_text=note_text)

    try:
        response = await acompletion(
            model=settings.active_judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
            api_key=settings.litellm_api_key,
        )
        degraded_text = response.choices[0].message.content.strip()

        result = copy.deepcopy(record)
        result["note_text"] = degraded_text
        result["_degradation_types"] = ["internal_contradiction"]
        result["_degradation_details"] = {"method": "llm_injection"}
        result["_original_note_id"] = record.get("_note_id", note_id)
        return result
    except Exception as e:
        print(f"  WARNING: LLM contradiction degradation failed — {e}")
        return None


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def main() -> None:
    print("Generating degraded SOAP note samples...")

    # Load good samples from manifest
    manifest_path = SAMPLES_DIR / "manifest.json"
    if not manifest_path.exists():
        print("ERROR: data/samples/manifest.json not found. Run download.py first.")
        sys.exit(1)

    with open(manifest_path) as f:
        good_manifest = json.load(f)

    good_entries = [e for e in good_manifest.get("samples", []) if e.get("label") == "good"]
    if not good_entries:
        print("No good samples found in manifest. Run download.py first.")
        sys.exit(1)

    degraded_manifest_entries = []
    degradation_fns_programmatic = [
        ("missing_section", degrade_missing_section),
        ("omitted_findings", degrade_omitted_findings),
        ("redundancy_bloat", degrade_redundancy_bloat),
        ("structural_errors", degrade_structural_errors),
    ]

    for entry in good_entries:
        sample_path = SAMPLES_DIR / entry["filename"]
        if not sample_path.exists():
            print(f"  SKIP (file not found): {entry['filename']}")
            continue

        with open(sample_path) as f:
            record = json.load(f)
        record["_note_id"] = entry["note_id"]

        print(f"\n[{entry['note_id']}] Generating programmatic degradations...")

        # Programmatic degradations
        for failure_type, fn in degradation_fns_programmatic:
            dg_note_id = f"{entry['note_id']}_{failure_type}"
            try:
                degraded = fn(record, dg_note_id)
            except Exception as e:
                print(f"  ERROR ({failure_type}): {e}")
                degraded = None

            if degraded is None:
                print(f"  SKIP {failure_type} (insufficient content)")
                continue

            _save_degraded(degraded, dg_note_id)
            degraded_manifest_entries.append({
                "note_id": dg_note_id,
                "filename": f"{dg_note_id}.json",
                "source_dataset": entry["source_dataset"],
                "label": "degraded",
                "degradation_types": degraded["_degradation_types"],
                "original_note_id": entry["note_id"],
                "degradation_details": degraded.get("_degradation_details", {}),
            })

        # LLM-assisted degradations
        print(f"[{entry['note_id']}] Generating LLM-assisted degradations...")

        for failure_type, async_fn in [
            ("hallucinated_entities", degrade_hallucinated_entities_llm),
            ("internal_contradiction", degrade_internal_contradiction_llm),
        ]:
            dg_note_id = f"{entry['note_id']}_{failure_type}"
            try:
                degraded = await async_fn(record, dg_note_id)
            except Exception as e:
                print(f"  ERROR ({failure_type}): {e}")
                degraded = None

            if degraded is None:
                print(f"  SKIP {failure_type}")
                continue

            _save_degraded(degraded, dg_note_id)
            degraded_manifest_entries.append({
                "note_id": dg_note_id,
                "filename": f"{dg_note_id}.json",
                "source_dataset": entry["source_dataset"],
                "label": "degraded",
                "degradation_types": degraded["_degradation_types"],
                "original_note_id": entry["note_id"],
                "degradation_details": degraded.get("_degradation_details", {}),
            })

    # Write degraded manifest
    degraded_manifest = {
        "version": "1.0",
        "description": "Synthetically degraded SOAP notes with ground-truth failure labels.",
        "samples": degraded_manifest_entries,
    }
    degraded_manifest_path = DEGRADED_DIR / "manifest.json"
    with open(degraded_manifest_path, "w") as f:
        json.dump(degraded_manifest, f, indent=2)
    print(f"\nDegraded manifest written → {degraded_manifest_path.relative_to(SAMPLES_DIR.parents[1])}")
    print(f"Total degraded samples: {len(degraded_manifest_entries)}")

    # Update the main manifest to include degraded entries
    all_entries = good_manifest.get("samples", []) + [
        {
            "note_id": e["note_id"],
            "filename": f"degraded/{e['filename']}",
            "source_dataset": e["source_dataset"],
            "label": "degraded",
            "degradation_types": e["degradation_types"],
            "original_note_id": e["original_note_id"],
            "metadata": {},
        }
        for e in degraded_manifest_entries
    ]

    updated_manifest = dict(good_manifest)
    updated_manifest["samples"] = all_entries
    with open(manifest_path, "w") as f:
        json.dump(updated_manifest, f, indent=2)
    print("Updated main manifest with degraded entries.")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
