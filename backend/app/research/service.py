"""Deep research service.

Provides analysis beyond the basic quote/history used by the portfolio view:
  - ETF/stock comparison across metrics
  - Key fundamentals (P/E, market cap, dividend, sector)
  - Financial calendar / earnings
  - Macro indicators (rates, VIX via ETFs)

Built on the existing market service (Alpha Vantage + Yahoo fallback) — no
heavy OpenBB dependency, keeps the Docker image lean.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import settings
from ..market.service import (
    _av_daily_history, _cache_get, _cache_set, _cached_chart, _throttle,
)

log = logging.getLogger(__name__)


def _yf_info(symbol: str) -> dict[str, Any]:
    """yfinance info dict — primary source for fundamentals (doesn't consume
    AV's scarce 25/day quota). Wrapped in a hard timeout via thread so it can
    never hang the request."""
    import concurrent.futures
    try:
        def _fetch():
            import yfinance as yf
            return yf.Ticker(symbol).info or {}
        with concurrent.futures.ThreadPoolExecutor() as ex:
            return ex.submit(_fetch).result(timeout=8)
    except Exception:  # noqa: BLE001
        return {}


def _av_overview(symbol: str) -> dict[str, Any]:
    """Alpha Vantage OVERVIEW — SECONDARY source. Only called if yfinance
    returned nothing, and capped at a 5s timeout so a dead AV quota can't
    hang the request. Results (incl. empty) are cached to avoid retries."""
    if not settings.alpha_vantage_api_key:
        return {}
    # Negative cache: if AV just failed/had no data, don't retry for 5 min.
    found, cached = _cache_get(f"avov:{symbol}", 300)
    if found:
        return cached or {}
    try:
        with httpx.Client(timeout=5.0) as c:  # short timeout — AV is secondary
            r = c.get("https://www.alphavantage.co/query", params={
                "function": "OVERVIEW", "symbol": symbol,
                "apikey": settings.alpha_vantage_api_key,
            })
        if r.status_code != 200:
            _cache_set(f"avov:{symbol}", {})
            return {}
        d = r.json()
        if not d or "Note" in d or "Information" in d or "Error Message" in d:
            _cache_set(f"avov:{symbol}", {})
            return {}
        _cache_set(f"avov:{symbol}", d)
        return d
    except Exception as exc:  # noqa: BLE001
        log.debug("AV overview failed for %s: %s", symbol, exc)
        _cache_set(f"avov:{symbol}", {})
        return {}


def fundamentals(symbol: str) -> dict[str, Any]:
    """Full fundamentals snapshot for a security."""
    symbol = symbol.strip().upper()
    info = _yf_info(symbol)
    av = _av_overview(symbol)

    def _pick(*keys, default=None):
        for k in keys:
            if k in info and info[k] not in (None, "None"):
                return info[k]
            if k in av and av[k] not in (None, "None", ""):
                return av[k]
        return default

    return {
        "symbol": symbol,
        "name": _pick("shortName", "longName", "Name", default=symbol),
        "type": _pick("quoteType", "AssetType", default=""),
        "sector": _pick("sector", "Sector"),
        "industry": _pick("industry", "Industry"),
        "market_cap": _pick("marketCap", "MarketCapitalization"),
        "pe_ratio": _pick("trailingPE", "PERatio"),
        "forward_pe": _pick("forwardPE"),
        "peg_ratio": _pick("pegRatio", "PEGRatio"),
        "dividend_yield": _pick("dividendYield", "DividendYield"),
        "pb_ratio": _pick("priceToBook", "PriceToBookRatio"),
        "eps": _pick("trailingEps", "EPS"),
        "beta": _pick("beta", "Beta"),
        "expense_ratio": _pick("annualReportExpenseRatio"),
        "yield_pct": _pick("yield"),
        "52w_high": _pick("fiftyTwoWeekHigh", "52WeekHigh"),
        "52w_low": _pick("fiftyTwoWeekLow", "52WeekLow"),
        "description": _pick("longBusinessSummary", "Description", default=""),
    }


def compare_symbols(symbols: list[str]) -> list[dict]:
    """Compare multiple symbols side-by-side. Fundamentals are fetched in
    parallel (thread pool) so comparing 4 symbols takes ~1 network round-trip's
    worth of wall-time instead of 4×."""
    import concurrent.futures
    clean = [s.strip().upper() for s in symbols if s.strip()]
    if not clean:
        return []
    out: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(clean))) as ex:
        futures = {ex.submit(fundamentals, sym): sym for sym in clean}
        for sym in clean:
            try:
                f = futures[sym].result(timeout=15)
            except Exception:  # noqa: BLE001
                f = {}
            out.append({
                "symbol": sym,
                "name": f.get("name", sym),
                "type": f.get("type", ""),
                "market_cap": f.get("market_cap"),
                "pe_ratio": f.get("pe_ratio"),
                "dividend_yield": f.get("dividend_yield"),
                "expense_ratio": f.get("expense_ratio"),
                "beta": f.get("beta"),
                "52w_high": f.get("52w_high"),
                "52w_low": f.get("52w_low"),
            })
    return out


def performance(symbol: str, periods: list[str] | None = None) -> dict:
    """Return % return over multiple periods (1mo, 3mo, 6mo, 1y).
    Uses yfinance history directly (independent of the throttled Yahoo chart
    path used by quotes) so it can't be blocked by quote traffic. Fetches the
    longest period once and derives all shorter periods from it."""
    import concurrent.futures
    symbol = symbol.strip().upper()
    periods = periods or ["1mo", "3mo", "6mo", "1y"]
    out: dict[str, Any] = {"symbol": symbol, "returns": {}}

    # Map period → yfinance period string (fetch the longest, slice the rest).
    yf_period = "1y"
    if "5y" in periods:
        yf_period = "5y"
    elif "2y" in periods:
        yf_period = "2y"
    elif "1y" in periods:
        yf_period = "1y"

    try:
        def _fetch():
            import yfinance as yf
            return yf.Ticker(symbol).history(period=yf_period)
        with concurrent.futures.ThreadPoolExecutor() as ex:
            hist = ex.submit(_fetch).result(timeout=10)
        if hist.empty:
            return out
        closes = [float(c) for c in hist["Close"].tolist() if c == c]  # drop NaN
    except Exception:  # noqa: BLE001
        return out

    # period → number of trading days to slice from the end
    period_days = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504, "5y": 1260}
    last = closes[-1]
    for p in periods:
        days = period_days.get(p, 252)
        if len(closes) > days:
            first = closes[-days]
        elif len(closes) >= 2:
            first = closes[0]
        else:
            out["returns"][p] = None
            continue
        out["returns"][p] = round((last - first) / first * 100, 2) if first else None
    return out


def macro_indicators() -> dict:
    """Macro temperature via representative ETFs. Uses Alpha Vantage GLOBAL_QUOTE
    (the same stable, key-backed source as portfolio quotes) instead of Yahoo
    which gets rate-limited in containers. Macro is cached 5 min so the 6 ETF
    fetches only happen once per refresh cycle."""
    from ..market.service import _av_global_quote, _cache_get, _cache_set, get_quote, CACHE_TTL

    found, cached = _cache_get("macro:snapshot", CACHE_TTL * 3)
    if found and cached:
        return cached

    proxies = {
        "SPY (标普500)": "SPY",
        "QQQ (纳指100)": "QQQ",
        "TLT (20年美债)": "TLT",
        "GLD (黄金)": "GLD",
    }
    out = []
    for label, sym in proxies.items():
        price = day_pct = None
        q = get_quote(sym)  # goes through AV (throttled+cached) → Yahoo fallback
        if q:
            price = q.price
            day_pct = q.day_change_pct
        out.append({
            "label": label, "symbol": sym,
            "price": price, "day_change_pct": day_pct,
        })
    result = {"indicators": out,
              "note": "宏观温度计：通过代表性ETF观察各大类资产当日表现"}
    _cache_set("macro:snapshot", result)
    return result


def earnings_calendar(symbols: list[str]) -> list[dict]:
    """Best-effort earnings dates for given symbols (from yfinance)."""
    out = []
    for sym in symbols:
        sym = sym.strip().upper()
        if not sym:
            continue
        try:
            import yfinance as yf
            cal = yf.Ticker(sym).calendar
            earnings = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if earnings and hasattr(earnings, "__iter__"):
                import datetime as dt
                dates = []
                for e in list(earnings)[:2]:
                    if isinstance(e, (int, float)):
                        dates.append(dt.datetime.fromtimestamp(e).strftime("%Y-%m-%d"))
                    elif hasattr(e, "strftime"):
                        dates.append(e.strftime("%Y-%m-%d"))
                if dates:
                    out.append({"symbol": sym, "next_earnings": dates[0]})
        except Exception:  # noqa: BLE001
            continue
    return out
