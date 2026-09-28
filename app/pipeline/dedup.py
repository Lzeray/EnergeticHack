from __future__ import annotations

import datetime as dt
import hashlib
from urllib.parse import urlsplit, urlunsplit

from rapidfuzz import fuzz

from app.pipeline.types import DedupGroup, PipelineArticle


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip().lower())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _within_window(a: dt.datetime | None, b: dt.datetime | None, window_hours: int) -> bool:
    if a is None or b is None:
        return True  # missing dates never block a merge on their own
    return abs((a - b).total_seconds()) <= window_hours * 3600


def compute_dedup_groups(
    articles: list[PipelineArticle],
    fuzzy_threshold: int = 87,
    window_hours: int = 72,
) -> list[DedupGroup]:
    """Two-pass dedup: exact groups by normalized URL, then a greedy fuzzy
    merge of remaining groups by title similarity within a time window.
    Deterministic given the same input order (callers should sort by
    published_at, id before calling for reproducible results)."""

    by_url: dict[str, list[PipelineArticle]] = {}
    for art in articles:
        by_url.setdefault(_normalize_url(art.url), []).append(art)

    buckets: list[list[PipelineArticle]] = list(by_url.values())
    buckets.sort(key=lambda b: (b[0].published_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc), b[0].id))

    merged: list[list[PipelineArticle]] = []
    for bucket in buckets:
        rep = _pick_representative(bucket)
        target = None
        for existing in merged:
            existing_rep = _pick_representative(existing)
            if not _within_window(rep.published_at, existing_rep.published_at, window_hours):
                continue
            similarity = fuzz.token_sort_ratio(rep.title.lower(), existing_rep.title.lower())
            if similarity >= fuzzy_threshold:
                target = existing
                break
        if target is not None:
            target.extend(bucket)
        else:
            merged.append(list(bucket))

    groups: list[DedupGroup] = []
    for members in merged:
        rep = _pick_representative(members)
        group_key = hashlib.sha1(f"{rep.id}:{rep.url}".encode("utf-8")).hexdigest()[:16]
        groups.append(
            DedupGroup(
                group_id=group_key,
                representative_id=rep.id,
                member_ids=[m.id for m in members],
            )
        )
    return groups


def _pick_representative(members: list[PipelineArticle]) -> PipelineArticle:
    def sort_key(a: PipelineArticle):
        published = a.published_at or dt.datetime.max.replace(tzinfo=dt.timezone.utc)
        return (published, -a.source_priority)

    return sorted(members, key=sort_key)[0]
