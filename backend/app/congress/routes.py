"""Congress/insider trade routes."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.service import get_current_user
from ..database import get_db
from ..models import User
from .service import fetch_all, list_trades


router = APIRouter(prefix="/api/congress", tags=["congress"])


def _serialize(t) -> dict:
    return {
        "id": t.id,
        "symbol": t.symbol,
        "politician": t.politician,
        "chamber": t.chamber,
        "party": t.party,
        "transaction_type": t.transaction_type,
        "amount": t.amount,
        "traded_at": t.traded_at.isoformat() if t.traded_at else None,
        "reported_at": t.reported_at.isoformat() if t.reported_at else None,
        "source": t.source,
    }


@router.get("")
def list_route(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    symbol: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    trades = list_trades(db, symbol=symbol, limit=limit)
    return {"items": [_serialize(t) for t in trades]}


@router.post("/refresh")
def refresh_route(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    result = fetch_all(db)
    return {"ok": True, **result, "fetched_at": datetime.utcnow().isoformat()}
