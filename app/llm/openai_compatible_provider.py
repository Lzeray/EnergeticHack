from __future__ import annotations

import httpx

from app.llm.base import CLUSTER_LABEL_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT, LLMProvider, LLMUnavailableError


class OpenAICompatibleProvider(LLMProvider):
    """Any OpenAI-compatible /chat/completions endpoint: OpenAI itself,
    OpenRouter, vLLM, LM Studio, etc. — just point base_url at it."""

    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str | None, model: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _chat(self, system: str, user: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailableError(f"OpenAI-compatible request failed: {exc}") from exc
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise LLMUnavailableError(f"Unexpected response shape: {data}") from exc
        if not text:
            raise LLMUnavailableError("OpenAI-compatible provider returned an empty response")
        return text

    def summarize(self, title: str, text: str, audience: str = "technical") -> str:
        audience_hint = "для менеджмента, деловым языком" if audience == "management" else "для технического специалиста"
        user = f"Аудитория: {audience_hint}.\nЗаголовок: {title}\n\nТекст статьи:\n{text[:4000]}"
        return self._chat(SUMMARY_SYSTEM_PROMPT, user)

    def label_cluster(self, titles: list[str]) -> str:
        user = "Заголовки:\n" + "\n".join(f"- {t}" for t in titles[:12])
        return self._chat(CLUSTER_LABEL_SYSTEM_PROMPT, user)
