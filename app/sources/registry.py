from __future__ import annotations

from app.sources.base import SourceAdapter
from app.sources.dataset import DatasetAdapter
from app.sources.proxy import ProxyAdapter
from app.sources.rss import RssAdapter
from app.sources.telegram import TelegramPublicAdapter
from app.sources.website import WebsiteAdapter

_ADAPTERS: dict[str, type[SourceAdapter]] = {
    "rss": RssAdapter,
    "website": WebsiteAdapter,
    "telegram": TelegramPublicAdapter,
    "dataset": DatasetAdapter,
    "proxy": ProxyAdapter,
}


def get_adapter(source_type: str) -> SourceAdapter:
    try:
        return _ADAPTERS[source_type]()
    except KeyError as exc:
        raise ValueError(f"Unknown source type: {source_type!r}. Known: {sorted(_ADAPTERS)}") from exc


def known_types() -> list[str]:
    return sorted(_ADAPTERS)
