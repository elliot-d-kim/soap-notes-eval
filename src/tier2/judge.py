"""Tier 2 LLM-as-a-Judge orchestrator.

Loads the active prompt version from prompts/manifest.json, sends the SOAP
note and transcript to LiteLLM (routed via OpenRouter), enforces chain-of-thought
before verdict, and returns a validated Pydantic Tier2Verdict.

Design decisions:
- Async by default (LLM calls are I/O-bound and should be parallelised).
- prompt version is config-driven via manifest.json — never hardcoded.
- Temperature 0.0 for maximum verdict consistency (reproducibility matters for evals).
- Structured JSON output enforced via prompt + Pydantic validation with retry.
"""

from __future__ import annotations

import json
import os
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import litellm
from litellm import acompletion

from src.config import settings
from src.data.models import SOAPNote
from src.tier2.schemas import (
    HallucinationFlag,
    Tier2Verdict,
    Verdict,
    CriterionVerdict,
)


# ---------------------------------------------------------------------------
# Suppress LiteLLM verbose logging unless debugging
# ---------------------------------------------------------------------------
litellm.suppress_debug_info = True


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------


def _load_prompt_manifest(prompts_dir: str | Path | None = None) -> dict:
    """Load prompts/manifest.json."""
    prompts_dir = Path(prompts_dir or settings.prompts_dir)
    manifest_path = prompts_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Prompt manifest not found: {manifest_path}")
    with open(manifest_path) as f:
        return json.load(f)


def _load_judge_prompt(
    prompts_dir: str | Path | None = None,
    version: str | None = None,
) -> tuple[str, str]:
    """Load the judge prompt template, returning (template_text, version_string).

    If version is None, uses the active version from the manifest.
    """
    prompts_dir = Path(prompts_dir or settings.prompts_dir)
    manifest = _load_prompt_manifest(prompts_dir)

    judge_config = manifest["prompts"]["tier2_judge"]
    active_version = version or judge_config["active_version"]
    filename = judge_config["versions"][active_version]["filename"]

    prompt_path = prompts_dir / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Judge prompt not found: {prompt_path}")

    return prompt_path.read_text(), active_version


# ---------------------------------------------------------------------------
# JSON extraction from LLM response
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from LLM response text.

    Handles both bare JSON and JSON wrapped in markdown code blocks.
    """
    # Try to find JSON inside ```json ... ``` or ``` ... ``` blocks
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        return json.loads(code_block.group(1))

    # Try to find a standalone JSON object
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return json.loads(brace_match.group(0))

    raise ValueError(f"No JSON object found in LLM response:\n{text[:500]}")


# ---------------------------------------------------------------------------
# Verdict construction
# ---------------------------------------------------------------------------


def _build_verdict(
    note_id: str,
    model_used: str,
    prompt_version: str,
    raw: dict,
) -> Tier2Verdict:
    """Construct a validated Tier2Verdict from raw LLM JSON output."""
    criteria = [
        CriterionVerdict(
            criterion=c["criterion"],
            rationale=c["rationale"],
            verdict=Verdict(c["verdict"]),
            evidence=c.get("evidence", []),
        )
        for c in raw.get("criteria", [])
    ]

    hallucinations = [
        HallucinationFlag(
            entity=h["entity"],
            claim_in_note=h["claim_in_note"],
            grounding_verdict=Verdict(h.get("grounding_verdict", "fail")),
            explanation=h["explanation"],
        )
        for h in raw.get("hallucination_flags", [])
    ]

    return Tier2Verdict(
        note_id=note_id,
        model_used=model_used,
        prompt_version=prompt_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        criteria=criteria,
        hallucination_flags=hallucinations,
        overall_verdict=Verdict(raw["overall_verdict"]),
        overall_rationale=raw["overall_rationale"],
        escalate_to_tier3=bool(raw.get("escalate_to_tier3", False)),
    )


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def judge_note(
    note: SOAPNote,
    prompts_dir: str | Path | None = None,
    model: str | None = None,
    max_retries: int = 2,
) -> Tier2Verdict:
    """Evaluate a SOAP note using the LLM judge.

    Args:
        note: The SOAP note to evaluate.
        prompts_dir: Override for prompts directory (default from config).
        model: Override for model (default from config.active_judge_model).
        max_retries: Number of times to retry on JSON parse failure.

    Returns:
        Validated Tier2Verdict.

    Raises:
        ValueError: If the LLM response cannot be parsed after all retries.
    """
    template, prompt_version = _load_judge_prompt(prompts_dir)
    model = model or settings.active_judge_model

    # Render prompt — handle missing transcript gracefully
    transcript_text = note.transcript or "(No transcript provided — evaluate note internally only)"
    prompt = template.replace("{transcript}", transcript_text).replace(
        "{note_text}", note.note_text
    )

    messages = [{"role": "user", "content": prompt}]

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=settings.judge_temperature,
                max_tokens=settings.judge_max_tokens,
                api_key=settings.litellm_api_key,
            )
            raw_text = response.choices[0].message.content or ""
            raw_json = _extract_json(raw_text)
            return _build_verdict(note.note_id, model, prompt_version, raw_json)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            last_error = e
            if attempt < max_retries:
                # Add a correction message and retry
                messages = messages + [
                    {"role": "assistant", "content": raw_text if "raw_text" in dir() else ""},
                    {
                        "role": "user",
                        "content": (
                            "Your response was not valid JSON. "
                            "Please respond with only a valid JSON object matching the schema. "
                            "No markdown, no prose — just the JSON."
                        ),
                    },
                ]

    raise ValueError(
        f"Failed to parse judge verdict for note '{note.note_id}' "
        f"after {max_retries + 1} attempts. Last error: {last_error}"
    )


async def judge_batch(
    notes: list[SOAPNote],
    prompts_dir: str | Path | None = None,
    model: str | None = None,
) -> list[Tier2Verdict]:
    """Evaluate a batch of notes concurrently.

    Uses asyncio.gather for concurrency — LLM API calls are I/O-bound.
    """
    import asyncio

    tasks = [judge_note(note, prompts_dir=prompts_dir, model=model) for note in notes]
    return await asyncio.gather(*tasks)
