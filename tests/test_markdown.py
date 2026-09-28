import datetime as dt
import re

from app.digest.markdown import render_markdown
from app.pipeline.types import FinalDigestItem, PipelineArticle

NOW = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")


def make_item(id_, title, url):
    article = PipelineArticle(
        id=id_, source_id=1, source_name="Test Source", source_priority=1.0,
        url=url, title=title, text="body", published_at=NOW, language="ru", tags=["CVE-2024-0001"],
    )
    return FinalDigestItem(article=article, score=0.8, why={"bm25": 0.8, "recency": 0.9, "source_trust": 0.5, "feedback": 0.0, "matched_keywords": ["cve"]}, summary="Краткое содержание.", cluster_label="Уязвимости")


def test_every_item_has_a_source_link():
    items = [make_item(1, "Title One", "https://a.example.com/1"), make_item(2, "Title Two", "https://b.example.com/2")]
    markdown = render_markdown("Профиль", "technical", "daily", NOW, {"source_count": 2, "considered_count": 2, "selected_count": 2, "dedup_merged_count": 0}, [("Уязвимости", items)])
    links = MARKDOWN_LINK_RE.findall(markdown)
    assert "https://a.example.com/1" in links
    assert "https://b.example.com/2" in links


def test_render_is_deterministic():
    items = [make_item(1, "Title One", "https://a.example.com/1")]
    stats = {"source_count": 1, "considered_count": 1, "selected_count": 1, "dedup_merged_count": 0}
    md1 = render_markdown("Профиль", "technical", "daily", NOW, stats, [("Уязвимости", items)])
    md2 = render_markdown("Профиль", "technical", "daily", NOW, stats, [("Уязвимости", items)])
    assert md1 == md2


def test_empty_digest_still_renders_valid_markdown():
    markdown = render_markdown("Профиль", "management", "monthly", NOW, {"source_count": 0, "considered_count": 0, "selected_count": 0, "dedup_merged_count": 0}, [])
    assert "дайджест" in markdown.lower()
    assert "не найдено" in markdown.lower()


def test_tags_are_rendered_as_inline_code():
    items = [make_item(1, "Title", "https://a.example.com/1")]
    markdown = render_markdown("П", "technical", "daily", NOW, {"source_count": 1, "considered_count": 1, "selected_count": 1, "dedup_merged_count": 0}, [("C", items)])
    assert "`CVE-2024-0001`" in markdown
