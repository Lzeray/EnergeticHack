from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.schemas import FeedbackIn

router = APIRouter()


@router.post("/api/feedback")
def submit_feedback(payload: FeedbackIn, session: Session = Depends(get_session)):
    existing = session.execute(
        select(models.Feedback).where(
            models.Feedback.profile_id == payload.profile_id,
            models.Feedback.article_id == payload.article_id,
        )
    ).scalar_one_or_none()
    if existing:
        existing.action = payload.action
        existing.rating = payload.rating
    else:
        session.add(
            models.Feedback(
                profile_id=payload.profile_id,
                article_id=payload.article_id,
                action=payload.action,
                rating=payload.rating,
            )
        )
    session.commit()
    return {"ok": True, "action": payload.action}
