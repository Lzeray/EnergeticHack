from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EH_", extra="ignore")

    app_name: str = "EnergeticHack"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    digests_dir: Path = BASE_DIR / "data" / "digests"
    fixtures_dir: Path = BASE_DIR / "data" / "fixtures"

    # LLM provider: "ollama" | "openai" | "anthropic" | "none"
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1"
    ollama_base_url: str = "http://localhost:11434"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    llm_timeout_seconds: float = 20.0

    # Ranking / digest sizing
    daily_top_k: int = 15
    monthly_top_k: int = 20
    max_items_per_source_ratio: float = 0.4  # cap any single source at 40% of the digest
    dedup_fuzzy_threshold: int = 87  # rapidfuzz token_sort_ratio 0-100
    dedup_window_hours: int = 72

    # HTTP fetch
    http_timeout_seconds: float = 15.0
    http_user_agent: str = "EnergeticHack-Digest-Bot/0.1 (+security digest prototype)"

    host: str = "0.0.0.0"
    port: int = 8899


settings = Settings()
settings.digests_dir.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
