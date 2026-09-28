from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.digest.builder import build_digest
from app.llm.factory import build_provider
from app.runtime_settings import get_llm_config
from app.templating import templates

router = APIRouter()


def _latest_digest_run(session: Session, profile_id: int, period_type: str) -> models.DigestRun | None:
    return session.execute(
        select(models.DigestRun)
        .where(models.DigestRun.profile_id == profile_id, models.DigestRun.period_type == period_type)
        .order_by(models.DigestRun.generated_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _grouped_items(digest_run: models.DigestRun) -> list[tuple[str, list[models.DigestArticle]]]:
    items = sorted(digest_run.items, key=lambda i: i.order_index)
    groups: list[tuple[str, list[models.DigestArticle]]] = []
    for item in items:
        if groups and groups[-1][0] == item.cluster_label:
            groups[-1][1].append(item)
        else:
            groups.append((item.cluster_label, [item]))
    return groups


@router.get("/")
def home():
    return RedirectResponse("/digest", status_code=303)


@router.get("/digest")
def view_digest(request: Request, profile_id: int | None = None, period_type: str = "daily", session: Session = Depends(get_session)):
    profiles = list(session.execute(select(models.Profile).order_by(models.Profile.name)).scalars())
    if not profiles:
        return templates.TemplateResponse(
            request,
            "digest.html",
            {"profiles": [], "profile": None, "digest_run": None, "groups": [], "period_type": period_type, "active_nav": "digest"},
        )
    profile = None
    if profile_id:
        profile = session.get(models.Profile, profile_id)
    profile = profile or profiles[0]

    digest_run = _latest_digest_run(session, profile.id, period_type)
    groups = _grouped_items(digest_run) if digest_run else []

    feedback_by_article: dict[int, str] = {}
    if digest_run:
        article_ids = [i.article_id for i in digest_run.items]
        rows = session.execute(
            select(models.Feedback).where(
                models.Feedback.profile_id == profile.id, models.Feedback.article_id.in_(article_ids)
            )
        ).scalars()
        for fb in rows:
            feedback_by_article[fb.article_id] = fb.action

    return templates.TemplateResponse(
        request,
        "digest.html",
        {
            "profiles": profiles,
            "profile": profile,
            "digest_run": digest_run,
            "groups": groups,
            "period_type": period_type,
            "feedback_by_article": feedback_by_article,
            "active_nav": "digest",
        },
    )


@router.post("/digest/generate")
def generate_digest(
    profile_id: int = Form(...),
    period_type: str = Form("daily"),
    session: Session = Depends(get_session),
):
    profile = session.get(models.Profile, profile_id)
    if profile:
        llm_config = get_llm_config(session)
        provider = build_provider(
            llm_config["llm_provider"],
            llm_config["llm_model"],
            ollama_base_url=llm_config["ollama_base_url"],
            openai_base_url=llm_config["openai_base_url"],
            openai_api_key=llm_config["openai_api_key"],
            anthropic_api_key=llm_config["anthropic_api_key"],
            anthropic_model=llm_config["anthropic_model"],
        )
        build_digest(session, profile, period_type, provider)
    return RedirectResponse(f"/digest?profile_id={profile_id}&period_type={period_type}", status_code=303)


@router.get("/digest/{digest_run_id}/markdown")
def download_markdown(digest_run_id: int, session: Session = Depends(get_session)):
    digest_run = session.get(models.DigestRun, digest_run_id)
    if not digest_run:
        return RedirectResponse("/digest", status_code=303)
    filename = f"digest_{digest_run.profile_id}_{digest_run.period_type}_{digest_run.generated_at:%Y%m%d}.md"
    return FileResponse(digest_run.markdown_path, media_type="text/markdown", filename=filename)
