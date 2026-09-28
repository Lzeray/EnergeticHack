import datetime as dt

from app.pipeline.clustering import cluster_articles
from app.pipeline.ranking import rank_articles
from app.pipeline.types import PipelineArticle

NOW = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)


def art(id_, title, text):
    return PipelineArticle(
        id=id_, source_id=1, source_name="src", source_priority=1.0,
        url=f"https://news.example.com/{id_}", title=title, text=text,
        published_at=NOW, language="ru",
    )


def test_small_corpus_falls_back_to_single_section():
    ranked = rank_articles([art(1, "Только одна новость", "текст")], "Приоритет: всё", reference_time=NOW)
    sections = cluster_articles(ranked)
    assert len(sections) == 1
    assert sections[0].label == "Общее"


def test_empty_corpus_returns_no_sections():
    assert cluster_articles([]) == []


def test_clustering_groups_similar_topics_together():
    articles = [
        art(1, "Ransomware атакует больницы Европы", "Группировка шифрует данные медучреждений и требует выкуп."),
        art(2, "Новая волна атак шифровальщиков на медицину", "Шифровальщик поразил несколько больниц подряд."),
        art(3, "Kubernetes kubelet API уязвимость RCE", "Небезопасная конфигурация kubelet допускает выполнение кода."),
        art(4, "Критическая уязвимость в Kubernetes API server", "Уязвимость API server Kubernetes позволяет RCE."),
        art(5, "Финтех стартап привлёк инвестиции", "Компания закрыла раунд финансирования."),
        art(6, "Раунд инвестиций в финтех вырос", "Финтех-сектор привлёк больше капитала на этой неделе."),
    ]
    ranked = rank_articles(articles, "Приоритет: всё", reference_time=NOW)
    sections = cluster_articles(ranked, min_clusters=2, max_clusters=4)
    assert len(sections) >= 2
    total_items = sum(len(s.items) for s in sections)
    assert total_items == len(articles)
    for section in sections:
        assert section.label  # every section has a non-empty label
