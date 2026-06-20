"""Portfolio HTTP routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Holding, User
from ..auth.service import get_current_user
from .service import compute_overview, list_holding_views


router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class HoldingIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    shares: float = Field(gt=0)
    cost_basis: float = Field(gt=0)
    note: str = ""


class HoldingUpdate(BaseModel):
    shares: float | None = Field(default=None, gt=0)
    cost_basis: float | None = Field(default=None, gt=0)
    note: str | None = None


class HoldingOut(BaseModel):
    id: int
    symbol: str
    shares: float
    cost_basis: float
    note: str
    name: str
    current_price: float
    market_value: float
    cost_value: float
    pnl: float
    pnl_pct: float
    day_change_pct: float


@router.get("/holdings", response_model=list[HoldingOut])
def get_holdings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[HoldingOut]:
    views = list_holding_views(db, user)
    return [HoldingOut(**v.__dict__) for v in views]


@router.post("/holdings", response_model=HoldingOut, status_code=201)
def add_holding(
    payload: HoldingIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> HoldingOut:
    holding = Holding(
        user_id=user.id,
        symbol=payload.symbol.strip().upper(),
        shares=payload.shares,
        cost_basis=payload.cost_basis,
        note=payload.note,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    # Return immediately with cached quote (if any); price refresh happens
    # asynchronously so the UI never waits on the network.
    from ..market.service import get_quote_cached
    from .service import _build_view

    view = _build_view(holding, get_quote_cached(holding.symbol))
    # Kick off a background price fetch for this symbol (non-blocking).
    from ..market.service import get_quote
    import threading
    threading.Thread(target=lambda: get_quote(holding.symbol), daemon=True).start()
    return HoldingOut(**view.__dict__)  # type: ignore[arg-type]


@router.put("/holdings/{holding_id}", response_model=HoldingOut)
def update_holding(
    holding_id: int,
    payload: HoldingUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> HoldingOut:
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Holding not found")
    if payload.shares is not None:
        holding.shares = payload.shares
    if payload.cost_basis is not None:
        holding.cost_basis = payload.cost_basis
    if payload.note is not None:
        holding.note = payload.note
    db.commit()
    from .service import get_holding_view

    view = get_holding_view(db, user, holding.id)
    return HoldingOut(**view.__dict__)  # type: ignore[arg-type]


@router.delete("/holdings/{holding_id}")
def delete_holding(
    holding_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(holding)
    db.commit()
    return {"ok": True, "id": holding_id}


@router.get("/overview")
def get_overview(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return compute_overview(db, user)


@router.post("/refresh")
def refresh_prices(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Background price refresh for all holdings. Fetches fresh quotes from
    AV (network, throttled) and updates the cache. Call this after adding
    holdings or when the user clicks '刷新行情'."""
    from .service import refresh_prices as do_refresh
    return do_refresh(db, user)


@router.get("/history")
def get_history(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    period: str = "1y",
):
    """Aggregate portfolio net value history by fetching each holding's history.

    For multiple holdings we fetch each symbol's history in turn. Alpha Vantage
    free tier allows 5 req/min, so for >1 holding we space the calls to stay
    under the limit (the market service also caches, so repeated dashboard
    loads don't re-fetch)."""
    import time as _time
    from ..market.service import get_history as market_history

    stmt = select(Holding).where(Holding.user_id == user.id)
    holdings = list(db.execute(stmt).scalars().all())
    if not holdings:
        return {"dates": [], "values": []}

    # Dedupe symbols (a user may hold the same ticker in multiple lots).
    unique_symbols = sorted({h.symbol for h in holdings})
    # Min shares per symbol (history scales by shares).
    shares_by_symbol = {}
    for h in holdings:
        shares_by_symbol[h.symbol] = shares_by_symbol.get(h.symbol, 0) + h.shares

    symbol_hist: dict[str, list[dict]] = {}
    for i, sym in enumerate(unique_symbols):
        if i > 0:
            _time.sleep(13)  # AV rate-limit spacing between symbols
        hist = market_history(sym, period=period)
        symbol_hist[sym] = hist.get("points", [])

    series: dict[str, dict[str, float]] = {}
    for sym, points in symbol_hist.items():
        for point in points:
            series.setdefault(point["date"], {})[sym] = point["close"] * shares_by_symbol[sym]

    dates = sorted(series.keys())
    values = [round(sum(series[d].values()), 2) for d in dates]
    return {"dates": dates, "values": values}
