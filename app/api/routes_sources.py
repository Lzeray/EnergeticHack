from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.pipeline.normalize import extract_security_tags
from app.sources.registry import get_adapter, known_types
from app.templating import templates

router = APIRouter()


@router.get("/sources")
def list_sources(request: Request, session: Session = Depends(get_session)):
    sources = list(session.execute(select(models.Source).order_by(models.Source.name)).scalars())
    return templates.TemplateResponse(
        request,
        "sources.html",
        {"sources": sources, "known_types": known_types(), "active_nav": "sources"},
    )


@router.post("/sources")
def create_source(
    name: str = Form(...),
    type: str = Form(...),
    url_or_path: str = Form(""),
    category: str = Form(""),
    priority: float = Form(1.0),
    session: Session = Depends(get_session),
):
    if type in ("rss", "website"):
        config = {"url": url_or_path}
    elif type == "telegram":
        config = {"channel": url_or_path.lstrip("@")}
    elif type == "dataset":
        config = {"path": url_or_path}
    else:  # proxy
        config = {"endpoint": url_or_path}
    source = models.Source(name=name, type=type, config=config, category=category or None, priority=priority)
    session.add(source)
    session.commit()
    return RedirectResponse("/sources", status_code=303)


@router.post("/sources/{source_id}/toggle")
def toggle_source(source_id: int, session: Session = Depends(get_session)):
    source = session.get(models.Source, source_id)
    if source:
        source.enabled = not source.enabled
        session.commit()
    return RedirectResponse("/sources", status_code=303)


@router.post("/sources/{source_id}/delete")
def delete_source(source_id: int, session: Session = Depends(get_session)):
    source = session.get(models.Source, source_id)
    if source:
        session.delete(source)
        session.commit()
    return RedirectResponse("/sources", status_code=303)


@router.post("/sources/{source_id}/fetch")
def fetch_source(source_id: int, session: Session = Depends(get_session)):
    source = session.get(models.Source, source_id)
    if not source:
        return RedirectResponse("/sources", status_code=303)

    adapter = get_adapter(source.type)
    try:
        records = adapter.collect(source.config)
        new_count = 0
        for record in records:
            exists = session.execute(
                select(models.Article).where(
                    models.Article.source_id == source.id, models.Article.external_id == record.external_id
                )
            ).scalar_one_or_none()
            if exists:
                continue
            session.add(
                models.Article(
                    source_id=source.id,
                    external_id=record.external_id,
                    url=record.url,
                    title=record.title,
                    text=record.text,
                    published_at=record.published_at,
                    language=record.language,
                    tags=extract_security_tags(f"{record.title} {record.text}"),
                    raw_meta=record.raw,
                )
            )
            new_count += 1
        source.last_status = "ok"
        source.last_error = None
        source.last_item_count = new_count
        source.last_fetch_at = dt.datetime.now(dt.timezone.utc)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator via source health, not a 500
        source.last_status = "error"
        source.last_error = str(exc)[:2000]
        source.last_fetch_at = dt.datetime.now(dt.timezone.utc)
    session.commit()
    return RedirectResponse("/sources", status_code=303)
