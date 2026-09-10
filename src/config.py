import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _integer(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a whole number") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    lead_provider: str = os.getenv("LEAD_PROVIDER", "fixture").lower()
    google_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    openrouter_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    ai_enabled: bool = os.getenv("ENABLE_AI_CLASSIFICATION", "false").lower() == "true"
    max_results: int = _integer("MAX_RESULTS_PER_MISSION", 25)
    max_provider_requests: int = _integer("MAX_PROVIDER_REQUESTS_PER_MISSION", 10)
    max_llm_classifications: int = _integer("MAX_LLM_CLASSIFICATIONS_PER_MISSION", 10, 0)
    request_timeout: int = _integer("REQUEST_TIMEOUT_SECONDS", 20)
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/leads.db"))

    def validate(self) -> None:
        if self.lead_provider not in {"fixture", "google"}:
            raise ValueError("LEAD_PROVIDER must be 'fixture' or 'google'")
        if self.lead_provider == "google" and not self.google_key:
            raise ValueError("Google provider selected, but GOOGLE_MAPS_API_KEY is not configured")

