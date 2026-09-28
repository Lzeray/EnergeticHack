from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings

_LLM_KEYS = [
    "llm_provider",
    "llm_model",
    "ollama_base_url",
    "openai_base_url",
    "openai_api_key",
    "anthropic_api_key",
    "anthropic_model",
]


def get_llm_config(session: Session) -> dict:
    """Runtime LLM config: DB-stored overrides (set via the Settings page)
    take precedence over the .env-backed defaults, so operators can switch
    providers without restarting the process."""
    rows = {row.key: row.value for row in session.execute(select(models.AppSetting)).scalars()}
    config = {key: rows.get(key, getattr(settings, key)) for key in _LLM_KEYS}
    return config


def set_llm_config(session: Session, **updates: str | None) -> None:
    for key, value in updates.items():
        if key not in _LLM_KEYS:
            continue
        existing = session.get(models.AppSetting, key)
        if value is None:
            if existing:
                session.delete(existing)
            continue
        if existing:
            existing.value = value
        else:
            session.add(models.AppSetting(key=key, value=value))
    session.commit()
