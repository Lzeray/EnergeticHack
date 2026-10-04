from __future__ import annotations

import json

import httpx

from app.config import settings
from app.sources.base import SourceAdapter, SourceRecord
from app.sources.dataset import _dig, rows_to_records
from app.sources.safety import validate_outbound_url


class ProxyAdapter(SourceAdapter):
    type_name = "proxy"

    def fetch_raw(self, config: dict) -> str:
        validate_outbound_url(config["endpoint"])
        method = config.get("method", "GET").upper()
        headers = {"User-Agent": settings.http_user_agent, **config.get("headers", {})}
        with httpx.Client(timeout=settings.http_timeout_seconds, follow_redirects=True) as client:
            response = client.request(
                method,
                config["endpoint"],
                headers=headers,
                params=config.get("params"),
                json=config.get("json_body"),
            )
            validate_outbound_url(str(response.url))  # re-check after any redirect hop
            response.raise_for_status()
            return response.text

    def parse(self, raw: str, config: dict) -> list[SourceRecord]:
        data = json.loads(raw)
        if isinstance(data, list):
            rows = data
        else:
            items_path = config.get("items_path", "items")
            rows = _dig(data, items_path) or []
        return rows_to_records(rows, config.get("field_map", {}))
