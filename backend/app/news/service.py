"""News aggregation service.

Sources (all free, no API key):
  - Chinese financial RSS (财联社/华尔街见闻/金十) — primary for CN users
  - Yahoo Finance per-ticker feed — symbol-specific US news
  - General market RSS (CNBC/WSJ/MarketWatch) — broad US coverage

English news headlines+summaries are translated to Chinese via the LLM layer
on demand to keep fetch fast and avoid burning quota on every article.
"""
from __future__ import annotations

import logging
from datetime import datetime
from time import mktime

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import NewsItem

log = logging.getLogger(__name__)

# Chinese financial news sources. We avoid the shared rsshub.app instance
# (frequently 403). These are direct stable RSS endpoints.
CN_FEEDS = [
    # Sina Finance US-markets feed (stable, no middleware).
    ("https://feedx.net/rss/sina.xml", "新浪财经"),
    # Wallstreetcn RSS (stable official endpoint).
    ("https://rss.wallstreetcn.com/feed.xml", "华尔街见闻"),
    # CLS (财联社) telegraph via their public RSS proxy.
    ("https://rsshub.feeded.xyz/cls/telegraph", "财联社·电报"),
    # 36kr finance
    ("https://36kr.com/feed", "36氪"),
]

# General English finance RSS (translated on demand).
GENERAL_FEEDS = [
    ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC"),
    ("https://feeds.content.dowjones.io/public/rss/SB10001424053111904265604576568171721505600/rss", "WSJ Markets"),
    ("https://www.marketwatch.com/rss/topstories", "MarketWatch"),
]

YAHOO_FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"


def _parse_published(entry) -> datetime | None:
    tp = entry.get("published_parsed") or entry.get("updated_parsed")
    if tp:
        try:
            return datetime.fromtimestamp(mktime(tp))
        except Exception:  # noqa: BLE001
            return None
    return None


def _store_item(db: Session, *, symbol: str | None, title: str, url: str,
                source: str, summary: str, published_at: datetime | None) -> bool:
    existing = db.execute(select(NewsItem).where(NewsItem.url == url)).scalar_one_or_none()
    if existing:
        return False
    db.add(NewsItem(
        symbol=symbol,
        title=title[:500],
        url=url[:1000],
        source=source,
        summary=(summary or "")[:2000],
        published_at=published_at,
    ))
    return True


def _is_cn_source(source: str) -> bool:
    return any(k in source for k in ["财联社", "华尔街见闻", "金十", "新浪", "中文"])


def _looks_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def fetch_for_symbol(db: Session, symbol: str, limit: int = 20) -> int:
    symbol = symbol.strip().upper()
    url = YAHOO_FEED.format(sym=symbol)
    feed = feedparser.parse(url)
    added = 0
    for entry in feed.entries[:limit]:
        link = entry.get("link", "")
        if not link:
            continue
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()
        published = _parse_published(entry)
        if _store_item(db, symbol=symbol, title=title, url=link,
                       source="Yahoo Finance", summary=summary, published_at=published):
            added += 1
    db.commit()
    return added


def _fetch_feed_list(db: Session, feeds: list[tuple[str, str]], limit_per_feed: int = 15) -> int:
    added = 0
    for feed_url, source in feeds:
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                log.debug("feed %s unreadable: %s", source, getattr(feed, "bozo_exception", "?"))
                continue
        except Exception as exc:  # noqa: BLE001
            log.debug("feed parse failed (%s): %s", source, exc)
            continue
        for entry in feed.entries[:limit_per_feed]:
            link = entry.get("link", "")
            if not link:
                continue
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            published = _parse_published(entry)
            if _store_item(db, symbol=None, title=title, url=link,
                           source=source, summary=summary, published_at=published):
                added += 1
    db.commit()
    return added


def fetch_cn(db: Session, limit_per_feed: int = 15) -> int:
    return _fetch_feed_list(db, CN_FEEDS, limit_per_feed)


def fetch_general(db: Session, limit_per_feed: int = 15) -> int:
    return _fetch_feed_list(db, GENERAL_FEEDS, limit_per_feed)


def fetch_and_store_news(db: Session, symbols: list[str] | None = None) -> dict:
    cn_n = fetch_cn(db)
    total = cn_n
    by_symbol: dict[str, int] = {}
    for sym in symbols or []:
        n = fetch_for_symbol(db, sym)
        by_symbol[sym] = n
        total += n
    total += fetch_general(db)
    log.info("news fetch: +%d new (cn=%d, %s)", total, cn_n, by_symbol)
    return {"new": total, "cn": cn_n, "by_symbol": by_symbol}


def list_recent_news(db: Session, symbol: str | None = None, limit: int = 50,
                     lang: str | None = None) -> list[NewsItem]:
    stmt = select(NewsItem)
    if symbol:
        stmt = stmt.where(NewsItem.symbol == symbol.upper())
    stmt = stmt.order_by(NewsItem.published_at.desc().nullslast(),
                         NewsItem.fetched_at.desc()).limit(limit)
    items = list(db.execute(stmt).scalars().all())
    if lang == "cn":
        items = [i for i in items if _is_cn_source(i.source) or _looks_chinese(i.title)]
    elif lang == "en":
        items = [i for i in items if not (_is_cn_source(i.source) or _looks_chinese(i.title))]
    return items


def translate_news_batch(items: list[NewsItem], llm) -> int:
    """Translate English news titles+summaries to Chinese via LLM (in place).
    Returns count translated."""
    if not items or not getattr(llm, "is_configured", False):
        return 0
    to_translate = [i for i in items if not _looks_chinese(i.title) and not _is_cn_source(i.source)]
    if not to_translate:
        return 0

    import json
    lines = []
    for i, it in enumerate(to_translate[:20]):
        lines.append(f"[{i}] TITLE: {it.title}\nSUMMARY: {(it.summary or '')[:200]}")
    user = (
        "把以下英文财经新闻翻译成中文（保留专业术语如 ETF/QQQ/美联储）。"
        "只翻译，不要添加内容。返回JSON数组，每个元素 {\"i\":序号,\"title\":中文标题,\"summary\":中文摘要}。\n\n"
        + "\n\n".join(lines)
    )
    try:
        raw = llm.chat(
            system="你是专业的财经翻译。严格输出合法JSON数组，不要markdown代码块，不要解释。",
            user=user,
            max_tokens=1500,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        arr = json.loads(raw)
        count = 0
        for item in arr:
            idx = item.get("i")
            if idx is None or idx >= len(to_translate):
                continue
            news = to_translate[idx]
            if item.get("title"):
                news.title = str(item["title"])[:500]
            if item.get("summary"):
                news.summary = str(item["summary"])[:2000]
            count += 1
        return count
    except Exception as exc:  # noqa: BLE001
        log.warning("news translation failed: %s", exc)
        return 0
