from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.digest.builder import build_digest
from app.llm.factory import build_provider
from app.runtime_settings import get_llm_config

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_for_all_profiles(period_type: str) -> None:
    with SessionLocal() as session:
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
        profiles = list(session.execute(select(models.Profile)).scalars())
        for profile in profiles:
            try:
                build_digest(session, profile, period_type, provider)
            except Exception:  # noqa: BLE001 - one profile's failure must not block the others
                logger.exception("Scheduled %s digest failed for profile %s", period_type, profile.id)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: _run_for_all_profiles("daily"),
        CronTrigger(hour=7, minute=0),
        id="daily_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_for_all_profiles("monthly"),
        CronTrigger(day=1, hour=7, minute=30),
        id="monthly_digest",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
