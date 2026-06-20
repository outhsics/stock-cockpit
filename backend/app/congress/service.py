"""Politician / insider trade tracking.

Data source strategy:
  1. Quiver Quant API (https://api.quiverquant.com) — if QUIVER_API_TOKEN set.
     Free tier covers congress trades, insider (Form 4) trades, gov contracts.
  2. Fallback: Capitol Trades public JSON (https://www.capitoltrades.com)
     — no key, scraped via their public data endpoint.

We dedupe by (symbol + politician + traded_at) and persist to congress_trades.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import CongressTrade

log = logging.getLogger(__name__)

QUIVER_BASE = "https://api.quiverquant.com/beta"
CAPITOL_TRADES = "https://www.capitoltrades.com/trades"


def _parse_dt(val: Any) -> datetime | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(str(val)[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _store(db: Session, **kwargs) -> bool:
    """Insert if not duplicate. kwargs must include symbol, politician, traded_at."""
    sym = kwargs.get("symbol", "")
    pol = kwargs.get("politician", "")
    traded = kwargs.get("traded_at")
    # Dedupe: same symbol + politician + trade date.
    stmt = select(CongressTrade).where(
        CongressTrade.symbol == sym,
        CongressTrade.politician == pol,
    )
    if traded:
        stmt = stmt.where(CongressTrade.traded_at == traded)
    if db.execute(stmt).scalar_one_or_none():
        return False
    db.add(CongressTrade(**kwargs))
    return True


def fetch_quiver_congress(db: Session, limit: int = 100) -> int:
    """Fetch recent congress trades via Quiver. Requires QUIVER_API_TOKEN."""
    token = getattr(settings, "quiver_api_token", "") or ""
    if not token:
        return -1  # signal: not configured
    added = 0
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(
                f"{QUIVER_BASE}/historical/house-disclosure",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": limit},
            )
        if r.status_code != 200:
            log.warning("quiver congress HTTP %s", r.status_code)
            return 0
        for item in r.json()[:limit]:
            traded = _parse_dt(item.get("TransactionDate"))
            if _store(db,
                      symbol=str(item.get("Ticker", "")).upper(),
                      politician=item.get("Representative", ""),
                      chamber="House",
                      party="",
                      transaction_type="Buy" if item.get("Transaction") == "Purchase" else "Sell",
                      amount=item.get("Range", ""),
                      traded_at=traded,
                      source="quiver"):
                added += 1
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("quiver congress fetch failed: %s", exc)
    return added


def fetch_quiver_insider(db: Session, limit: int = 100) -> int:
    """Fetch recent insider (Form 4) trades via Quiver."""
    token = getattr(settings, "quiver_api_token", "") or ""
    if not token:
        return -1
    added = 0
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(
                f"{QUIVER_BASE}/historical/insider-transactions",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": limit},
            )
        if r.status_code != 200:
            return 0
        for item in r.json()[:limit]:
            traded = _parse_dt(item.get("TransactionDate"))
            txtype = "Buy" if str(item.get("Transaction", "")).startswith(("Purchase", "Buy")) else "Sell"
            if _store(db,
                      symbol=str(item.get("Ticker", "")).upper(),
                      politician=item.get("Name", "Insider"),
                      chamber="Insider",
                      party="",
                      transaction_type=txtype,
                      amount=f"{item.get('TransactionShares', '')} shares",
                      traded_at=traded,
                      source="quiver-insider"):
                added += 1
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("quiver insider fetch failed: %s", exc)
    return added


def fetch_capitol_trades(db: Session, limit: int = 80) -> int:
    """Fallback: Capitol Trades public data (no key). Best-effort scrape of
    their JSON API; degrades gracefully if structure changes or anti-bot kicks in."""
    added = 0
    try:
        with httpx.Client(timeout=12.0) as c:
            r = c.get(
                "https://www.capitoltrades.com/trades.json",
                params={"page": 1, "perPage": limit},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                follow_redirects=True,
            )
        # Capitol Trades uses Vercel security checkpoint; if challenged, skip silently.
        if r.status_code != 200 or "vercel" in r.text.lower() or "security checkpoint" in r.text.lower():
            log.info("capitoltrades unavailable (status %s / anti-bot), skipping", r.status_code)
            return 0
        data = r.json()
        trades = data.get("data", []) if isinstance(data, dict) else data
        for item in trades[:limit]:
            symbol = (item.get("asset", {}) or {}).get("assetTicker") or item.get("ticker", "")
            pol_obj = item.get("politician", {}) or {}
            pol_name = pol_obj.get("politicianName") or item.get("politician", "")
            tx = (item.get("trade", {}) or {})
            tx_size = tx.get("tradeSize", {})
            chamber = pol_obj.get("congress", "") or ""
            traded = _parse_dt(tx.get("traded") or item.get("txDate"))
            if not symbol:
                continue
            if _store(db,
                      symbol=str(symbol).upper(),
                      politician=str(pol_name),
                      chamber=str(chamber)[:16],
                      party=str(pol_obj.get("party", ""))[:16],
                      transaction_type="Buy" if str(tx.get("side", "")).lower().startswith("buy") else "Sell",
                      amount=str(tx_size.get("text", "") if isinstance(tx_size, dict) else tx_size)[:64],
                      traded_at=traded,
                      source="capitoltrades"):
                added += 1
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.info("capitoltrades fetch failed (optional source): %s", exc)
    return added


def fetch_all(db: Session) -> dict:
    """Fetch from all configured sources. Returns counts per source."""
    result = {"quiver_congress": 0, "quiver_insider": 0, "capitoltrades": 0, "configured": True}
    # Capitol Trades first (no key, broadest free coverage).
    result["capitoltrades"] = fetch_capitol_trades(db)
    qc = fetch_quiver_congress(db)
    result["quiver_congress"] = max(qc, 0)
    result["configured"] = qc != -1
    qi = fetch_quiver_insider(db)
    result["quiver_insider"] = max(qi, 0)
    total = result["quiver_congress"] + result["quiver_insider"] + result["capitoltrades"]
    result["new"] = total
    log.info("congress fetch: +%d (%s)", total, {k: v for k, v in result.items() if k != "new"})
    return result


def list_trades(db: Session, symbol: str | None = None, limit: int = 50) -> list[CongressTrade]:
    stmt = select(CongressTrade)
    if symbol:
        stmt = stmt.where(CongressTrade.symbol == symbol.upper())
    stmt = stmt.order_by(CongressTrade.traded_at.desc().nullslast(),
                         CongressTrade.fetched_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())
