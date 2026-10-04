from __future__ import annotations

import httpx

from app.llm.base import CLUSTER_LABEL_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT, LLMProvider, LLMUnavailableError


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _generate(self, system: str, prompt: str) -> str:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "system": system,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailableError(f"Ollama request failed: {exc}") from exc
        text = (data.get("response") or "").strip()
        if not text:
            raise LLMUnavailableError("Ollama returned an empty response")
        return text

    def summarize(self, title: str, text: str, audience: str = "technical") -> str:
        audience_hint = "для менеджмента, деловым языком" if audience == "management" else "для технического специалиста"
        prompt = f"Аудитория: {audience_hint}.\nЗаголовок: {title}\n\nТекст статьи:\n{text[:4000]}"
        return self._generate(SUMMARY_SYSTEM_PROMPT, prompt)

    def label_cluster(self, titles: list[str]) -> str:
        prompt = "Заголовки:\n" + "\n".join(f"- {t}" for t in titles[:12])
        return self._generate(CLUSTER_LABEL_SYSTEM_PROMPT, prompt)
