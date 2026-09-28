import datetime as dt

from app.pipeline.dedup import compute_dedup_groups
from app.pipeline.types import PipelineArticle


def make_article(id_, title, url, hours_ago, source_id=1):
    now = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)
    return PipelineArticle(
        id=id_, source_id=source_id, source_name=f"src{source_id}", source_priority=1.0,
        url=url, title=title, text="body text", published_at=now - dt.timedelta(hours=hours_ago), language="ru",
    )


def test_exact_url_duplicates_are_merged():
    articles = [
        make_article(1, "Title A", "https://news.example.com/a", 1),
        make_article(2, "Title A (mirror)", "https://news.example.com/a?utm_source=x", 1, source_id=2),
    ]
    groups = compute_dedup_groups(articles)
    assert len(groups) == 1
    assert set(groups[0].member_ids) == {1, 2}


def test_fuzzy_near_duplicate_titles_within_window_are_merged():
    articles = [
        make_article(1, "Критическая уязвимость обнаружена в Kubernetes kubelet API", "https://a.example.com/1", 1, source_id=1),
        make_article(2, "Критическая уязвимость найдена в Kubernetes kubelet API", "https://b.example.com/2", 1.5, source_id=2),
    ]
    groups = compute_dedup_groups(articles, fuzzy_threshold=80)
    assert len(groups) == 1


def test_dissimilar_titles_are_not_merged():
    articles = [
        make_article(1, "Ransomware hits hospital network", "https://a.example.com/1", 1),
        make_article(2, "Fintech startup raises funding round", "https://b.example.com/2", 1),
    ]
    groups = compute_dedup_groups(articles)
    assert len(groups) == 2


def test_similar_titles_outside_time_window_are_not_merged():
    articles = [
        make_article(1, "Critical vulnerability disclosed in popular library", "https://a.example.com/1", 1),
        make_article(2, "Critical vulnerability disclosed in popular library", "https://b.example.com/2", 200),
    ]
    groups = compute_dedup_groups(articles, window_hours=72)
    assert len(groups) == 2


def test_representative_prefers_earliest_publication():
    articles = [
        make_article(1, "Same story here", "https://a.example.com/1", 5),
        make_article(2, "Same story here", "https://b.example.com/2", 10),
    ]
    groups = compute_dedup_groups(articles, fuzzy_threshold=80)
    assert len(groups) == 1
    assert groups[0].representative_id == 2  # published earlier (10h ago vs 5h ago)
