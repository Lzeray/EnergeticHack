from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class PipelineArticle:
    """Lightweight, DB-agnostic view of an article used across the ranking /
    dedup / clustering pipeline, so those stages stay pure and unit-testable
    without a database."""

    id: int
    source_id: int
    source_name: str
    source_priority: float
    url: str
    title: str
    text: str
    published_at: dt.datetime | None
    language: str | None
    tags: list[str] = field(default_factory=list)


@dataclass
class DedupGroup:
    group_id: str
    representative_id: int
    member_ids: list[int]

    @property
    def size(self) -> int:
        return len(self.member_ids)


@dataclass
class RankedArticle:
    article: PipelineArticle
    score: float
    why: dict
    corroborating: list[PipelineArticle] = field(default_factory=list)


@dataclass
class ClusterSection:
    label: str
    items: list[RankedArticle]


@dataclass
class FinalDigestItem:
    article: PipelineArticle
    score: float
    why: dict
    summary: str
    cluster_label: str
    corroborating: list[PipelineArticle] = field(default_factory=list)
