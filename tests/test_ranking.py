import datetime as dt

from app.pipeline.ranking import parse_profile_interests, rank_articles, select_diverse_top_k, tokenize
from app.pipeline.types import PipelineArticle

NOW = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)


def art(id_, title, text, hours_ago=1.0, source_id=1, source_priority=1.0):
    return PipelineArticle(
        id=id_, source_id=source_id, source_name=f"src{source_id}", source_priority=source_priority,
        url=f"https://news.example.com/{id_}", title=title, text=text,
        published_at=NOW - dt.timedelta(hours=hours_ago), language="ru",
    )


def test_parse_profile_interests_splits_exclude_section():
    text = "Приоритет: CVE, ransomware. Исключить: гаджеты, инвестиции"
    query, excludes = parse_profile_interests(text)
    assert "CVE" in query
    assert excludes == ["гаджеты", "инвестиции"]


def test_parse_profile_interests_without_exclude_section():
    query, excludes = parse_profile_interests("Приоритет: Kubernetes, CI/CD")
    assert query == "Приоритет: Kubernetes, CI/CD"
    assert excludes == []


ARTICLES = [
    art(1, "Критическая уязвимость CVE-2024-12345 в Kubernetes kubelet", "RCE в kubelet API, срочно обновите кластеры."),
    art(2, "Ransomware атакует медицинские учреждения", "Группировка шифрует данные больниц, требуя выкуп."),
    art(3, "Инвестиции в финтех выросли на этой неделе", "Стартапы привлекли финансирование в секторе финтех."),
    art(4, "Новый гаджет для умного дома", "Компания представила новую линейку смарт-колонок."),
]


def test_excluded_terms_are_hard_filtered_out():
    profile = "Приоритет: CVE, ransomware, Kubernetes. Исключить: гаджеты, инвестиции"
    ranked = rank_articles(ARTICLES, profile, reference_time=NOW)
    titles = [r.article.title.lower() for r in ranked]
    assert not any("гаджет" in t for t in titles)
    assert not any("инвестиции" in t or "финтех" in t for t in titles)


def test_relevant_articles_rank_above_irrelevant_ones():
    profile = "Приоритет: CVE, ransomware, Kubernetes."
    ranked = rank_articles(ARTICLES, profile, reference_time=NOW)
    ranked_ids = [r.article.id for r in ranked]
    assert ranked_ids.index(1) < ranked_ids.index(3)
    assert ranked_ids.index(2) < ranked_ids.index(3)


def test_changing_profile_changes_top_result():
    profile_security = "Приоритет: ransomware, шифровальщик, больница"
    profile_other = "Приоритет: финтех, инвестиции, стартап"
    ranked_a = rank_articles(ARTICLES, profile_security, reference_time=NOW)
    ranked_b = rank_articles(ARTICLES, profile_other, reference_time=NOW)
    assert ranked_a[0].article.id != ranked_b[0].article.id


def test_feedback_boosts_matching_future_articles():
    from collections import Counter

    liked = Counter(tokenize("ransomware шифрует больниц"))
    ranked_with_feedback = rank_articles(ARTICLES, "Приоритет: общие новости", liked_tokens=liked, reference_time=NOW)
    ranked_without = rank_articles(ARTICLES, "Приоритет: общие новости", reference_time=NOW)
    score_with = next(r.score for r in ranked_with_feedback if r.article.id == 2)
    score_without = next(r.score for r in ranked_without if r.article.id == 2)
    assert score_with > score_without


def test_select_diverse_top_k_bypasses_cap_when_no_other_source_can_fill_slots():
    # A single-source corpus: capping would just shrink the digest for no
    # benefit, so all k slots get filled from the one available source.
    articles = [art(i, f"Story {i}", "CVE ransomware Kubernetes text " * 3, source_id=1) for i in range(10)]
    ranked = rank_articles(articles, "Приоритет: CVE ransomware Kubernetes", reference_time=NOW)
    selected = select_diverse_top_k(ranked, k=10, max_per_source_ratio=0.4)
    assert len(selected) == 10


def test_select_diverse_top_k_does_not_let_dominant_source_crowd_out_a_relevant_minor_one():
    # A prolific source with 20 relevant articles competes against a small
    # source with only 3, equally relevant, articles. Without the cap, a
    # source with this much more supply could take every top-k slot;
    # capping it guarantees the minor source's relevant items still surface.
    dominant = [art(i, f"Dominant story {i}", "CVE ransomware Kubernetes уязвимость атака", source_id=1) for i in range(20)]
    minor = [art(100 + i, f"Minor story {i}", "CVE ransomware Kubernetes уязвимость атака", source_id=2) for i in range(3)]
    ranked = rank_articles(dominant + minor, "Приоритет: CVE ransomware Kubernetes", reference_time=NOW)
    selected = select_diverse_top_k(ranked, k=7, max_per_source_ratio=0.4)
    from collections import Counter

    counts = Counter(r.article.source_id for r in selected)
    assert len(selected) == 7
    assert counts[1] <= 4  # ceil(7 * 0.4): the dominant source is capped
    assert counts[2] == 3  # all of the minor source's relevant items still make it in


def test_why_breakdown_contains_expected_keys():
    ranked = rank_articles(ARTICLES, "Приоритет: CVE Kubernetes", reference_time=NOW)
    why = ranked[0].why
    assert set(why) == {"bm25", "recency", "source_trust", "feedback", "matched_keywords"}
