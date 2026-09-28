from __future__ import annotations

import re
from collections import Counter

from app.pipeline.ranking import tokenize
from app.pipeline.clustering import _STOPWORDS
from app.llm.base import LLMProvider

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_MAX_SUMMARY_CHARS = 320


class ExtractiveProvider(LLMProvider):
    """No-LLM fallback: takes the first couple of sentences of the article
    (or the title, if the body is too short) instead of a generated
    abstractive summary. Always available, used when no LLM is configured
    or reachable, so the pipeline never hard-fails on missing LLM access."""

    name = "extractive"

    def summarize(self, title: str, text: str, audience: str = "technical") -> str:
        body = (text or "").strip()
        if not body:
            return title.strip()
        sentences = _SENTENCE_SPLIT_RE.split(body)
        summary = ""
        for sentence in sentences:
            candidate = (summary + " " + sentence).strip()
            if len(candidate) > _MAX_SUMMARY_CHARS and summary:
                break
            summary = candidate
            if len(summary) > _MAX_SUMMARY_CHARS:
                break
        summary = summary[:_MAX_SUMMARY_CHARS].rstrip()
        return summary or title.strip()

    def label_cluster(self, titles: list[str]) -> str:
        counter: Counter[str] = Counter()
        for title in titles:
            counter.update(t for t in tokenize(title) if t not in _STOPWORDS and len(t) > 2)

        chosen: list[str] = []
        chosen_prefixes: set[str] = set()
        for word, _ in counter.most_common(20):
            prefix = word[:5]
            if prefix in chosen_prefixes:
                continue  # skip near-duplicate stems, e.g. "уязвимость" / "уязвимостей"
            chosen_prefixes.add(prefix)
            chosen.append(word.capitalize())
            if len(chosen) == 3:
                break
        return " / ".join(chosen) or "Общее"
