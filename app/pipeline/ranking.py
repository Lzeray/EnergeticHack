from __future__ import annotations

import datetime as dt
import math
import re
from collections import Counter

from rank_bm25 import BM25Okapi

from app.pipeline.types import PipelineArticle, RankedArticle

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9\-]{2,}")

_EXCLUDE_MARKER_RE = re.compile(r"(?:Исключить|Exclude)\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)

WEIGHT_BM25 = 0.55
WEIGHT_RECENCY = 0.2
WEIGHT_SOURCE_TRUST = 0.15
WEIGHT_FEEDBACK = 0.10


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def parse_profile_interests(interests_text: str) -> tuple[str, list[str]]:
    text = interests_text or ""
    match = _EXCLUDE_MARKER_RE.search(text)
    if not match:
        return text.strip(), []
    exclude_terms = [t.strip(" .\n") for t in re.split(r"[,;\n]", match.group(1)) if t.strip(" .\n")]
    query_text = text[: match.start()].strip()
    return query_text, exclude_terms


def _token_matches(term_token: str, haystack_tokens: set[str]) -> bool:
    prefix_len = min(len(term_token), 5)
    term_prefix = term_token[:prefix_len]
    return any(ht[:prefix_len] == term_prefix for ht in haystack_tokens if len(ht) >= prefix_len)


def _matches_any_term(haystack: str, terms: list[str]) -> bool:
    haystack_tokens = set(tokenize(haystack))
    for term in terms:
        term_tokens = tokenize(term)
        if term_tokens and all(_token_matches(tt, haystack_tokens) for tt in term_tokens):
            return True
    return False


def _recency_score(published_at: dt.datetime | None, reference_time: dt.datetime, half_life_hours: float) -> float:
    if published_at is None:
        return 0.3
    age_hours = max(0.0, (reference_time - published_at).total_seconds() / 3600.0)
    return math.exp(-age_hours / max(half_life_hours, 1e-6) * math.log(2))


def _minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def rank_articles(
    articles: list[PipelineArticle],
    interests_text: str,
    liked_tokens: Counter | None = None,
    disliked_tokens: Counter | None = None,
    reference_time: dt.datetime | None = None,
    recency_half_life_hours: float = 48.0,
) -> list[RankedArticle]:
    if not articles:
        return []

    reference_time = reference_time or dt.datetime.now(dt.timezone.utc)
    liked_tokens = liked_tokens or Counter()
    disliked_tokens = disliked_tokens or Counter()
    query_text, exclude_terms = parse_profile_interests(interests_text)
    query_tokens = tokenize(query_text)

    kept = [a for a in articles if not _matches_any_term(f"{a.title} {a.text}", exclude_terms)]
    if not kept:
        return []

    corpus_tokens = [tokenize(f"{a.title} {a.title} {a.text}") for a in kept]  # title counted twice
    bm25 = BM25Okapi(corpus_tokens) if any(corpus_tokens) else None
    bm25_raw = bm25.get_scores(query_tokens).tolist() if bm25 and query_tokens else [0.0] * len(kept)
    bm25_norm = _minmax_normalize(bm25_raw)

    source_priorities = [a.source_priority for a in kept]
    source_norm = _minmax_normalize(source_priorities) if len(set(source_priorities)) > 1 else [0.5] * len(kept)

    max_feedback = max(1, sum(liked_tokens.values()) + sum(disliked_tokens.values()))

    ranked: list[RankedArticle] = []
    for idx, art in enumerate(kept):
        tokens = corpus_tokens[idx]
        recency = _recency_score(art.published_at, reference_time, recency_half_life_hours)

        feedback_raw = sum(liked_tokens.get(t, 0) for t in tokens) - sum(disliked_tokens.get(t, 0) for t in tokens)
        feedback_norm = max(-1.0, min(1.0, feedback_raw / max_feedback * 5))

        score = (
            WEIGHT_BM25 * bm25_norm[idx]
            + WEIGHT_RECENCY * recency
            + WEIGHT_SOURCE_TRUST * source_norm[idx]
            + WEIGHT_FEEDBACK * (feedback_norm + 1) / 2
        )

        matched = [t for t in dict.fromkeys(tokens) if t in query_tokens][:6]
        why = {
            "bm25": round(bm25_norm[idx], 3),
            "recency": round(recency, 3),
            "source_trust": round(source_norm[idx], 3),
            "feedback": round(feedback_norm, 3),
            "matched_keywords": matched,
        }
        ranked.append(RankedArticle(article=art, score=round(score, 4), why=why))

    ranked.sort(key=lambda r: (r.score, r.article.published_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc)), reverse=True)
    return ranked


def select_diverse_top_k(ranked: list[RankedArticle], k: int, max_per_source_ratio: float = 0.4) -> list[RankedArticle]:
    if k <= 0:
        return []
    max_per_source = max(1, math.ceil(k * max_per_source_ratio))
    per_source_count: Counter = Counter()
    selected: list[RankedArticle] = []
    overflow_by_source: dict[int, list[RankedArticle]] = {}

    for item in ranked:
        if len(selected) >= k:
            break
        source_id = item.article.source_id
        if per_source_count[source_id] < max_per_source:
            selected.append(item)
            per_source_count[source_id] += 1
        else:
            overflow_by_source.setdefault(source_id, []).append(item)

    source_order = list(overflow_by_source)
    while len(selected) < k and any(overflow_by_source.values()):
        for source_id in source_order:
            if len(selected) >= k:
                break
            queue = overflow_by_source.get(source_id)
            if queue:
                selected.append(queue.pop(0))

    return selected
