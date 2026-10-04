from __future__ import annotations

from app.llm.base import CLUSTER_LABEL_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT, LLMProvider, LLMUnavailableError


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None, model: str, timeout: float = 20.0):
        if not api_key:
            raise LLMUnavailableError("ANTHROPIC_API_KEY is not configured")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailableError("anthropic package is not installed") from exc
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.model = model

    def _message(self, system: str, user: str, max_tokens: int) -> str:
        from anthropic import APIError

        try:
            response = self._client.messages.create(
                model=self.model,
                system=system,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": user}],
            )
        except APIError as exc:
            raise LLMUnavailableError(f"Anthropic request failed: {exc}") from exc
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()
        if not text:
            raise LLMUnavailableError("Anthropic returned an empty response")
        return text

    def summarize(self, title: str, text: str, audience: str = "technical") -> str:
        audience_hint = "для менеджмента, деловым языком" if audience == "management" else "для технического специалиста"
        user = f"Аудитория: {audience_hint}.\nЗаголовок: {title}\n\nТекст статьи:\n{text[:4000]}"
        return self._message(SUMMARY_SYSTEM_PROMPT, user, max_tokens=300)

    def label_cluster(self, titles: list[str]) -> str:
        user = "Заголовки:\n" + "\n".join(f"- {t}" for t in titles[:12])
        return self._message(CLUSTER_LABEL_SYSTEM_PROMPT, user, max_tokens=30)
