"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve project paths relative to this file so it works in Docker & locally.
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = Path("/data") if Path("/data").is_dir() else PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Stock Cockpit"
    debug: bool = False

    # --- Database ---
    database_url: str = f"sqlite:///{DATA_DIR / 'cockpit.db'}"

    # --- Auth (JWT) ---
    # These two MUST be overridden via .env for production use.
    secret_key: str = "CHANGE_ME_PLEASE_overwrite_in_.env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- Default admin (created on first run by seed script) ---
    default_admin_username: str = "admin"
    default_admin_password: str = ""  # empty => auto-generated on first seed

    # --- LLM (OpenAI-compatible). Defaults to Z.ai / GLM. ---
    llm_provider: str = "glm"  # glm | openai | deepseek | ollama | custom
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4-flash"
    llm_temperature: float = 0.6

    # --- Market data ---
    # yfinance needs no key. Alpha Vantage is optional fallback.
    alpha_vantage_api_key: str = ""

    # --- Politician/insider trades ---
    # Optional: Quiver Quant free token (https://quiverquant.com). If unset,
    # congress tracking falls back to the public Capitol Trades source.
    quiver_api_token: str = ""

    # --- News ---
    news_refresh_minutes: int = 30
    briefing_cron_hour: int = 5   # 05:00 UTC = ~01:00 ET after market close
    briefing_cron_minute: int = 0

    # --- CORS ---
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
