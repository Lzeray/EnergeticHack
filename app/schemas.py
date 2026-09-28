from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class SourceIn(BaseModel):
    name: str
    type: str
    config: dict
    category: str | None = None
    priority: float = 1.0
    enabled: bool = True


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    config: dict
    category: str | None
    priority: float
    enabled: bool
    last_fetch_at: dt.datetime | None
    last_status: str
    last_error: str | None
    last_item_count: int


class ProfileIn(BaseModel):
    name: str
    audience: str = "custom"
    interests_text: str = ""


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    audience: str
    interests_text: str
    updated_at: dt.datetime


class FeedbackIn(BaseModel):
    profile_id: int
    article_id: int
    action: str  # like|dislike|save|dismiss
    rating: int | None = None


class DigestGenerateIn(BaseModel):
    profile_id: int
    period_type: str = "daily"  # daily|monthly
    source_ids: list[int] | None = None  # None = all enabled sources


class CompareIn(BaseModel):
    profile_a_id: int
    profile_b_id: int
    source_ids: list[int] | None = None
    limit_articles: int = 200
