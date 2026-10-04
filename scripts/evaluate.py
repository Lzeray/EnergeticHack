from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app import models
from app.config import settings
from app.db import SessionLocal, init_db
from app.digest.builder import to_pipeline_article
from app.pipeline.ranking import rank_articles
from scripts.seed_fixtures import seed

K_VALUES = (5, 10)


def precision_recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> tuple[float, float]:
    top_k = ranked_ids[:k]
    hits = sum(1 for article_id in top_k if article_id in relevant_ids)
    precision = hits / len(top_k) if top_k else 0.0
    recall = hits / len(relevant_ids) if relevant_ids else 0.0
    return precision, recall


def main() -> None:
    init_db()
    seed()

    golden = json.loads((settings.fixtures_dir / "golden_labels.json").read_text(encoding="utf-8"))
    golden.pop("_comment", None)

    with SessionLocal() as session:
        for profile_name, labels in golden.items():
            profile = session.execute(
                select(models.Profile).where(models.Profile.name == profile_name)
            ).scalar_one_or_none()
            if not profile:
                print(f"[skip] profile not found: {profile_name}")
                continue

            articles = session.execute(
                select(models.Article).where(models.Article.external_id.in_(labels.keys()))
            ).scalars().all()
            if len(articles) != len(labels):
                print(f"[warn] {profile_name}: {len(labels)} labeled but only {len(articles)} found in DB")

            pipeline_articles = [to_pipeline_article(a) for a in articles]
            external_id_by_pk = {a.id: a.external_id for a in articles}

            ranked = rank_articles(pipeline_articles, profile.interests_text)
            ranked_external_ids = [external_id_by_pk[r.article.id] for r in ranked]
            relevant_ids = {ext_id for ext_id, label in labels.items() if label == 1}

            print(f"\n{profile_name}")
            print(f"  размечено: {len(labels)} статей, релевантных: {len(relevant_ids)}")
            for k in K_VALUES:
                precision, recall = precision_recall_at_k(ranked_external_ids, relevant_ids, k)
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
                print(f"  precision@{k}: {precision:.2f}  recall@{k}: {recall:.2f}  f1@{k}: {f1:.2f}")


if __name__ == "__main__":
    main()
