from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(32))  # rss|website|telegram|dataset|proxy
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetch_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(16), default="never")  # never|ok|error
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    articles: Mapped[list["Article"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_article_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    external_id: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_meta: Mapped[dict] = mapped_column(JSON, default=dict)

    source: Mapped[Source] = relationship(back_populates="articles")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    audience: Mapped[str] = mapped_column(String(16), default="custom")  # technical|management|custom
    interests_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    action: Mapped[str] = mapped_column(String(16))  # like|dislike|save|dismiss
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DigestRun(Base):
    __tablename__ = "digest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    period_type: Mapped[str] = mapped_column(String(16))  # daily|monthly
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    markdown_path: Mapped[str] = mapped_column(Text)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)

    items: Mapped[list["DigestArticle"]] = relationship(back_populates="digest_run", cascade="all, delete-orphan")
    profile: Mapped[Profile] = relationship()


class DigestArticle(Base):
    __tablename__ = "digest_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_run_id: Mapped[int] = mapped_column(ForeignKey("digest_runs.id"))
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    cluster_label: Mapped[str] = mapped_column(String(255), default="")
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    why: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    digest_run: Mapped[DigestRun] = relationship(back_populates="items")
    article: Mapped[Article] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
