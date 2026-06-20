"""AI Q&A service: answers user questions using their portfolio + market data
as live context (RAG-style, no vector DB needed for this scale)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..briefing.llm import LLMError, get_llm
from ..briefing.prompts import SYSTEM_PROMPT as _BRIEFING_SYS
from ..models import ChatMessage, User
from ..news.service import list_recent_news
from ..portfolio.service import list_holding_views

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是 Stock Cockpit 的智能投资助手，服务一位正在学习美股的中文用户。

你的能力：
1. 基于用户当前持仓、最新新闻、市场数据回答问题。
2. 解释股票涨跌的原因（结合提供的上下文，不要编造）。
3. 对 ETF、财报、宏观概念做通俗解释。
4. 用中文回答，专业但易懂，可用 Markdown。

规则：
- 如果上下文里没有明确原因，说明"信息不足"，并给出可能的几个方向，不要编造具体事件。
- 涉及买卖建议时，必须强调"仅供参考，不构成投资建议"。
- 回答简洁有重点，除非用户要求详细。
"""


def _build_context(db: Session, user: User) -> str:
    """Assemble a context string from portfolio + recent news."""
    parts: list[str] = []

    views = list_holding_views(db, user)
    if views:
        parts.append("# 我的持仓")
        for v in views:
            arrow = "↑" if v.day_change_pct >= 0 else "↓"
            parts.append(
                f"- {v.symbol} ({v.name}): 现价 ${v.current_price:.2f}, "
                f"当日 {arrow}{abs(v.day_change_pct):.2f}%, "
                f"持仓 {v.shares} 股, 市值 ${v.market_value:.2f}, "
                f"累计盈亏 ${v.pnl:+.2f} ({v.pnl_pct:+.2f}%)"
            )
    else:
        parts.append("# 我的持仓\n（暂无持仓）")

    news = list_recent_news(db, limit=10)
    if news:
        parts.append("\n# 最新相关新闻")
        for n in news[:10]:
            ts = n.published_at.strftime("%m-%d") if n.published_at else ""
            sym = f"[{n.symbol}] " if n.symbol else ""
            parts.append(f"- {ts} {sym}({n.source}) {n.title}")
    return "\n".join(parts)


def ask(db: Session, user: User, question: str) -> dict:
    """Answer a user question. Persists both the question and the answer."""
    context = _build_context(db, user)

    # Save the user's question first.
    db.add(ChatMessage(
        user_id=user.id, role="user", content=question, context_snapshot=context,
    ))
    db.commit()

    llm = get_llm()
    if not llm.is_configured:
        answer = "⚠️ AI 未配置。请在 .env 设置 LLM_API_KEY 后重启服务。"
        model = "stub"
    else:
        try:
            user_msg = f"# 实时上下文\n{context}\n\n# 用户问题\n{question}"
            answer = llm.chat(system=SYSTEM_PROMPT, user=user_msg, max_tokens=1500)
            model = llm.model
        except LLMError as exc:
            log.error("chat failed: %s", exc)
            answer = f"⚠️ 回答失败：{exc}"
            model = "error"

    # Save the assistant's answer.
    msg = ChatMessage(user_id=user.id, role="assistant", content=answer)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "content": answer, "model": model,
            "created_at": msg.created_at.isoformat()}


def history(db: Session, user: User, limit: int = 50) -> list[ChatMessage]:
    from sqlalchemy import select
    stmt = (select(ChatMessage)
            .where(ChatMessage.user_id == user.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit))
    msgs = list(db.execute(stmt).scalars().all())
    msgs.reverse()  # chronological for display
    return msgs
