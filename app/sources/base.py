from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.sources.safety import validate_outbound_url


@dataclass
class SourceRecord:
    """One raw publication as produced by a source adapter, before normalization."""

    external_id: str
    url: str
    title: str
    text: str
    published_at: dt.datetime | None = None
    language: str | None = None
    raw: dict = field(default_factory=dict)


class SourceAdapter(ABC):
    """Every adapter separates the network call (fetch_raw) from parsing (parse)
    so parsing logic is unit-testable with recorded fixture payloads, with no
    network access required in tests."""

    type_name: str

    def fetch_raw(self, config: dict) -> str:
        url = config["url"]
        validate_outbound_url(url)
        headers = {"User-Agent": settings.http_user_agent, **config.get("headers", {})}
        with httpx.Client(timeout=settings.http_timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers=headers, params=config.get("params"))
            validate_outbound_url(str(response.url))  # re-check after any redirect hop
            response.raise_for_status()
            return response.text

    @abstractmethod
    def parse(self, raw: str, config: dict) -> list[SourceRecord]:
        """Pure parsing: raw payload text -> list of SourceRecord. No I/O."""

    def collect(self, config: dict) -> list[SourceRecord]:
        raw = self.fetch_raw(config)
        return self.parse(raw, config)
