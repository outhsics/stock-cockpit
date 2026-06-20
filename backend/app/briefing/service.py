"""Briefing generation service."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Briefing, User
from ..news.service import list_recent_news
from ..portfolio.service import list_holding_views
from .llm import LLMError, get_llm
from .prompts import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)


def _format_holdings(views) -> str:
    if not views:
        return "（暂无持仓）"
    lines = []
    for v in views:
        direction = "↑" if v.day_change_pct >= 0 else "↓"
        lines.append(
            f"- **{v.symbol}** ({v.name}): 现价 ${v.current_price:.2f}，"
            f"当日 {direction}{abs(v.day_change_pct):.2f}%，"
            f"持仓 {v.shares} 股，市值 ${v.market_value:.2f}，"
            f"累计盈亏 ${v.pnl:+.2f} ({v.pnl_pct:+.2f}%)"
        )
    return "\n".join(lines)


def _format_news(items, max_items: int = 12) -> str:
    if not items:
        return "（暂无相关新闻）"
    lines = []
    for n in items[:max_items]:
        ts = n.published_at.strftime("%m-%d %H:%M") if n.published_at else ""
        sym = f"[{n.symbol}] " if n.symbol else ""
        lines.append(f"- {ts} {sym}({n.source}) {n.title}")
    return "\n".join(lines)


def generate_briefing_for_user(db: Session, user: User, scope: str = "daily") -> Briefing:
    """Generate and persist a new briefing for the given user."""
    views = list_holding_views(db, user)
    symbols = [v.symbol for v in views]
    # Pull news: prioritize holding-specific, fall back to general.
    news = list_recent_news(db, symbol=None, limit=20)

    holdings_text = _format_holdings(views)
    news_text = _format_news(news)

    llm = get_llm()
    if not llm.is_configured:
        content = _stub_briefing(holdings_text, news_text)
        model_name = "stub"
    else:
        try:
            content = llm.chat(
                system=SYSTEM_PROMPT,
                user=build_user_prompt(holdings_text, news_text),
                max_tokens=2000,
            )
            model_name = llm.model
        except LLMError as exc:
            log.error("Briefing generation failed: %s", exc)
            content = _error_briefing(str(exc), holdings_text, news_text)
            model_name = "error"

    briefing = Briefing(
        user_id=user.id,
        scope=scope,
        content=content,
        model=model_name,
    )
    db.add(briefing)
    db.commit()
    db.refresh(briefing)
    return briefing


def _stub_briefing(holdings_text: str, news_text: str) -> str:
    return f"""\
> ⚠️ **AI 未配置**：未检测到 `LLM_API_KEY`，下方为占位简报。
> 请在 `.env` 中设置 `LLM_API_KEY`（推荐智谱 Z.ai：[open.bigmodel.cn](https://open.bigmodel.cn)），
> 然后重启服务，即可获得真实 AI 简报。

---

# 今日持仓快照

{holdings_text}

# 近期新闻

{news_text}

_本简报为未配置 AI 时的占位内容，不构成投资建议。_
"""


def _error_briefing(err: str, holdings_text: str, news_text: str) -> str:
    return f"""\
> ❌ **AI 简报生成失败**：{err}

---

# 持仓快照

{holdings_text}

# 近期新闻

{news_text}

_请检查 LLM 配置（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。_
"""


def get_latest_briefing(db: Session, user: User) -> Briefing | None:
    stmt = (
        select(Briefing)
        .where(Briefing.user_id == user.id)
        .order_by(Briefing.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_briefings(db: Session, user: User, limit: int = 10) -> list[Briefing]:
    stmt = (
        select(Briefing)
        .where(Briefing.user_id == user.id)
        .order_by(Briefing.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
