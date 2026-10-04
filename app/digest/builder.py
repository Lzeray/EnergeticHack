from __future__ import annotations

import datetime as dt
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.digest.action import derive_action_line
from app.digest.markdown import render_markdown
from app.llm.base import LLMProvider
from app.pipeline.clustering import cluster_articles
from app.pipeline.dedup import compute_dedup_groups
from app.pipeline.ranking import rank_articles, select_diverse_top_k, tokenize
from app.pipeline.types import FinalDigestItem, PipelineArticle, RankedArticle

LOOKBACK_HOURS = {"daily": 48, "monthly": 24 * 31}
RECENCY_HALF_LIFE_HOURS = {"daily": 48.0, "monthly": 24 * 20.0}


class SelectionResult:
    def __init__(
        self,
        pipeline_articles: list[PipelineArticle],
        dedup_groups: list,
        corroborating_by_rep: dict[int, list[PipelineArticle]],
        ranked: list[RankedArticle],
        selected: list[RankedArticle],
    ):
        self.pipeline_articles = pipeline_articles
        self.dedup_groups = dedup_groups
        self.corroborating_by_rep = corroborating_by_rep
        self.ranked = ranked
        self.selected = selected

    @property
    def stats(self) -> dict:
        return {
            "source_count": len({a.source_id for a in self.pipeline_articles}),
            "considered_count": len(self.pipeline_articles),
            "selected_count": len(self.selected),
            "dedup_merged_count": len(self.pipeline_articles) - len(self.dedup_groups),
        }


def _as_utc(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def to_pipeline_article(article: models.Article) -> PipelineArticle:
    return PipelineArticle(
        id=article.id,
        source_id=article.source_id,
        source_name=article.source.name if article.source else str(article.source_id),
        source_priority=article.source.priority if article.source else 1.0,
        url=article.url,
        title=article.title,
        text=article.text,
        published_at=_as_utc(article.published_at),
        language=article.language,
        tags=list(article.tags or []),
    )


def _effective_time(article: models.Article) -> dt.datetime:
    ts = article.published_at or article.fetched_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts


def _candidate_articles(session: Session, source_ids: list[int] | None, period_type: str, reference_time: dt.datetime) -> list[models.Article]:
    query = select(models.Article).join(models.Source).where(models.Source.enabled.is_(True))
    if source_ids:
        query = query.where(models.Article.source_id.in_(source_ids))
    articles = list(session.execute(query).scalars())
    cutoff = reference_time - dt.timedelta(hours=LOOKBACK_HOURS.get(period_type, 48))
    return [a for a in articles if _effective_time(a) >= cutoff]


def _feedback_token_counters(session: Session, profile_id: int) -> tuple[Counter, Counter]:
    liked: Counter = Counter()
    disliked: Counter = Counter()
    rows = session.execute(
        select(models.Feedback, models.Article)
        .join(models.Article, models.Article.id == models.Feedback.article_id)
        .where(models.Feedback.profile_id == profile_id)
    ).all()
    for feedback, article in rows:
        tokens = tokenize(f"{article.title} {article.text}")
        is_positive = feedback.action in ("like", "save") or (feedback.rating or 0) >= 4
        is_negative = feedback.action in ("dislike", "dismiss") or 1 <= (feedback.rating or 0) <= 2
        if is_positive:
            liked.update(tokens)
        elif is_negative:
            disliked.update(tokens)
    return liked, disliked


def select_for_profile(
    session: Session,
    profile: models.Profile,
    period_type: str,
    source_ids: list[int] | None = None,
    reference_time: dt.datetime | None = None,
) -> SelectionResult:
    reference_time = reference_time or dt.datetime.now(dt.timezone.utc)
    top_k = settings.daily_top_k if period_type == "daily" else settings.monthly_top_k
    half_life = RECENCY_HALF_LIFE_HOURS.get(period_type, 48.0)

    db_articles = _candidate_articles(session, source_ids, period_type, reference_time)
    pipeline_articles = [to_pipeline_article(a) for a in db_articles]
    by_id = {a.id: a for a in pipeline_articles}

    dedup_groups = compute_dedup_groups(
        pipeline_articles,
        fuzzy_threshold=settings.dedup_fuzzy_threshold,
        window_hours=settings.dedup_window_hours,
    )
    representative_ids = {g.representative_id for g in dedup_groups}
    corroborating_by_rep: dict[int, list[PipelineArticle]] = {
        g.representative_id: [by_id[m] for m in g.member_ids if m != g.representative_id and m in by_id]
        for g in dedup_groups
    }
    representatives = [by_id[rid] for rid in representative_ids if rid in by_id]

    liked_tokens, disliked_tokens = _feedback_token_counters(session, profile.id)
    ranked = rank_articles(
        representatives,
        profile.interests_text,
        liked_tokens=liked_tokens,
        disliked_tokens=disliked_tokens,
        reference_time=reference_time,
        recency_half_life_hours=half_life,
    )
    selected = select_diverse_top_k(ranked, k=top_k, max_per_source_ratio=settings.max_items_per_source_ratio)
    return SelectionResult(pipeline_articles, dedup_groups, corroborating_by_rep, ranked, selected)


def build_digest(
    session: Session,
    profile: models.Profile,
    period_type: str,
    llm_provider: LLMProvider,
    source_ids: list[int] | None = None,
    reference_time: dt.datetime | None = None,
) -> models.DigestRun:
    reference_time = reference_time or dt.datetime.now(dt.timezone.utc)
    selection = select_for_profile(session, profile, period_type, source_ids, reference_time)
    selected = selection.selected
    corroborating_by_rep = selection.corroborating_by_rep

    clusters = cluster_articles(selected)
    audience = profile.audience if profile.audience in ("technical", "management") else "technical"

    final_clusters: list[tuple[str, list[FinalDigestItem]]] = []
    order_index = 0
    digest_items: list[FinalDigestItem] = []
    for section in clusters:
        titles = [i.article.title for i in section.items]
        label = section.label
        if len(section.items) >= 2:
            label = llm_provider.label_cluster(titles) or section.label
        rendered_items: list[FinalDigestItem] = []
        for ranked_item in section.items:
            summary = llm_provider.summarize(ranked_item.article.title, ranked_item.article.text, audience)
            item = FinalDigestItem(
                article=ranked_item.article,
                score=ranked_item.score,
                why=ranked_item.why,
                summary=summary,
                cluster_label=label,
                action=derive_action_line(ranked_item.article, audience),
                corroborating=corroborating_by_rep.get(ranked_item.article.id, []),
            )
            rendered_items.append(item)
            digest_items.append(item)
            order_index += 1
        final_clusters.append((label, rendered_items))

    stats = selection.stats

    markdown = render_markdown(profile.name, audience, period_type, reference_time, stats, final_clusters)

    timestamp = reference_time.strftime("%Y%m%dT%H%M%SZ")
    filename = f"{profile.id}_{period_type}_{timestamp}.md"
    path = settings.digests_dir / filename
    path.write_text(markdown, encoding="utf-8")
    latest_path = settings.digests_dir / f"latest_{profile.id}_{period_type}.md"
    latest_path.write_text(markdown, encoding="utf-8")

    digest_run = models.DigestRun(
        profile_id=profile.id,
        period_type=period_type,
        generated_at=reference_time,
        markdown_path=str(path),
        stats=stats,
    )
    session.add(digest_run)
    session.flush()

    for idx, item in enumerate(digest_items):
        session.add(
            models.DigestArticle(
                digest_run_id=digest_run.id,
                article_id=item.article.id,
                cluster_label=item.cluster_label,
                rank_score=item.score,
                why=item.why,
                summary=item.summary,
                action=item.action,
                order_index=idx,
            )
        )
    session.commit()
    session.refresh(digest_run)
    return digest_run
