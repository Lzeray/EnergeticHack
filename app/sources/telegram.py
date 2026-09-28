from __future__ import annotations

import datetime as dt
import hashlib

from bs4 import BeautifulSoup

from app.sources.base import SourceAdapter, SourceRecord
from app.sources.util import strip_html


class TelegramPublicAdapter(SourceAdapter):
    """Reads a public Telegram channel's web preview (t.me/s/<channel>), which
    Telegram serves without authentication for public channels. No Bot API
    token needed; only channels with public previews enabled work.

    config: {"channel": "channelname"} or {"url": "https://t.me/s/channelname"}
    """

    type_name = "telegram"

    def fetch_raw(self, config: dict) -> str:
        if "url" not in config and "channel" in config:
            config = {**config, "url": f"https://t.me/s/{config['channel']}"}
        return super().fetch_raw(config)

    def parse(self, raw: str, config: dict) -> list[SourceRecord]:
        soup = BeautifulSoup(raw, "lxml")
        records: list[SourceRecord] = []

        for message in soup.select("div.tgme_widget_message"):
            post_id = message.get("data-post")  # e.g. "channelname/123"
            text_el = message.select_one(".tgme_widget_message_text")
            text = strip_html(str(text_el)) if text_el else ""
            if not text:
                continue

            time_el = message.select_one("time")
            published_at = _parse_iso(time_el.get("datetime")) if time_el else None

            url = f"https://t.me/{post_id}" if post_id else message.get("data-view", "")
            external_id = post_id or hashlib.sha1(text.encode("utf-8")).hexdigest()

            title = text.split("\n", 1)[0][:200].strip()
            records.append(
                SourceRecord(
                    external_id=str(external_id),
                    url=url,
                    title=title or "(без заголовка)",
                    text=text,
                    published_at=published_at,
                    raw={},
                )
            )
        return records


def _parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
