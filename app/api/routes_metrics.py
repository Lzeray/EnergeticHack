from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.metrics import compute_service_metrics
from app.templating import templates

router = APIRouter()


@router.get("/metrics")
def view_metrics(request: Request, session: Session = Depends(get_session)):
    metrics = compute_service_metrics(session)
    return templates.TemplateResponse(request, "metrics.html", {"metrics": metrics, "active_nav": "metrics"})
