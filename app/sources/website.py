from __future__ import annotations

import hashlib

from bs4 import BeautifulSoup

from app.sources.base import SourceAdapter, SourceRecord
from app.sources.util import absolute_url, strip_html

DEFAULT_ITEM_SELECTOR = "article, .post, .news-item, li"
DEFAULT_LINK_SELECTOR = "a"


class WebsiteAdapter(SourceAdapter):
    """Best-effort generic listing-page scraper.

    Extracts headline + URL + optional teaser text straight from a listing/index
    page using configurable CSS selectors. It intentionally does NOT crawl into
    each article (that would break the fetch/parse purity used for testing) —
    prefer the RSS adapter, or set a per-site selector tuple, for full body text.

    config: {
      "url": str,
      "item_selector"?: str,   # container per headline, default "article, .post, .news-item, li"
      "link_selector"?: str,   # <a> within the item, default "a"
      "title_selector"?: str,  # optional heading selector within the item
      "excerpt_selector"?: str # optional teaser <p> selector within the item
    }
    """

    type_name = "website"

    def parse(self, raw: str, config: dict) -> list[SourceRecord]:
        base_url = config["url"]
        item_selector = config.get("item_selector", DEFAULT_ITEM_SELECTOR)
        link_selector = config.get("link_selector", DEFAULT_LINK_SELECTOR)
        title_selector = config.get("title_selector")
        excerpt_selector = config.get("excerpt_selector")

        soup = BeautifulSoup(raw, "lxml")
        seen_urls: set[str] = set()
        records: list[SourceRecord] = []

        for item in soup.select(item_selector):
            link = item.select_one(link_selector)
            if link is None or not link.get("href"):
                continue
            url = absolute_url(base_url, link["href"])
            if url in seen_urls:
                continue

            title_el = item.select_one(title_selector) if title_selector else None
            title = strip_html(str(title_el)) if title_el else strip_html(link.get_text())
            title = title.strip()
            if not title:
                continue

            excerpt_el = item.select_one(excerpt_selector) if excerpt_selector else item.find("p")
            text = strip_html(str(excerpt_el)) if excerpt_el else ""

            seen_urls.add(url)
            records.append(
                SourceRecord(
                    external_id=hashlib.sha1(url.encode("utf-8")).hexdigest(),
                    url=url,
                    title=title,
                    text=text,
                    published_at=None,
                    raw={},
                )
            )
        return records
