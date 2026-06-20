"""Deep research HTTP routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth.service import get_current_user
from ..database import get_db
from ..models import User
from .service import compare_symbols, earnings_calendar, fundamentals, macro_indicators, performance


router = APIRouter(prefix="/api/research", tags=["research"])


class CompareIn(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=8)


@router.get("/fundamentals/{symbol}")
def fund_route(symbol: str, _: Annotated[User, Depends(get_current_user)]):
    return fundamentals(symbol)


@router.get("/performance/{symbol}")
def perf_route(
    symbol: str,
    _: Annotated[User, Depends(get_current_user)],
    periods: Annotated[str, Query()] = "1mo,3mo,6mo,1y",
):
    return performance(symbol, periods=periods.split(","))


@router.post("/compare")
def compare_route(
    payload: CompareIn,
    _: Annotated[User, Depends(get_current_user)],
):
    return {"items": compare_symbols(payload.symbols)}


@router.get("/macro")
def macro_route(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)] = None,
):
    return macro_indicators()


@router.get("/earnings")
def earnings_route(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    from ..portfolio.service import list_holding_views
    views = list_holding_views(db, user)
    return {"items": earnings_calendar([v.symbol for v in views])}
