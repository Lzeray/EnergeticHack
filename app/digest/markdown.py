from __future__ import annotations

import datetime as dt

from app.pipeline.types import FinalDigestItem

AUDIENCE_LABELS = {"technical": "технические специалисты", "management": "менеджмент", "custom": "профиль"}
PERIOD_LABELS = {"daily": "ежедневный", "monthly": "ежемесячный"}


def _fmt_dt(value: dt.datetime | None) -> str:
    if value is None:
        return "дата неизвестна"
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _why_line(why: dict) -> str:
    parts = [
        f"релевантность {why.get('bm25', 0):.2f}",
        f"свежесть {why.get('recency', 0):.2f}",
        f"доверие к источнику {why.get('source_trust', 0):.2f}",
    ]
    feedback = why.get("feedback", 0)
    if feedback:
        parts.append(f"фидбек {feedback:+.2f}")
    keywords = why.get("matched_keywords") or []
    if keywords:
        parts.append("совпадения: " + ", ".join(keywords))
    return "; ".join(parts)


def render_markdown(
    profile_name: str,
    audience: str,
    period_type: str,
    generated_at: dt.datetime,
    stats: dict,
    clusters: list[tuple[str, list[FinalDigestItem]]],
) -> str:
    audience_label = AUDIENCE_LABELS.get(audience, audience)
    period_label = PERIOD_LABELS.get(period_type, period_type)

    lines: list[str] = []
    lines.append(f"# ИТ/ИБ-дайджест — {audience_label} — {period_label}")
    lines.append("")
    lines.append(f"*Профиль:* {profile_name}  ")
    lines.append(f"*Сгенерировано:* {_fmt_dt(generated_at)}  ")
    lines.append(
        f"*Источников:* {stats.get('source_count', 0)} · "
        f"*Материалов рассмотрено:* {stats.get('considered_count', 0)} · "
        f"*Отобрано:* {stats.get('selected_count', 0)} · "
        f"*Дублей объединено:* {stats.get('dedup_merged_count', 0)}"
    )
    lines.append("")

    if not clusters:
        lines.append("_За этот период не найдено релевантных материалов по заданному профилю интересов._")
        return "\n".join(lines) + "\n"

    for cluster_label, items in clusters:
        lines.append(f"## {cluster_label}")
        lines.append("")
        for item in items:
            art = item.article
            lines.append(f"### [{art.title}]({art.url})")
            lines.append("")
            lines.append(item.summary.strip())
            lines.append("")
            lines.append(f"- Источник: [{art.source_name}]({art.url}) · {_fmt_dt(art.published_at)}")
            lines.append(f"- Почему выбрано: {_why_line(item.why)}")
            if art.tags:
                tags_str = ", ".join(f"`{t}`" for t in art.tags)
                lines.append(f"- Теги: {tags_str}")
            if item.corroborating:
                links = ", ".join(f"[{c.source_name}]({c.url})" for c in item.corroborating)
                lines.append(f"- Похожие публикации: {links}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
