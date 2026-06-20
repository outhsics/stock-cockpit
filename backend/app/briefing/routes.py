"""Briefing HTTP routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.service import get_current_user
from ..database import get_db
from ..models import User
from .service import generate_briefing_for_user, get_latest_briefing, list_briefings


router = APIRouter(prefix="/api/briefing", tags=["briefing"])


class BriefingOut(BaseModel):
    id: int
    scope: str
    content: str
    model: str
    created_at: str


def _serialize(b) -> BriefingOut:
    return BriefingOut(
        id=b.id,
        scope=b.scope,
        content=b.content,
        model=b.model,
        created_at=b.created_at.isoformat() if b.created_at else "",
    )


@router.get("/latest", response_model=BriefingOut | None)
def latest(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    b = get_latest_briefing(db, user)
    return _serialize(b) if b else None


@router.get("/list", response_model=list[BriefingOut])
def history(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = 10,
):
    items = list_briefings(db, user, limit=limit)
    return [_serialize(b) for b in items]


@router.post("/generate", response_model=BriefingOut)
def generate(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Manually trigger briefing generation for the current user."""
    b = generate_briefing_for_user(db, user, scope="adhoc")
    return _serialize(b)
