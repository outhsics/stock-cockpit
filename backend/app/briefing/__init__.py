"""Briefing package: AI daily summary generation."""
from .routes import router
from .service import generate_briefing_for_user, get_latest_briefing

__all__ = ["router", "generate_briefing_for_user", "get_latest_briefing"]
