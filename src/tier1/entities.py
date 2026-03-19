"""Entity extraction for Tier 1 automated screening.

Uses scispaCy (en_core_sci_sm) for biomedical NER. Falls back to en_core_web_sm
if the scispaCy model is unavailable, with degraded entity coverage.

Extracted entity categories:
- medications: drugs, dosages, routes
- diagnoses: diseases, conditions, disorders
- procedures: tests, treatments, interventions
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Optional

import spacy
from spacy.language import Language

from src.config import settings


# ---------------------------------------------------------------------------
# Entity model
# ---------------------------------------------------------------------------


@dataclass
class ExtractedEntities:
    """Structured container for clinical entities extracted from a SOAP note."""

    medications: list[str] = field(default_factory=list)
    diagnoses: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)

    # spaCy entity labels classified to each bucket
    model_name: str = ""

    def all_entities(self) -> list[str]:
        """All extracted entities across all categories."""
        return self.medications + self.diagnoses + self.procedures + self.other

    def to_dict(self) -> dict:
        return {
            "medications": self.medications,
            "diagnoses": self.diagnoses,
            "procedures": self.procedures,
            "other": self.other,
            "model_name": self.model_name,
        }


# ---------------------------------------------------------------------------
# Label → category mapping
# ---------------------------------------------------------------------------

# scispaCy en_core_sci_sm uses generic ENTITY labels; we post-classify using
# a curated vocabulary heuristic. This is intentionally simple — the goal is
# reliable detection, not exhaustive classification.

_MEDICATION_CLUES = frozenset([
    "mg", "mcg", "tablet", "capsule", "injection", "inhaler", "solution",
    "syrup", "patch", "cream", "ointment", "dose", "daily", "twice",
    "bid", "tid", "qid", "prn", "po", "iv", "im", "sc", "topical",
])

_PROCEDURE_CLUES = frozenset([
    "xray", "x-ray", "mri", "ct", "ecg", "ekg", "ultrasound", "biopsy",
    "catheterization", "colonoscopy", "endoscopy", "spirometry", "culture",
    "panel", "labs", "bloodwork", "scan", "imaging", "test", "surgery",
    "procedure", "exam", "examination", "assessment", "therapy", "pt",
    "referral", "consultation",
])

# Common diagnosis suffixes
_DIAGNOSIS_SUFFIXES = (
    "itis", "osis", "emia", "oma", "uria", "pathy", "plasia", "trophy",
    "philia", "phobia", "syndrome", "disease", "disorder", "deficiency",
    "failure", "insufficiency", "hypertension", "diabetes", "asthma",
    "cancer", "infection", "pneumonia",
)


def _classify_entity(text: str, label: str) -> str:
    """Heuristically classify a scispaCy ENTITY into a clinical category."""
    lower = text.lower()

    # Procedures
    if any(clue in lower for clue in _PROCEDURE_CLUES):
        return "procedures"

    # Medications — dosage clue or known drug suffix
    tokens = set(lower.split())
    if tokens & _MEDICATION_CLUES:
        return "medications"
    if lower.endswith(("il", "in", "ole", "ine", "ate", "ide", "mab", "nib", "vir")):
        return "medications"

    # Diagnoses — disease/condition suffixes
    if any(lower.endswith(suffix) for suffix in _DIAGNOSIS_SUFFIXES):
        return "diagnoses"

    return "other"


# ---------------------------------------------------------------------------
# Model loader (singleton pattern to avoid reloading)
# ---------------------------------------------------------------------------

_nlp: Optional[Language] = None


def _load_model() -> Language:
    global _nlp
    if _nlp is not None:
        return _nlp

    primary = settings.spacy_model  # en_core_sci_sm by default
    fallback = "en_core_web_sm"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            _nlp = spacy.load(primary)
        except OSError:
            warnings.warn(
                f"spaCy model '{primary}' not found; falling back to '{fallback}'. "
                "Entity coverage will be reduced. Install scispaCy for clinical NER.",
                RuntimeWarning,
                stacklevel=3,
            )
            _nlp = spacy.load(fallback)

    return _nlp


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_entities(text: str) -> ExtractedEntities:
    """Extract clinical entities from text using the configured spaCy model.

    Args:
        text: Any text to extract entities from (note section, full note, transcript).

    Returns:
        ExtractedEntities with medication, diagnosis, and procedure buckets.
    """
    if not text or not text.strip():
        return ExtractedEntities()

    nlp = _load_model()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        doc = nlp(text)

    result = ExtractedEntities(model_name=nlp.meta.get("name", "unknown"))

    seen: set[str] = set()
    for ent in doc.ents:
        norm = ent.text.strip()
        if not norm or norm.lower() in seen:
            continue
        seen.add(norm.lower())

        category = _classify_entity(norm, ent.label_)
        getattr(result, category).append(norm)

    return result


def extract_entities_from_sections(sections: dict[str, str | None]) -> dict[str, ExtractedEntities]:
    """Extract entities per SOAP section.

    Args:
        sections: Mapping of section name → text (values may be None).

    Returns:
        Mapping of section name → ExtractedEntities.
    """
    return {
        name: extract_entities(text or "")
        for name, text in sections.items()
    }
