"""Download ~100 representative samples from public SOAP note datasets.

Datasets:
- adesouza1/soap_notes  (HuggingFace, 558 rows)
- omi-health/medical-dialogue-to-soap-summary  (HuggingFace, 9250 rows)

Run from the project root:
    python data/samples/download.py

Saves JSON files to data/samples/ preserving original field names.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datasets import load_dataset  # noqa: E402

SAMPLES_DIR = Path(__file__).parent
N_SAMPLES = 50  # per dataset — 50 × 2 = 100 total


def save(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path.relative_to(SAMPLES_DIR.parents[1])}")


# ---------------------------------------------------------------------------
# adesouza1/soap_notes
# ---------------------------------------------------------------------------

def download_adesouza() -> list[str]:
    """Download samples from adesouza1/soap_notes."""
    print(f"\n[1/2] adesouza1/soap_notes (target: {N_SAMPLES})")
    saved = []
    try:
        ds = load_dataset("adesouza1/soap_notes", split="train", streaming=True)
        for i, row in enumerate(ds):
            if i >= N_SAMPLES:
                break
            note_id = f"adesouza_{i:03d}"
            record = dict(row)
            # Actual fields: soap_notes, patient_convo
            record["note_text"] = record.get("soap_notes", "")
            record["transcript"] = record.get("patient_convo", "")
            path = SAMPLES_DIR / f"{note_id}.json"
            save(record, path)
            saved.append(note_id)
    except Exception as e:
        print(f"  WARNING: could not download adesouza1/soap_notes — {e}")
        saved.extend(_create_fallback_samples("adesouza", N_SAMPLES))
    print(f"  downloaded {len(saved)} samples")
    return saved


# ---------------------------------------------------------------------------
# Omi Health
# ---------------------------------------------------------------------------

def download_omi_health() -> list[str]:
    """Download samples from omi-health/medical-dialogue-to-soap-summary."""
    print(f"\n[2/2] omi-health/medical-dialogue-to-soap-summary (target: {N_SAMPLES})")
    saved = []
    try:
        ds = load_dataset(
            "omi-health/medical-dialogue-to-soap-summary",
            split="train",
            streaming=True,
        )
        for i, row in enumerate(ds):
            if i >= N_SAMPLES:
                break
            note_id = f"omi_{i:03d}"
            record = dict(row)
            # Actual fields: soap, dialogue
            record["note_text"] = record.get("soap", "")
            record["transcript"] = record.get("dialogue", "")
            path = SAMPLES_DIR / f"{note_id}.json"
            save(record, path)
            saved.append(note_id)
    except Exception as e:
        print(f"  WARNING: could not download omi-health — {e}")
        saved.extend(_create_fallback_samples("omi", N_SAMPLES))
    print(f"  downloaded {len(saved)} samples")
    return saved


# ---------------------------------------------------------------------------
# Fallback samples (used if HuggingFace datasets unavailable)
# ---------------------------------------------------------------------------

_FALLBACK_NOTES = [
    {
        "note_text": (
            "Subjective:\nPatient is a 45-year-old female presenting with a 3-day history of productive cough, "
            "fever (38.5°C), and mild shortness of breath. She reports no prior lung conditions. "
            "Currently taking lisinopril 10mg daily for hypertension.\n\n"
            "Objective:\nTemp 38.5°C, HR 92 bpm, BP 128/82 mmHg, O2 sat 97% on room air. "
            "Lung auscultation reveals crackles in the right lower lobe. "
            "CXR shows right lower lobe infiltrate.\n\n"
            "Assessment:\n1. Community-acquired pneumonia, right lower lobe\n"
            "2. Hypertension, well-controlled\n\n"
            "Plan:\n1. Azithromycin 500mg PO x1, then 250mg daily x 4 days\n"
            "2. Amoxicillin-clavulanate 875mg BID x 5 days\n"
            "3. Follow up in 5–7 days or sooner if worsening\n"
            "4. Return precautions: worsening dyspnea, high fever, hemoptysis"
        ),
        "transcript": (
            "Doctor: Good morning. What brings you in today?\n"
            "Patient: I've had this cough for 3 days now and I feel really hot and short of breath.\n"
            "Doctor: Any chest pain? Bringing up any mucus?\n"
            "Patient: Yes, greenish mucus. No chest pain.\n"
            "Doctor: Any prior lung problems or recent travel?\n"
            "Patient: No. I do take lisinopril for my blood pressure.\n"
            "Doctor: Let me listen to your lungs. [examines] I hear crackles on the right side. "
            "Your temperature is 38.5. I'd like to get a chest X-ray.\n"
            "Patient: Okay.\n"
            "Doctor: The X-ray shows an infection in the right lower lobe. You have pneumonia. "
            "I'll prescribe antibiotics — azithromycin and amoxicillin-clavulanate. "
            "Follow up in a week or sooner if you feel worse."
        ),
        "ground_truth_note": None,
    },
    {
        "note_text": (
            "Subjective:\n62-year-old male with type 2 diabetes presenting for routine follow-up. "
            "Reports fatigue over the past month. Diet has been inconsistent. "
            "Taking metformin 1000mg BID and atorvastatin 40mg nightly.\n\n"
            "Objective:\nBP 138/86 mmHg, HR 78 bpm, weight 98kg (BMI 31.2). "
            "HbA1c 8.4% (up from 7.8% 3 months ago). Fasting glucose 186 mg/dL. "
            "LDL 82 mg/dL.\n\n"
            "Assessment:\n1. Type 2 diabetes mellitus, suboptimally controlled (HbA1c 8.4%)\n"
            "2. Hypertension, mildly elevated\n"
            "3. Hyperlipidemia, at target on statin\n\n"
            "Plan:\n1. Increase metformin to max tolerated dose; consider adding semaglutide\n"
            "2. Dietary counseling referral\n"
            "3. Add lisinopril 5mg daily for BP and renoprotection\n"
            "4. Recheck HbA1c and comprehensive metabolic panel in 3 months\n"
            "5. Continue atorvastatin 40mg"
        ),
        "transcript": (
            "Doctor: How have you been since your last visit?\n"
            "Patient: Tired mostly. I haven't been eating well.\n"
            "Doctor: Your HbA1c has gone up to 8.4% from 7.8%. How consistent have you been with metformin?\n"
            "Patient: Pretty consistent, but I miss a dose here and there.\n"
            "Doctor: Your blood pressure is a bit high today too — 138 over 86. "
            "I want to add lisinopril to help with both the blood pressure and your kidneys.\n"
            "Patient: Okay. Should I be worried?\n"
            "Doctor: Not alarmed, but we need to get things back in control. "
            "I'm also going to refer you to a dietitian and discuss adding a second diabetes medication."
        ),
        "ground_truth_note": None,
    },
    {
        "note_text": (
            "Subjective:\n28-year-old female presenting with 2-week history of right knee pain after "
            "a running injury. Describes pain as sharp with activity, rated 6/10. "
            "No locking or giving way. No previous knee injuries.\n\n"
            "Objective:\nRight knee: full ROM, mild swelling. Tenderness at lateral joint line. "
            "McMurray's negative. Lachman's negative. Patellar grind test negative.\n\n"
            "Assessment:\n1. Lateral knee pain, likely IT band syndrome vs. lateral meniscus irritation\n\n"
            "Plan:\n1. RICE protocol\n"
            "2. Naproxen 500mg BID with food for 1–2 weeks\n"
            "3. Physical therapy referral for IT band stretching and strengthening\n"
            "4. Avoid running until pain-free\n"
            "5. Return if no improvement in 3 weeks or if locking/instability develops"
        ),
        "transcript": (
            "Doctor: What happened with your knee?\n"
            "Patient: I was training for a half marathon and started getting this sharp pain on the outside "
            "of my right knee about two weeks ago.\n"
            "Doctor: Any popping, locking, or feeling like it gives way?\n"
            "Patient: No, none of that.\n"
            "Doctor: On a scale of 1–10?\n"
            "Patient: About a 6 when I'm running.\n"
            "Doctor: [examines knee] You have some swelling and tenderness along the lateral joint line. "
            "Special tests are negative. This looks like IT band syndrome or mild lateral meniscus irritation.\n"
            "Patient: What should I do?\n"
            "Doctor: Rest, ice, naproxen for pain. I'll refer you to PT for stretching. "
            "Hold off on running for now."
        ),
        "ground_truth_note": None,
    },
]


def _create_fallback_samples(prefix: str, n: int) -> list[str]:
    """Write synthetic fallback samples when HuggingFace download fails."""
    saved = []
    for i in range(min(n, len(_FALLBACK_NOTES))):
        note_id = f"{prefix}_{i:03d}"
        record = dict(_FALLBACK_NOTES[i])
        record["_fallback"] = True
        path = SAMPLES_DIR / f"{note_id}.json"
        save(record, path)
        saved.append(note_id)
    return saved


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def write_manifest(
    adesouza_ids: list[str],
    omi_ids: list[str],
) -> None:
    """Write data/samples/manifest.json cataloging all downloaded good samples."""
    entries = []

    for note_id in adesouza_ids:
        entries.append({
            "note_id": note_id,
            "filename": f"{note_id}.json",
            "source_dataset": "adesouza1",
            "label": "good",
            "metadata": {},
        })
    for note_id in omi_ids:
        entries.append({
            "note_id": note_id,
            "filename": f"{note_id}.json",
            "source_dataset": "omi-health",
            "label": "good",
            "metadata": {},
        })

    manifest = {
        "version": "1.0",
        "description": "SOAP note evaluation suite — sample manifest (good samples only; see degraded/manifest.json for degraded)",
        "samples": entries,
    }

    path = SAMPLES_DIR / "manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest written → {path.relative_to(SAMPLES_DIR.parents[1])}")
    print(f"Total good samples: {len(entries)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Downloading SOAP note samples...")
    adesouza_ids = download_adesouza()
    omi_ids = download_omi_health()
    write_manifest(adesouza_ids, omi_ids)
    print("\nDone.")
