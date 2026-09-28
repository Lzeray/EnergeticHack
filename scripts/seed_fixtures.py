"""Seeds the database with a demo corpus and demo profiles from
data/fixtures/articles_sample.json, so the app is immediately usable without
live network access. Safe to re-run: it is idempotent on (source name) and
(profile name).

Usage: python -m scripts.seed_fixtures
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app import models
from app.config import settings
from app.db import SessionLocal, init_db
from app.pipeline.normalize import extract_security_tags

DEMO_PROFILES = [
    {
        "name": "Технический дайджест (ежедневно)",
        "audience": "technical",
        "interests_text": (
            "Я технический специалист по ИТ/ИБ. Приоритет: активно эксплуатируемые "
            "уязвимости (CVE), атаки шифровальщиков-вымогателей, supply-chain и "
            "APT-атаки, уязвимости в облачной и контейнерной инфраструктуре "
            "(Kubernetes, CI/CD), рекомендации по устранению. "
            "Исключить: гаджеты, инвестиции, общие новости ИИ без связи с защитой информации."
        ),
    },
    {
        "name": "Сводка для менеджмента (ежемесячно)",
        "audience": "management",
        "interests_text": (
            "Я руковожу подразделением и мне нужна деловая сводка по кибербезопасности: "
            "крупные инциденты и их бизнес-последствия, регуляторные штрафы, тренды "
            "атак на отрасль, ключевые уязвимости, требующие внимания руководства. "
            "Исключить: гаджеты, глубокие технические детали эксплойтов."
        ),
    },
    {
        "name": "Демо: SOC-аналитик",
        "audience": "custom",
        "interests_text": (
            "Я аналитик SOC. Приоритет: активно эксплуатируемые CVE, ransomware, APT, "
            "фишинг, реагирование на инциденты, бюллетени регуляторов. "
            "Исключить: гаджеты, инвестиции, финтех."
        ),
    },
    {
        "name": "Демо: Platform/AppSec-инженер",
        "audience": "custom",
        "interests_text": (
            "Я platform/AppSec-инженер. Приоритет: Kubernetes, контейнеры, "
            "software supply chain, CI/CD, секреты, облачный IAM, уязвимости библиотек. "
            "Исключить: гаджеты, инвестиции, финтех."
        ),
    },
]


def _get_or_create_source(session, name: str, source_type: str, category: str, priority: float) -> models.Source:
    existing = session.execute(select(models.Source).where(models.Source.name == name)).scalar_one_or_none()
    if existing:
        return existing
    source = models.Source(
        name=name,
        type=source_type,
        config={"path": "articles_sample.json", "seeded": True},
        category=category,
        priority=priority,
        enabled=True,
        last_status="ok",
        last_fetch_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(source)
    session.flush()
    return source


def _get_or_create_profile(session, spec: dict) -> models.Profile:
    existing = session.execute(select(models.Profile).where(models.Profile.name == spec["name"])).scalar_one_or_none()
    if existing:
        return existing
    profile = models.Profile(name=spec["name"], audience=spec["audience"], interests_text=spec["interests_text"])
    session.add(profile)
    session.flush()
    return profile


def seed() -> None:
    init_db()
    records = json.loads((settings.fixtures_dir / "articles_sample.json").read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)

    with SessionLocal() as session:
        created_articles = 0
        for row in records:
            source = _get_or_create_source(
                session, row["source_name"], row["source_type"], row["source_category"], row["source_priority"]
            )
            exists = session.execute(
                select(models.Article).where(
                    models.Article.source_id == source.id, models.Article.external_id == row["id"]
                )
            ).scalar_one_or_none()
            if exists:
                continue
            tags = row.get("tags") or extract_security_tags(row["text"])
            article = models.Article(
                source_id=source.id,
                external_id=row["id"],
                url=row["url"],
                title=row["title"],
                text=row["text"],
                published_at=now - dt.timedelta(hours=row["hours_ago"]),
                language=row.get("language"),
                tags=tags,
                raw_meta={},
            )
            session.add(article)
            created_articles += 1

        for spec in DEMO_PROFILES:
            _get_or_create_profile(session, spec)

        session.commit()
        print(f"Seeded {created_articles} new article(s). Profiles ready: {[p['name'] for p in DEMO_PROFILES]}")


if __name__ == "__main__":
    seed()
