"""Market data HTTP routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..auth.service import get_current_user
from ..models import User
from .service import get_history, get_quote, get_quote_cached, get_security_info


router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/quote/{symbol}")
def quote(symbol: str, _: Annotated[User, Depends(get_current_user)]):
    """Returns cached quote instantly if available, else fetches (may be slow).
    For UI previews that must be non-blocking, prefer the quote_cached path."""
    q = get_quote_cached(symbol) or get_quote(symbol)
    if not q:
        return {"symbol": symbol.upper(), "error": "No data"}
    return q.__dict__


@router.get("/info/{symbol}")
def info(symbol: str, _: Annotated[User, Depends(get_current_user)]):
    return get_security_info(symbol)


@router.get("/history/{symbol}")
def history(
    symbol: str,
    _: Annotated[User, Depends(get_current_user)],
    period: Annotated[str, Query()] = "1y",
):
    return get_history(symbol, period=period)
