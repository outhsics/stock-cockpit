"""FastAPI application entrypoint.

Mounts all routers, sets up CORS, runs DB init + seed, and starts the scheduler.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .auth.routes import router as auth_router
from .config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("cockpit")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB, seed default admin, start scheduler.
    from .database import init_db

    init_db()
    log.info("Database initialized at %s", settings.database_url)

    # Seed admin (always via inline to avoid import path issues).
    _inline_seed()

    # Start scheduler (optional, fails gracefully if APScheduler missing).
    try:
        from .scheduler import start_scheduler

        start_scheduler()
    except Exception as exc:  # noqa: BLE001
        log.warning("Scheduler not started: %s", exc)

    yield
    log.info("Shutting down.")


def _inline_seed() -> None:
    import secrets

    from sqlalchemy import select

    from .auth.service import hash_password
    from .database import SessionLocal
    from .models import User

    db = SessionLocal()
    try:
        exists = db.execute(
            select(User).where(User.username == settings.default_admin_username)
        ).scalar_one_or_none()
        if exists:
            log.info("Admin '%s' exists, skipping seed", exists.username)
            return
        password = settings.default_admin_password or secrets.token_urlsafe(12)
        db.add(User(username=settings.default_admin_username, hashed_password=hash_password(password)))
        db.commit()
        log.info("[seed] Admin created: %s / %s", settings.default_admin_username, password)
    finally:
        db.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    app.include_router(auth_router)
    from .portfolio.routes import router as portfolio_router

    app.include_router(portfolio_router)
    from .market.routes import router as market_router

    app.include_router(market_router)
    from .news.routes import router as news_router

    app.include_router(news_router)
    from .briefing.routes import router as briefing_router

    app.include_router(briefing_router)
    from .chat.routes import router as chat_router

    app.include_router(chat_router)
    from .congress.routes import router as congress_router

    app.include_router(congress_router)
    from .research.routes import router as research_router

    app.include_router(research_router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}

    # Serve built frontend (if present) with proper SPA fallback.
    # API routes (/api/*) are matched first by the routers above; static assets
    # (JS/CSS/images) are served from the dist dir; any OTHER path (e.g.
    # /dashboard, /briefing) returns index.html so client-side routing works
    # on direct visits / refreshes.
    candidates = [
        Path("/app/frontend/dist"),
        Path(__file__).resolve().parent.parent / "frontend" / "dist",
        Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    ]
    frontend_dist = next((p for p in candidates if (p / "index.html").is_file()), None)
    if frontend_dist:
        from fastapi.responses import FileResponse

        # Serve static assets (hashed files under /assets, favicon, etc).
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        index_file = frontend_dist / "index.html"
        index_bytes = index_file.read_bytes()
        index_etag = f'W/"{hash(index_bytes) & 0xFFFFFFFF:x}"'

        # Favicon + other top-level static files (favicon.svg, etc).
        @app.get("/favicon.svg", include_in_schema=False)
        async def favicon():
            fav = frontend_dist / "favicon.svg"
            if fav.is_file():
                return FileResponse(str(fav))
            return Response(status_code=404)

        # SPA fallback: any GET that isn't /api/* or a static file → index.html.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            # Serve a real static file if it exists at that path (e.g. other
            # top-level files). Otherwise return index.html for client routing.
            candidate = frontend_dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(str(candidate))
            return Response(
                content=index_bytes,
                media_type="text/html",
                headers={"etag": index_etag},
            )

        log.info("Serving SPA frontend from %s (with route fallback)", frontend_dist)
    else:
        log.info("No built frontend found (tried %s); API-only mode.", candidates)

    return app

    return app


app = create_app()
