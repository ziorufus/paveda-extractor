import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # Google OAuth2
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Where the browser is sent back after login
    frontend_url: str = "http://localhost:5173"
    # Comma-separated list; defaults to frontend_url
    cors_origins: str = ""

    # Session tokens (JWT)
    secret_key: str = ""
    token_expire_hours: int = 24 * 7

    # Converter configuration (essential version of scripts/config.json)
    config_file: str = "config.json"

    # SQLAlchemy connection string
    database_url: str = "sqlite:///./valpal.db"

    @property
    def cors_origin_list(self):
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or [self.frontend_url.rstrip("/")]


@lru_cache
def get_settings():
    settings = Settings()
    if not settings.secret_key:
        logger.warning("SECRET_KEY is not set: using a random key, sessions will not survive a restart")
        settings.secret_key = secrets.token_urlsafe(48)
    return settings
