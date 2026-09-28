from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.templating import templates

router = APIRouter()


@router.get("/profiles")
def list_profiles(request: Request, session: Session = Depends(get_session)):
    profiles = list(session.execute(select(models.Profile).order_by(models.Profile.name)).scalars())
    return templates.TemplateResponse(
        request, "profiles.html", {"profiles": profiles, "active_nav": "profiles"}
    )


@router.post("/profiles")
def create_profile(
    name: str = Form(...),
    audience: str = Form("custom"),
    interests_text: str = Form(""),
    session: Session = Depends(get_session),
):
    session.add(models.Profile(name=name, audience=audience, interests_text=interests_text))
    session.commit()
    return RedirectResponse("/profiles", status_code=303)


@router.post("/profiles/{profile_id}")
def update_profile(
    profile_id: int,
    name: str = Form(...),
    audience: str = Form("custom"),
    interests_text: str = Form(""),
    session: Session = Depends(get_session),
):
    profile = session.get(models.Profile, profile_id)
    if profile:
        profile.name = name
        profile.audience = audience
        profile.interests_text = interests_text
        session.commit()
    return RedirectResponse("/profiles", status_code=303)


@router.post("/profiles/{profile_id}/delete")
def delete_profile(profile_id: int, session: Session = Depends(get_session)):
    profile = session.get(models.Profile, profile_id)
    if profile:
        session.delete(profile)
        session.commit()
    return RedirectResponse("/profiles", status_code=303)
