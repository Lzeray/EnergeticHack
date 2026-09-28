from app.llm.base import LLMProvider, LLMUnavailableError
from app.llm.factory import FallbackProvider, build_provider


class _AlwaysFailsProvider(LLMProvider):
    name = "broken"

    def summarize(self, title, text, audience="technical"):
        raise LLMUnavailableError("simulated outage")

    def label_cluster(self, titles):
        raise LLMUnavailableError("simulated outage")


class _WorksProvider(LLMProvider):
    name = "works"

    def summarize(self, title, text, audience="technical"):
        return "ok summary"

    def label_cluster(self, titles):
        return "ok label"


def test_fallback_provider_uses_extractive_on_failure():
    from app.llm.extractive_fallback import ExtractiveProvider

    provider = FallbackProvider(_AlwaysFailsProvider(), ExtractiveProvider())
    summary = provider.summarize("Заголовок статьи", "Первое предложение. Второе предложение.")
    assert summary  # never empty/raises
    assert provider.last_error is not None


def test_fallback_provider_passes_through_when_primary_works():
    from app.llm.extractive_fallback import ExtractiveProvider

    provider = FallbackProvider(_WorksProvider(), ExtractiveProvider())
    assert provider.summarize("T", "body") == "ok summary"
    assert provider.last_error is None


def test_build_provider_none_returns_extractive_only():
    provider = build_provider("none", "any-model")
    assert provider.name == "extractive"


def test_build_provider_anthropic_without_key_falls_back_to_extractive():
    provider = build_provider("anthropic", "claude-sonnet-5-5", anthropic_api_key=None)
    assert provider.name == "extractive"


def test_build_provider_ollama_unreachable_degrades_gracefully():
    provider = build_provider("ollama", "does-not-matter", ollama_base_url="http://127.0.0.1:1", timeout=1.0)
    summary = provider.summarize("Заголовок", "Текст статьи для проверки.")
    assert summary
