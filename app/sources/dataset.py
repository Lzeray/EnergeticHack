from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path

from app.config import settings
from app.sources.base import SourceAdapter, SourceRecord

_DEFAULT_FIELD_CANDIDATES = {
    "id": ["id", "external_id", "guid"],
    "url": ["url", "link", "source_url"],
    "title": ["title", "headline", "name"],
    "text": ["text", "body", "summary", "content", "description"],
    "date": ["published_at", "date", "published", "created_at", "pub_date"],
    "language": ["language", "lang"],
}


def _dig(obj: dict, dotted_path: str):
    node = obj
    for part in dotted_path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
    return node


def _get_field(row: dict, field_map: dict, key: str) -> str | None:
    if key in field_map:
        return row.get(field_map[key])
    for candidate in _DEFAULT_FIELD_CANDIDATES[key]:
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
    return None


def _parse_date(value) -> dt.datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except ValueError:
        return None


def rows_to_records(rows: list[dict], field_map: dict) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for row in rows:
        url = _get_field(row, field_map, "url") or ""
        title = (_get_field(row, field_map, "title") or "").strip()
        text = _get_field(row, field_map, "text") or ""
        if not title or not url:
            continue
        ext_id = _get_field(row, field_map, "id") or hashlib.sha1(url.encode("utf-8")).hexdigest()
        records.append(
            SourceRecord(
                external_id=str(ext_id),
                url=url,
                title=title,
                text=text,
                published_at=_parse_date(_get_field(row, field_map, "date")),
                language=_get_field(row, field_map, "language"),
                raw={},
            )
        )
    return records


class DatasetAdapter(SourceAdapter):
    type_name = "dataset"

    def fetch_raw(self, config: dict) -> str:
        if "path" in config:
            path = Path(config["path"])
            if not path.is_absolute():
                path = settings.fixtures_dir / path
            return path.read_text(encoding="utf-8")
        return super().fetch_raw(config)

    def parse(self, raw: str, config: dict) -> list[SourceRecord]:
        fmt = config.get("format") or ("csv" if config.get("path", "").endswith(".csv") else "json")
        field_map = config.get("field_map", {})
        rows: list[dict]

        if fmt == "csv":
            rows = list(csv.DictReader(io.StringIO(raw)))
        else:
            data = json.loads(raw)
            if isinstance(data, list):
                rows = data
            else:
                items_path = config.get("items_path", "")
                rows = _dig(data, items_path) if items_path else data.get("items", [])
                rows = rows or []

        return rows_to_records(rows, field_map)
