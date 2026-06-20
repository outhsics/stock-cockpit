"""ORM models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Holding(Base):
    """A user's position in a single ticker (shares + cost basis)."""

    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)  # e.g. QQQ, VOO
    shares: Mapped[float] = mapped_column(Float)
    cost_basis: Mapped[float] = mapped_column(Float)  # average price paid per share
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped[User] = relationship(back_populates="holdings")


class NewsItem(Base):
    """Cached news entry (deduplicated by url)."""

    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class Briefing(Base):
    """An AI-generated daily briefing, stored as markdown."""

    __tablename__ = "briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(32), default="daily")  # daily | adhoc
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class ChatMessage(Base):
    """AI Q&A conversation history."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    context_snapshot: Mapped[str] = mapped_column(Text, default="")  # holdings/news at Q time
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class CongressTrade(Base):
    """US politician / insider trades (from Quiver Quant)."""

    __tablename__ = "congress_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    politician: Mapped[str] = mapped_column(String(128))
    chamber: Mapped[str] = mapped_column(String(16), default="")  # House | Senate
    party: Mapped[str] = mapped_column(String(16), default="")
    transaction_type: Mapped[str] = mapped_column(String(16))  # Buy | Sell
    amount: Mapped[str] = mapped_column(String(64), default="")
    traded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="quiver")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

