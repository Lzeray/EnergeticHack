from __future__ import annotations

import logging

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider, LLMUnavailableError
from app.llm.extractive_fallback import ExtractiveProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_compatible_provider import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class FallbackProvider(LLMProvider):
    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.last_error: str | None = None
        self._warned = False

    def _warn_once(self, exc: Exception) -> None:
        self.last_error = str(exc)
        if not self._warned:
            logger.warning(
                "LLM provider %s failed (%s); falling back to extractive summaries for the rest of this run",
                self.primary.name,
                exc,
            )
            self._warned = True

    def summarize(self, title: str, text: str, audience: str = "technical") -> str:
        try:
            return self.primary.summarize(title, text, audience)
        except Exception as exc:  # noqa: BLE001
            self._warn_once(exc)
            return self.fallback.summarize(title, text, audience)

    def label_cluster(self, titles: list[str]) -> str:
        try:
            return self.primary.label_cluster(titles)
        except Exception as exc:  # noqa: BLE001
            self._warn_once(exc)
            return self.fallback.label_cluster(titles)


def build_provider(
    provider_name: str,
    model: str,
    *,
    ollama_base_url: str = "http://localhost:11434",
    openai_base_url: str = "https://api.openai.com/v1",
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    anthropic_model: str = "claude-sonnet-5-5",
    timeout: float = 20.0,
) -> LLMProvider:
    extractive = ExtractiveProvider()
    if provider_name == "none":
        return extractive

    try:
        if provider_name == "ollama":
            primary: LLMProvider = OllamaProvider(ollama_base_url, model, timeout)
        elif provider_name == "openai":
            primary = OpenAICompatibleProvider(openai_base_url, openai_api_key, model, timeout)
        elif provider_name == "anthropic":
            primary = AnthropicProvider(anthropic_api_key, anthropic_model, timeout)
        else:
            raise LLMUnavailableError(f"Unknown llm_provider: {provider_name!r}")
    except LLMUnavailableError as exc:
        logger.warning("LLM provider %s could not be constructed (%s); using extractive fallback only", provider_name, exc)
        return extractive

    return FallbackProvider(primary, extractive)
