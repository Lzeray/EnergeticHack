from __future__ import annotations

import json

import httpx

from app.config import settings
from app.sources.base import SourceAdapter, SourceRecord
from app.sources.dataset import _dig, rows_to_records


class ProxyAdapter(SourceAdapter):
    """Generic HTTP(S)+JSON adapter for a custom organizer/partner API whose
    response shape isn't known in advance — point it at any endpoint and
    describe how to find the article list and map its fields.

    config: {
      "endpoint": "https://partner.example.com/api/news",
      "method"?: "GET" | "POST",           # default GET
      "headers"?: {"Authorization": "Bearer ..."},
      "params"?: {...},                      # query string for GET
      "json_body"?: {...},                    # request body for POST
      "items_path"?: "data.items",             # dot-path to the article list in the JSON response
      "field_map"?: {"id": "...", "url": "...", "title": "...", "text": "...", "date": "...", "language": "..."}
    }
    """

    type_name = "proxy"

    def fetch_raw(self, config: dict) -> str:
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
