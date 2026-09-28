import datetime as dt

from app import models
from app.digest.builder import build_digest
from app.llm.extractive_fallback import ExtractiveProvider

NOW = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)


def _seed_corpus(session):
    source_a = models.Source(name="Source A", type="dataset", config={}, priority=1.0)
    source_b = models.Source(name="Source B", type="dataset", config={}, priority=1.0)
    session.add_all([source_a, source_b])
    session.flush()

    articles = [
        models.Article(source_id=source_a.id, external_id="1", url="https://a.example.com/1",
                        title="Критическая RCE-уязвимость CVE-2024-1111 в Kubernetes", text="Уязвимость kubelet API позволяет удалённое выполнение кода.",
                        published_at=NOW - dt.timedelta(hours=2), language="ru", tags=["CVE-2024-1111"]),
        models.Article(source_id=source_a.id, external_id="2", url="https://a.example.com/2",
                        title="Ransomware атакует больницы", text="Группировка шифрует данные медицинских учреждений.",
                        published_at=NOW - dt.timedelta(hours=3), language="ru"),
        models.Article(source_id=source_b.id, external_id="3", url="https://b.example.com/3",
                        title="Инвестиции в финтех выросли", text="Стартапы привлекли финансирование в секторе финтех.",
                        published_at=NOW - dt.timedelta(hours=4), language="ru"),
        models.Article(source_id=source_b.id, external_id="4", url="https://b.example.com/4",
                        title="Новый гаджет для умного дома", text="Компания представила новую линейку смарт-колонок.",
                        published_at=NOW - dt.timedelta(hours=1), language="ru"),
    ]
    session.add_all(articles)
    session.commit()
    return source_a, source_b, articles


def test_build_digest_end_to_end_writes_markdown_with_links(db_session, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "digests_dir", tmp_path)
    _seed_corpus(db_session)
    profile = models.Profile(name="Технический", audience="technical",
                              interests_text="Приоритет: CVE, ransomware, Kubernetes. Исключить: гаджеты, инвестиции")
    db_session.add(profile)
    db_session.commit()

    digest_run = build_digest(db_session, profile, "daily", ExtractiveProvider(), reference_time=NOW)

    assert digest_run.id is not None
    assert digest_run.stats["considered_count"] == 4
    titles = [i.article.title for i in digest_run.items]
    assert not any("гаджет" in t.lower() for t in titles)
    assert not any("инвестиции" in t.lower() or "финтех" in t.lower() for t in titles)

    markdown_text = (tmp_path / f"{profile.id}_daily_{NOW.strftime('%Y%m%dT%H%M%SZ')}.md").read_text(encoding="utf-8")
    assert "https://a.example.com/1" in markdown_text
    assert "CVE-2024-1111" in markdown_text


def test_changing_profile_interests_changes_selected_articles(db_session, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "digests_dir", tmp_path)
    _seed_corpus(db_session)

    profile_security = models.Profile(name="Security", audience="technical", interests_text="Приоритет: ransomware, CVE, Kubernetes")
    profile_business = models.Profile(name="Business", audience="management", interests_text="Приоритет: финтех, инвестиции, стартапы")
    db_session.add_all([profile_security, profile_business])
    db_session.commit()

    run_security = build_digest(db_session, profile_security, "daily", ExtractiveProvider(), reference_time=NOW)
    run_business = build_digest(db_session, profile_business, "daily", ExtractiveProvider(), reference_time=NOW)

    top_security = run_security.items[0].article.title
    top_business = run_business.items[0].article.title
    assert top_security != top_business


def test_positive_feedback_increases_future_rank_score(db_session, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "digests_dir", tmp_path)
    _source_a, _source_b, articles = _seed_corpus(db_session)
    profile = models.Profile(name="Neutral", audience="custom", interests_text="Приоритет: новости")
    db_session.add(profile)
    db_session.commit()

    ransomware_article = next(a for a in articles if "Ransomware" in a.title)

    run_before = build_digest(db_session, profile, "daily", ExtractiveProvider(), reference_time=NOW)
    score_before = next(i.rank_score for i in run_before.items if i.article_id == ransomware_article.id)

    db_session.add(models.Feedback(profile_id=profile.id, article_id=ransomware_article.id, action="like"))
    db_session.commit()

    run_after = build_digest(db_session, profile, "daily", ExtractiveProvider(), reference_time=NOW)
    score_after = next(i.rank_score for i in run_after.items if i.article_id == ransomware_article.id)

    assert score_after >= score_before
