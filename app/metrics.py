from __future__ import annotations

import datetime as dt
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

READ_MINUTES_PER_CONSIDERED_ARTICLE = 3.0
READ_MINUTES_PER_DIGEST_ITEM = 1.0


def _latest_digest_run(session: Session, profile_id: int) -> models.DigestRun | None:
    return session.execute(
        select(models.DigestRun)
        .where(models.DigestRun.profile_id == profile_id)
        .order_by(models.DigestRun.generated_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _precision_at_k(session: Session, digest_run: models.DigestRun, k: int = 10) -> float | None:
    items = sorted(digest_run.items, key=lambda i: i.order_index)[:k]
    if not items:
        return None
    article_ids = [i.article_id for i in items]
    feedback_rows = session.execute(
        select(models.Feedback).where(
            models.Feedback.profile_id == digest_run.profile_id,
            models.Feedback.article_id.in_(article_ids),
        )
    ).scalars()
    labeled: dict[int, bool] = {}
    for fb in feedback_rows:
        positive = fb.action in ("like", "save") or (fb.rating or 0) >= 4
        negative = fb.action in ("dislike", "dismiss") or 1 <= (fb.rating or 0) <= 2
        if positive:
            labeled[fb.article_id] = True
        elif negative:
            labeled.setdefault(fb.article_id, False)
    if not labeled:
        return None
    return sum(1 for v in labeled.values() if v) / len(labeled)


def compute_profile_metrics(session: Session, profile: models.Profile) -> dict:
    digest_run = _latest_digest_run(session, profile.id)
    if digest_run is None:
        return {
            "profile_id": profile.id,
            "profile_name": profile.name,
            "has_digest": False,
        }

    stats = digest_run.stats or {}
    considered = stats.get("considered_count", 0)
    selected = stats.get("selected_count", 0)
    dedup_merged = stats.get("dedup_merged_count", 0)
    now = dt.datetime.now(dt.timezone.utc)

    ages_hours = []
    for item in digest_run.items:
        published = item.article.published_at
        if published is None:
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=dt.timezone.utc)
        gen = digest_run.generated_at if digest_run.generated_at.tzinfo else digest_run.generated_at.replace(tzinfo=dt.timezone.utc)
        ages_hours.append((gen - published).total_seconds() / 3600.0)
    avg_age_hours = sum(ages_hours) / len(ages_hours) if ages_hours else None

    time_saved_minutes = (
        considered * READ_MINUTES_PER_CONSIDERED_ARTICLE - selected * READ_MINUTES_PER_DIGEST_ITEM
    )

    return {
        "profile_id": profile.id,
        "profile_name": profile.name,
        "has_digest": True,
        "generated_at": digest_run.generated_at,
        "considered_count": considered,
        "selected_count": selected,
        "duplicate_rate": round(dedup_merged / considered, 3) if considered else 0.0,
        "precision_at_10": _precision_at_k(session, digest_run),
        "avg_selected_age_hours": round(avg_age_hours, 1) if avg_age_hours is not None else None,
        "estimated_minutes_saved": round(max(0.0, time_saved_minutes), 1),
        "source_count": stats.get("source_count", 0),
    }


def compute_service_metrics(session: Session) -> dict:
    profiles = list(session.execute(select(models.Profile)).scalars())
    per_profile = [compute_profile_metrics(session, p) for p in profiles]

    sources = list(session.execute(select(models.Source)).scalars())
    articles = list(session.execute(select(models.Article)).scalars())
    language_counts = Counter(a.language or "unknown" for a in articles)
    category_counts = Counter(s.category or "uncategorized" for s in sources)
    healthy_sources = sum(1 for s in sources if s.last_status == "ok")

    digest_runs_total = session.execute(select(models.DigestRun)).scalars().all()
    feedback_total = session.execute(select(models.Feedback)).scalars().all()

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc),
        "per_profile": per_profile,
        "source_count": len(sources),
        "healthy_source_count": healthy_sources,
        "source_category_coverage": dict(category_counts),
        "language_coverage": dict(language_counts),
        "article_count": len(articles),
        "digest_runs_total": len(digest_runs_total),
        "feedback_count": len(feedback_total),
    }
