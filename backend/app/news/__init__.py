"""News package."""
from .routes import router
from .service import fetch_and_store_news, list_recent_news

__all__ = ["router", "fetch_and_store_news", "list_recent_news"]
