from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_compare,
    routes_digest,
    routes_feedback,
    routes_metrics,
    routes_profiles,
    routes_settings,
    routes_sources,
)
from app.config import BASE_DIR, settings
from app.db import init_db
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(routes_digest.router)
app.include_router(routes_sources.router)
app.include_router(routes_profiles.router)
app.include_router(routes_feedback.router)
app.include_router(routes_metrics.router)
app.include_router(routes_settings.router)
app.include_router(routes_compare.router)
