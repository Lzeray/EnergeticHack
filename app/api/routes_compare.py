from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.digest.builder import select_for_profile
from app.templating import templates

router = APIRouter()


@router.get("/compare")
def compare_profiles(
    request: Request,
    profile_a_id: int | None = None,
    profile_b_id: int | None = None,
    period_type: str = "daily",
    session: Session = Depends(get_session),
):
    profiles = list(session.execute(select(models.Profile).order_by(models.Profile.name)).scalars())
    context = {
        "profiles": profiles,
        "profile_a_id": profile_a_id,
        "profile_b_id": profile_b_id,
        "period_type": period_type,
        "active_nav": "compare",
        "result": None,
    }
    if not (profile_a_id and profile_b_id) or len(profiles) < 1:
        return templates.TemplateResponse(request, "compare.html", context)

    profile_a = session.get(models.Profile, profile_a_id)
    profile_b = session.get(models.Profile, profile_b_id)
    if not profile_a or not profile_b:
        return templates.TemplateResponse(request, "compare.html", context)

    selection_a = select_for_profile(session, profile_a, period_type)
    selection_b = select_for_profile(session, profile_b, period_type)

    ids_a = {r.article.id: r for r in selection_a.selected}
    ids_b = {r.article.id: r for r in selection_b.selected}
    overlap_ids = set(ids_a) & set(ids_b)

    only_a = [r for aid, r in ids_a.items() if aid not in overlap_ids]
    only_b = [r for aid, r in ids_b.items() if aid not in overlap_ids]
    overlap = [ids_a[aid] for aid in overlap_ids]

    total_union = len(set(ids_a) | set(ids_b)) or 1
    context["result"] = {
        "profile_a": profile_a,
        "profile_b": profile_b,
        "only_a": sorted(only_a, key=lambda r: r.score, reverse=True),
        "only_b": sorted(only_b, key=lambda r: r.score, reverse=True),
        "overlap": sorted(overlap, key=lambda r: r.score, reverse=True),
        "overlap_pct": round(len(overlap_ids) / total_union * 100, 1),
        "stats_a": selection_a.stats,
        "stats_b": selection_b.stats,
    }
    return templates.TemplateResponse(request, "compare.html", context)
