"""News HTTP routes."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.service import get_current_user
from ..database import get_db
from ..models import User
from .service import fetch_and_store_news, list_recent_news, translate_news_batch


router = APIRouter(prefix="/api/news", tags=["news"])


def _serialize(n) -> dict:
    return {
        "id": n.id,
        "symbol": n.symbol,
        "title": n.title,
        "url": n.url,
        "source": n.source,
        "summary": n.summary,
        "published_at": n.published_at.isoformat() if n.published_at else None,
        "fetched_at": n.fetched_at.isoformat() if n.fetched_at else None,
    }


@router.get("")
def list_news(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    symbol: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    lang: Annotated[str | None, Query()] = None,  # cn | en | None(all)
):
    items = list_recent_news(db, symbol=symbol, limit=limit, lang=lang)
    return {"items": [_serialize(n) for n in items]}


@router.post("/refresh")
def refresh_news(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Fetch holdings-specific + Chinese + general news."""
    from ..portfolio.service import list_holding_views

    views = list_holding_views(db, user)
    symbols = [v.symbol for v in views]
    result = fetch_and_store_news(db, symbols=symbols)
    return {"ok": True, **result, "fetched_at": datetime.utcnow().isoformat()}


@router.post("/translate")
def translate_news(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    limit: int = 20,
):
    """Translate up to `limit` English news items to Chinese via LLM."""
    from ..briefing.llm import get_llm

    items = list_recent_news(db, limit=limit)
    llm = get_llm()
    if not llm.is_configured:
        return {"ok": False, "error": "LLM not configured (set LLM_API_KEY)"}
    count = translate_news_batch(items, llm)
    if count:
        db.commit()
    return {"ok": True, "translated": count}
