"""Market data service — commercial-grade.

Data source strategy (in priority order):
  1. Alpha Vantage GLOBAL_QUOTE  — when ALPHA_VANTAGE_API_KEY is set.
     Stable, doesn't block container IPs. Free tier: 5 req/min, 500/day.
     We throttle + cache to stay well within limits.
  2. Yahoo Finance chart API     — fallback when AV not configured or fails.
     Works from clean IPs (cloud/home); container IPs may get 429.

Design goals:
  * Never hang the caller for >~15s total (Yahoo's long backoff was unacceptable
    for a UI request — we cap it).
  * Cache positive AND negative results briefly to avoid hammering the API on
    repeated page loads / refreshes.
  * Serialize all external calls through a global throttle so concurrent
    requests don't blow the rate limit.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import settings

log = logging.getLogger(__name__)

CHART_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
CHART_PATH = "/v8/finance/chart/{symbol}"
AV_BASE = "https://www.alphavantage.co/query"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

# ---- Throttling -----------------------------------------------------------
# Yahoo is the PRIMARY source: it has no hard daily cap but rate-limits (~429)
# if requests come faster than ~every 8s from the same IP. We use 8s spacing
# to stay safely under. Alpha Vantage is fallback only (25 req/DAY free tier).
_MIN_INTERVAL = 8.0
_last_request_ts = 0.0
_throttle_lock = threading.Lock()


def _throttle() -> None:
    global _last_request_ts
    with _throttle_lock:
        now = time.time()
        wait = _MIN_INTERVAL - (now - _last_request_ts)
        if wait > 0:
            time.sleep(wait)
        _last_request_ts = time.time()


# ---- Caching --------------------------------------------------------------
# key -> (timestamp, value). Positive results cached CACHE_TTL; negative
# (failed) results cached NEG_CACHE_TTL to avoid retry storms.
_CACHE: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 120      # 2 min for successful quotes/history
NEG_CACHE_TTL = 30   # 30s for failed lookups


def _cache_get(key: str, ttl: float) -> tuple[bool, Any]:
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return True, hit[1]
    return False, None


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


@dataclass
class Quote:
    symbol: str
    name: str
    price: float
    previous_close: float
    day_change_pct: float
    currency: str = "USD"


# ---- Alpha Vantage --------------------------------------------------------
def _av_global_quote(symbol: str) -> dict | None:
    """Alpha Vantage GLOBAL_QUOTE. Returns {price, previous_close, change_pct}
    or None. Honors throttle + caching (incl. negative cache)."""
    if not settings.alpha_vantage_api_key:
        return None

    key = f"av:{symbol}"
    # Negative cache: if it just failed, don't retry immediately.
    found, cached = _cache_get(key, NEG_CACHE_TTL)
    if found:
        return cached  # may be None (neg cache)

    _throttle()
    try:
        with httpx.Client(timeout=12.0) as c:
            r = c.get(AV_BASE, params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": settings.alpha_vantage_api_key,
            })
        if r.status_code != 200:
            _cache_set(key, None)
            return None
        data = r.json().get("Global Quote", {})
        if not data or not data.get("05. price"):
            # AV returns empty "Global Quote" on rate-limit or bad symbol.
            _cache_set(key, None)
            return None
        result = {
            "price": float(data["05. price"]),
            "previous_close": float(data["08. previous close"]),
            "change_pct": (
                float(str(data["10. change percent"]).strip("%"))
                if data.get("10. change percent") not in (None, "--") else 0.0
            ),
        }
        _cache_set(key, result)
        return result
    except Exception as exc:  # noqa: BLE001
        log.debug("Alpha Vantage quote failed for %s: %s", symbol, exc)
        _cache_set(key, None)
        return None


# ---- Yahoo chart ----------------------------------------------------------
def _fetch_chart(symbol: str, params: dict) -> dict | None:
    """Yahoo chart API. Rotates query1/query2 hosts; on 429 does one retry
    after a short backoff. Total worst-case ~20s (2 hosts × retry). The caller
    caches success for 2 min, so this network hit only happens on cache miss."""
    import time as _time
    last_err = None
    for attempt in range(2):  # 1 normal + 1 backoff retry
        for host in CHART_HOSTS:
            _throttle()
            url = f"https://{host}{CHART_PATH.format(symbol=symbol)}"
            try:
                with httpx.Client(headers=HEADERS, timeout=8.0) as c:
                    r = c.get(url, params=params)
                if r.status_code == 200:
                    return r.json()
                last_err = f"{host} HTTP {r.status_code}"
                if r.status_code == 404:
                    return None
                # 429 / 5xx → try other host
            except Exception as exc:  # noqa: BLE001
                last_err = f"{host} {exc}"
                continue
        # All hosts failed this round; back off before a final retry.
        if attempt == 0:
            log.info("Yahoo rate-limited (%s), backing off 10s before retry", last_err)
            _time.sleep(10)
    log.debug("chart fetch failed for %s: %s", symbol, last_err)
    return None


def _cached_chart(symbol: str, params: dict, ttl: int = CACHE_TTL) -> dict | None:
    key = f"yc:{symbol}:{params.get('range')}:{params.get('interval')}"
    found, cached = _cache_get(key, ttl)
    if found and cached is not None:
        return cached
    data = _fetch_chart(symbol, params)
    if data is not None:
        _cache_set(key, data)
    return data


# ---- Public API -----------------------------------------------------------
def get_quote_cached(symbol: str) -> Quote | None:
    """Return a quote from cache ONLY — never triggers a network request.
    Used for fast UI responses (dashboard loads instantly with last-known
    prices); refresh happens via get_quote() in the background."""
    symbol = symbol.strip().upper()
    # AV cache holds the quote dict under "av:{symbol}".
    found, av = _cache_get(f"av:{symbol}", NEG_CACHE_TTL)
    if found and av:
        return Quote(symbol=symbol, name=symbol, price=av["price"],
                     previous_close=av["previous_close"],
                     day_change_pct=round(av["change_pct"], 2))
    # Yahoo cache holds the chart payload; derive quote from meta.
    found, data = _cache_get(f"yc:{symbol}:5d:1d", CACHE_TTL)
    if found and data:
        try:
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
            if price:
                return Quote(symbol=symbol, name=str(meta.get("shortName") or symbol),
                             price=float(price), previous_close=float(prev),
                             day_change_pct=round((float(price) - float(prev)) / float(prev) * 100, 2))
        except Exception:  # noqa: BLE001
            pass
    return None


def get_quote(symbol: str) -> Quote | None:
    """Get a quote. Yahoo is primary (3s throttle, no daily cap); Alpha Vantage
    is fallback only when Yahoo fails AND AV is configured (we conserve its
    scarce 25/day quota for real outages)."""
    symbol = symbol.strip().upper()

    # Layer 1: Yahoo chart (primary).
    try:
        data = _cached_chart(symbol, {"range": "5d", "interval": "1d"})
        if data:
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price is None:
                closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                closes = [x for x in closes if x is not None]
                if closes:
                    price = closes[-1]
                    if len(closes) > 1:
                        prev = prev or closes[-2]
            if price is not None:
                prev = prev or price
                change_pct = ((price - prev) / prev * 100.0) if prev else 0.0
                name = meta.get("longName") or meta.get("shortName") or symbol
                return Quote(
                    symbol=symbol, name=str(name),
                    price=float(price), previous_close=float(prev),
                    day_change_pct=round(change_pct, 2),
                    currency=str(meta.get("currency", "USD")),
                )
    except Exception as exc:  # noqa: BLE001
        log.debug("yahoo quote failed for %s: %s", symbol, exc)

    # Layer 2: Alpha Vantage (fallback — sparingly, to conserve 25/day quota).
    av = _av_global_quote(symbol)
    if av:
        return Quote(
            symbol=symbol, name=symbol,
            price=av["price"], previous_close=av["previous_close"],
            day_change_pct=round(av["change_pct"], 2),
        )
    return None


def get_quote_batch(symbols: list[str]) -> dict[str, Quote]:
    """Fetch quotes for multiple symbols. Serialized through the global throttle
    so we never exceed rate limits. Returns {symbol: Quote}."""
    out: dict[str, Quote] = {}
    for sym in symbols:
        sym = sym.strip().upper()
        q = get_quote(sym)
        if q:
            out[sym] = q
    return out


def _av_daily_history(symbol: str, period: str) -> list[dict]:
    """Alpha Vantage TIME_SERIES_DAILY. Returns list of {date, open, high,
    low, close, volume} sorted ascending. Returns [] on failure/limit."""
    if not settings.alpha_vantage_api_key:
        return []
    key = f"avhist:{symbol}:{period}"
    # Positive results cached 10 min; but DON'T long-cache failures — use a
    # short separate check so a transient rate-limit doesn't blank the chart
    # for 10 minutes. Only cache None for 30s.
    found_pos, cached_pos = _cache_get(key, 600)
    if found_pos and cached_pos:
        return cached_pos
    found_neg, _ = _cache_get(key, 30)
    if found_neg:
        return []

    _throttle()
    try:
        outputsize = "compact" if period in ("1mo", "3mo") else "full"
        with httpx.Client(timeout=15.0) as c:
            r = c.get(AV_BASE, params={
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": outputsize,
                "apikey": settings.alpha_vantage_api_key,
            })
        if r.status_code != 200:
            _cache_set(key, [])
            return []
        body = r.json()
        series = body.get("Time Series (Daily)", {})
        if not series or "Note" in body or "Information" in body:
            _cache_set(key, [])
            return []
        points = []
        for date, vals in series.items():
            try:
                points.append({
                    "date": date,
                    "open": round(float(vals.get("1. open", 0)), 2),
                    "high": round(float(vals.get("2. high", 0)), 2),
                    "low": round(float(vals.get("3. low", 0)), 2),
                    "close": round(float(vals.get("4. close", 0)), 2),
                    "volume": int(float(vals.get("5. volume", 0))),
                })
            except (ValueError, TypeError):
                continue
        points.sort(key=lambda p: p["date"])
        period_days = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "5y": 1260, "max": 99999}
        trim = period_days.get(period, 252)
        points = points[-trim:]
        _cache_set(key, points)
        return points
    except Exception as exc:  # noqa: BLE001
        log.debug("Alpha Vantage history failed for %s: %s", symbol, exc)
        _cache_set(key, [])
        return []


def get_history(symbol: str, period: str = "1y", interval: str = "1d") -> dict:
    """OHLC history. Prefer Alpha Vantage TIME_SERIES_DAILY (stable); fall back
    to Yahoo chart API. Result cached 5-10 min."""
    symbol = symbol.strip().upper()

    # Layer 1: Alpha Vantage daily (stable, no container-IP blocking).
    av_points = _av_daily_history(symbol, period)
    if av_points:
        return {"symbol": symbol, "points": av_points}

    # Layer 2: Yahoo chart.
    try:
        data = _cached_chart(symbol, {"range": period, "interval": interval}, ttl=300)
        if not data:
            return {"symbol": symbol, "points": []}
        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quotes = result.get("indicators", {}).get("quote", [{}])[0]
        o, h, l, cl, v = (
            quotes.get("open", []),
            quotes.get("high", []),
            quotes.get("low", []),
            quotes.get("close", []),
            quotes.get("volume", []),
        )
        points = []
        for i, ts in enumerate(timestamps):
            close = cl[i] if i < len(cl) else None
            if close is None:
                continue
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            points.append({
                "date": date,
                "open": round(float(o[i]), 2) if i < len(o) and o[i] else 0.0,
                "high": round(float(h[i]), 2) if i < len(h) and h[i] else 0.0,
                "low": round(float(l[i]), 2) if i < len(l) and l[i] else 0.0,
                "close": round(float(close), 2),
                "volume": int(v[i]) if i < len(v) and v[i] else 0,
            })
        return {"symbol": symbol, "points": points}
    except Exception as exc:  # noqa: BLE001
        log.warning("get_history failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "points": [], "error": str(exc)}


def get_security_info(symbol: str) -> dict[str, Any]:
    """Static info. AV for price basics; Yahoo for richer metadata when reachable."""
    symbol = symbol.strip().upper()
    base: dict[str, Any] = {
        "symbol": symbol, "name": symbol, "type": "", "exchange": "",
        "currency": "USD", "expense_ratio": None, "yield": None,
        "sector": None, "industry": None, "description": "", "top_holdings": [],
    }
    q = get_quote(symbol)
    if q:
        base["name"] = q.name
        base["currency"] = q.currency

    # Best-effort enrichment via Yahoo (never fatal).
    try:
        import yfinance as yf  # type: ignore
        info = (yf.Ticker(symbol).info or {})
        base["name"] = info.get("shortName") or info.get("longName") or base["name"]
        base["type"] = info.get("quoteType", "") or base["type"]
        base["exchange"] = info.get("exchange", "") or base["exchange"]
        if info.get("annualReportExpenseRatio") is not None:
            base["expense_ratio"] = float(info["annualReportExpenseRatio"])
        if info.get("yield") is not None:
            base["yield"] = float(info["yield"])
        base["sector"] = info.get("sector")
        base["industry"] = info.get("industry")
        base["description"] = info.get("longBusinessSummary", "") or base["description"]
        holdings = info.get("holdings") or []
        base["top_holdings"] = [
            {"symbol": h.get("symbol"), "weight": float(h.get("holdingPercent", 0) * 100)}
            for h in holdings[:10]
        ]
    except Exception as exc:  # noqa: BLE001
        log.debug("yfinance enrichment skipped for %s: %s", symbol, exc)
    return base
