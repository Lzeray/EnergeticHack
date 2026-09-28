from __future__ import annotations

import datetime as dt

from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _fmt_dt(value: dt.datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


templates.env.filters["fmtdt"] = _fmt_dt
