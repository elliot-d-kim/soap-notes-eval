"""Central configuration for the SOAP Note Evaluation Suite.

Uses pydantic-settings to auto-read from .env. All LLM model names use the
openrouter/ prefix so LiteLLM routes through OpenRouter with a single API key.
Never hardcode a model name — always read from config.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    openrouter_api_key: str = ""
    default_model: str = "openrouter/anthropic/claude-3.5-sonnet"

    # Tier 2 judge
    judge_model: str = ""  # falls back to default_model if empty
    judge_temperature: float = 0.0
    judge_max_tokens: int = 2048

    # Tier 1 — tries scispaCy first; falls back to en_core_web_sm
    spacy_model: str = "en_core_sci_sm"

    # Paths
    prompts_dir: str = "prompts"
    output_dir: str = "output"
    data_dir: str = "data/samples"

    # Meta-eval
    agreement_target: float = 0.90  # target Cohen's kappa / percent agreement

    @property
    def active_judge_model(self) -> str:
        """Return judge model, defaulting to the general default model."""
        return self.judge_model if self.judge_model else self.default_model

    @property
    def litellm_api_key(self) -> str:
        """LiteLLM expects OPENROUTER_API_KEY in its own env var format."""
        return self.openrouter_api_key


# Module-level singleton — import and use directly.
settings = Settings()
