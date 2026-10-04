from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.llm.factory import build_provider
from app.runtime_settings import get_llm_config, set_llm_config
from app.templating import templates

router = APIRouter()


@router.get("/settings")
def view_settings(request: Request, session: Session = Depends(get_session)):
    config = get_llm_config(session)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"config": config, "locked": settings.settings_locked, "active_nav": "settings", "test_result": None},
    )


@router.post("/settings")
def save_settings(
    llm_provider: str = Form("ollama"),
    llm_model: str = Form("llama3.1"),
    ollama_base_url: str = Form("http://localhost:11434"),
    openai_base_url: str = Form("https://api.openai.com/v1"),
    openai_api_key: str = Form(""),
    anthropic_api_key: str = Form(""),
    anthropic_model: str = Form("claude-sonnet-5-5"),
    session: Session = Depends(get_session),
):
    if settings.settings_locked:
        raise HTTPException(status_code=403, detail="Settings are locked")
    updates = dict(
        llm_provider=llm_provider,
        llm_model=llm_model,
        ollama_base_url=ollama_base_url,
        openai_base_url=openai_base_url,
        anthropic_model=anthropic_model,
    )
    if openai_api_key:
        updates["openai_api_key"] = openai_api_key
    if anthropic_api_key:
        updates["anthropic_api_key"] = anthropic_api_key
    set_llm_config(session, **updates)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/test")
def test_settings(request: Request, session: Session = Depends(get_session)):
    config = get_llm_config(session)
    provider = build_provider(
        config["llm_provider"],
        config["llm_model"],
        ollama_base_url=config["ollama_base_url"],
        openai_base_url=config["openai_base_url"],
        openai_api_key=config["openai_api_key"],
        anthropic_api_key=config["anthropic_api_key"],
        anthropic_model=config["anthropic_model"],
    )
    result = provider.summarize("Тестовый заголовок", "Это тестовый текст для проверки подключения LLM-провайдера.")
    used_fallback = getattr(provider, "last_error", None) is not None
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "config": config,
            "locked": settings.settings_locked,
            "active_nav": "settings",
            "test_result": {"summary": result, "used_fallback": used_fallback, "provider": provider.name},
        },
    )
