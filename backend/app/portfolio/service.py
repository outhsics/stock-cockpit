"""Portfolio business logic: holdings CRUD + live valuation via market module."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Holding, User
from ..market.service import get_quote, get_quote_batch, get_quote_cached


@dataclass
class HoldingView:
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
    day_change_pct: float  # today's % move of the underlying


def _build_view(h: Holding, quote) -> HoldingView:
    price = quote.price if quote and quote.price else 0.0
    day_change_pct = quote.day_change_pct if quote else 0.0
    market_value = price * h.shares
    cost_value = h.cost_basis * h.shares
    pnl = market_value - cost_value
    pnl_pct = (pnl / cost_value) if cost_value > 0 else 0.0
    return HoldingView(
        id=h.id,
        symbol=h.symbol,
        shares=h.shares,
        cost_basis=h.cost_basis,
        note=h.note or "",
        name=quote.name if quote else h.symbol,
        current_price=price,
        market_value=market_value,
        cost_value=cost_value,
        pnl=pnl,
        pnl_pct=pnl_pct,
        day_change_pct=day_change_pct,
    )


def get_holding_view(db: Session, user: User, holding_id: int) -> HoldingView | None:
    h = db.get(Holding, holding_id)
    if not h or h.user_id != user.id:
        return None
    return _build_view(h, get_quote(h.symbol))


def list_holding_views(db: Session, user: User) -> list[HoldingView]:
    """List holdings with LAST-CACHED prices (instant). Use refresh_prices()
    to update the cache in the background; never block the UI on network."""
    stmt = select(Holding).where(Holding.user_id == user.id).order_by(Holding.symbol)
    holdings = list(db.execute(stmt).scalars().all())
    if not holdings:
        return []
    # Use cached-only quotes → O(1), no network. Holdings show last-known price.
    views = []
    for h in holdings:
        q = get_quote_cached(h.symbol)
        views.append(_build_view(h, q))
    return views


def refresh_prices(db: Session, user: User) -> dict:
    """Background price refresh. Runs SYNCHRONOUSLY but with a hard cap: each
    symbol is fetched with a short timeout, and we stop early if the data source
    is rate-limiting (detected via empty results). Returns immediately so the
    caller never blocks for long. The scheduler also runs this hourly to keep
    caches warm independently of user clicks."""
    stmt = select(Holding).where(Holding.user_id == user.id)
    symbols = [h.symbol for h in db.execute(stmt).scalars().all()]
    if not symbols:
        return {"refreshed": 0, "total": 0}

    quotes = get_quote_batch(symbols)  # network, throttled, degrades gracefully
    return {"refreshed": len(quotes), "total": len(symbols)}


@dataclass
class Overview:
    total_market_value: float
    total_cost_value: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    day_pnl_pct: float
    holdings_count: int
    top_movers: list[dict]
    allocation: list[dict]  # [{symbol, value, pct}]


def compute_overview(db: Session, user: User) -> Overview:
    views = list_holding_views(db, user)
    if not views:
        return Overview(
            total_market_value=0,
            total_cost_value=0,
            total_pnl=0,
            total_pnl_pct=0,
            day_pnl=0,
            day_pnl_pct=0,
            holdings_count=0,
            top_movers=[],
            allocation=[],
        )

    total_mv = sum(v.market_value for v in views)
    total_cost = sum(v.cost_value for v in views)
    total_pnl = total_mv - total_cost
    total_pnl_pct = (total_pnl / total_cost) if total_cost > 0 else 0.0

    # Day P&L: today's % move applied to current market value (approx).
    day_pnl = sum(v.market_value * (v.day_change_pct / 100.0) for v in views)
    day_pnl_pct = (day_pnl / (total_mv - day_pnl)) if (total_mv - day_pnl) > 0 else 0.0

    movers = sorted(views, key=lambda v: v.day_change_pct, reverse=True)
    top_movers = [
        {"symbol": v.symbol, "day_change_pct": round(v.day_change_pct, 2)} for v in movers[:5]
    ]

    allocation = [
        {
            "symbol": v.symbol,
            "value": round(v.market_value, 2),
            "pct": round((v.market_value / total_mv * 100) if total_mv > 0 else 0.0, 2),
        }
        for v in sorted(views, key=lambda x: x.market_value, reverse=True)
    ]

    return Overview(
        total_market_value=round(total_mv, 2),
        total_cost_value=round(total_cost, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct * 100, 2),
        day_pnl=round(day_pnl, 2),
        day_pnl_pct=round(day_pnl_pct * 100, 2),
        holdings_count=len(views),
        top_movers=top_movers,
        allocation=allocation,
    )
