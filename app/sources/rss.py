from __future__ import annotations

import hashlib

import feedparser

from app.sources.base import SourceAdapter, SourceRecord
from app.sources.util import strip_html, struct_time_to_dt


class RssAdapter(SourceAdapter):
    type_name = "rss"

    def parse(self, raw: str, config: dict) -> list[SourceRecord]:
        parsed = feedparser.parse(raw)
        records: list[SourceRecord] = []
        for entry in parsed.entries:
            url = entry.get("link", "") or ""
            title = strip_html(entry.get("title", "")).strip()
            body_html = entry.get("summary", "") or entry.get("description", "")
            if not body_html and entry.get("content"):
                body_html = entry["content"][0].get("value", "")
            text = strip_html(body_html)
            published_at = struct_time_to_dt(entry.get("published_parsed") or entry.get("updated_parsed"))
            external_id = entry.get("id") or entry.get("guid") or url
            if not external_id:
                external_id = hashlib.sha1(title.encode("utf-8")).hexdigest()
            tags = [t.get("term", "") for t in entry.get("tags", [])] if entry.get("tags") else []
            if not title or not url:
                continue
            records.append(
                SourceRecord(
                    external_id=str(external_id),
                    url=url,
                    title=title,
                    text=text,
                    published_at=published_at,
                    raw={"feed_tags": tags, "author": entry.get("author", "")},
                )
            )
        return records
