import json

import pytest

from app.sources.dataset import DatasetAdapter
from app.sources.proxy import ProxyAdapter
from app.sources.rss import RssAdapter
from app.sources.telegram import TelegramPublicAdapter
from app.sources.website import WebsiteAdapter

RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test</title>
<item><title>Critical RCE in Example Server</title><link>https://news.example.com/a1</link>
<guid>https://news.example.com/a1</guid><description><![CDATA[A critical remote code execution flaw was disclosed.]]></description>
<pubDate>Mon, 01 Sep 2025 10:00:00 GMT</pubDate></item>
</channel></rss>"""

TELEGRAM_HTML = """<div class="tgme_widget_message" data-post="testchan/42">
<div class="tgme_widget_message_text">Новый ransomware атакует облачные сервисы.\nПодробности внутри.</div>
<time datetime="2025-09-01T10:00:00+00:00"></time></div>"""

WEBSITE_HTML = """<html><body><ul>
<li class="post"><a href="/n/1">Supply chain attack hits popular library</a><p>Researchers found malicious code.</p></li>
</ul></body></html>"""


def test_rss_adapter_parses_entries():
    records = RssAdapter().parse(RSS_XML, {})
    assert len(records) == 1
    assert records[0].title == "Critical RCE in Example Server"
    assert records[0].url == "https://news.example.com/a1"
    assert records[0].published_at is not None


def test_rss_adapter_skips_entries_missing_title_or_link():
    xml = RSS_XML.replace("<link>https://news.example.com/a1</link>", "<link></link>")
    records = RssAdapter().parse(xml, {})
    assert records == []


def test_telegram_adapter_parses_public_preview():
    records = TelegramPublicAdapter().parse(TELEGRAM_HTML, {})
    assert len(records) == 1
    assert records[0].url == "https://t.me/testchan/42"
    assert "ransomware" in records[0].text.lower()


def test_website_adapter_extracts_headline_and_teaser():
    records = WebsiteAdapter().parse(WEBSITE_HTML, {"url": "https://news.example.com/"})
    assert len(records) == 1
    assert records[0].url == "https://news.example.com/n/1"
    assert records[0].text == "Researchers found malicious code."


def test_dataset_adapter_maps_custom_field_names():
    rows = [
        {
            "id": "1",
            "link": "https://news.example.com/d1",
            "headline": "CVE disclosed",
            "body": "Some text",
            "published": "2025-09-01T00:00:00Z",
        }
    ]
    records = DatasetAdapter().parse(json.dumps(rows), {"format": "json"})
    assert len(records) == 1
    assert records[0].title == "CVE disclosed"
    assert records[0].published_at is not None


def test_dataset_adapter_supports_csv():
    csv_text = "id,url,title,text\n1,https://news.example.com/c1,CSV title,CSV body\n"
    records = DatasetAdapter().parse(csv_text, {"format": "csv"})
    assert len(records) == 1
    assert records[0].title == "CSV title"


def test_proxy_adapter_navigates_nested_items_path():
    payload = json.dumps({"data": {"items": [{"id": "9", "url": "https://x.example.com/9", "title": "T", "text": "B"}]}})
    records = ProxyAdapter().parse(payload, {"items_path": "data.items"})
    assert len(records) == 1
    assert records[0].external_id == "9"


def test_dataset_adapter_refuses_paths_outside_fixtures(tmp_path):
    secret = tmp_path / "secret.json"
    secret.write_text("[]", encoding="utf-8")
    for path in [str(secret), "../../../etc/passwd", "../app.db"]:
        with pytest.raises(ValueError):
            DatasetAdapter().fetch_raw({"path": path})


def test_dataset_adapter_reads_fixture_by_relative_path():
    assert DatasetAdapter().fetch_raw({"path": "articles_sample.json"}).lstrip().startswith("[")
