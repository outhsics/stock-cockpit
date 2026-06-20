"""APScheduler setup: daily briefing + periodic news refresh.

Runs in-process inside the FastAPI app (BackgroundScheduler). All jobs use the
default in-memory store; on restart they simply resume from the next cron tick.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _daily_briefing_job() -> None:
    """Generate a briefing for every active user."""
    from sqlalchemy import select

    from .database import SessionLocal
    from .briefing.service import generate_briefing_for_user
    from .models import User

    db = SessionLocal()
    try:
        users = list(db.execute(select(User).where(User.is_active.is_(True))).scalars().all())
        log.info("daily briefing job: %d users", len(users))
        for u in users:
            try:
                generate_briefing_for_user(db, u, scope="daily")
            except Exception as exc:  # noqa: BLE001
                log.error("briefing for %s failed: %s", u.username, exc)
    finally:
        db.close()


def _news_refresh_job() -> None:
    """Refresh general market news (no symbol needed)."""
    from .database import SessionLocal
    from .news.service import fetch_and_store_news

    db = SessionLocal()
    try:
        result = fetch_and_store_news(db, symbols=[])
        log.info("news refresh job: +%d", result["new"])
    except Exception as exc:  # noqa: BLE001
        log.error("news refresh failed: %s", exc)
    finally:
        db.close()


def _price_refresh_job() -> None:
    """Hourly background refresh of all users' holding prices. Keeps caches
    warm so dashboard loads are instant and we don't hammer data sources when
    users click (each symbol fetched ~once/hour, well under rate limits)."""
    from sqlalchemy import select

    from .database import SessionLocal
    from .models import User
    from .portfolio.service import refresh_prices

    db = SessionLocal()
    try:
        users = list(db.execute(select(User).where(User.is_active.is_(True))).scalars().all())
        for u in users:
            try:
                refresh_prices(db, u)
            except Exception as exc:  # noqa: BLE001
                log.error("price refresh for %s failed: %s", u.username, exc)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone="UTC")

    # Daily briefing at configured UTC time (default 05:00 UTC ≈ 01:00 ET).
    sched.add_job(
        _daily_briefing_job,
        CronTrigger(hour=settings.briefing_cron_hour, minute=settings.briefing_cron_minute),
        id="daily_briefing",
        replace_existing=True,
    )

    # Hourly price refresh — keeps quote cache warm without user interaction.
    sched.add_job(
        _price_refresh_job,
        CronTrigger(minute=7),  # :07 every hour
        id="price_refresh",
        replace_existing=True,
    )

    # Periodic news refresh.
    sched.add_job(
        _news_refresh_job,
        IntervalTrigger(minutes=settings.news_refresh_minutes),
        id="news_refresh",
        replace_existing=True,
        next_run_time=None,  # don't fire immediately on boot
    )

    sched.start()
    _scheduler = sched
    log.info(
        "Scheduler started: daily_briefing@%02d:%02d UTC, news_refresh every %d min",
        settings.briefing_cron_hour, settings.briefing_cron_minute, settings.news_refresh_minutes,
    )
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
