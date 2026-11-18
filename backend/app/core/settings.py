from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
_PRODUCTION_SECRET_PLACEHOLDER_MARKERS = (
    "replace-with",
    "change-me",
    "example",
    "placeholder",
    "development",
    "test-secret",
)


class Settings(BaseSettings):
    """Runtime configuration loaded only when settings are requested."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    app_environment: Literal["development", "test", "production"] = "development"
    session_token_hash_secret: SecretStr
    guest_session_inactivity_days: int = 7
    trusted_origins: str = "http://localhost:3000,http://localhost:8000"
    chat_provider: Literal["mock", "langgraph"] = "mock"
    welcome_message: str = (
        "Welcome to BioMedicHospicare's AI Supply Assistant! I can help you explore our "
        "demonstration medical-supply catalog, check availability, and prepare a quotation "
        "inquiry. This is a synthetic-data demo, not a live ordering service."
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        url = make_url(value)
        if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
            raise ValueError("DATABASE_URL must be a PostgreSQL psycopg connection URL.")
        return value

    @field_validator("session_token_hash_secret")
    @classmethod
    def validate_session_token_hash_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("SESSION_TOKEN_HASH_SECRET must be at least 32 characters.")
        return value

    @model_validator(mode="after")
    def reject_production_secret_placeholders(self) -> Self:
        """Prevent development-only settings from reaching production."""
        if self.app_environment != "production":
            return self

        if self.chat_provider == "mock":
            raise ValueError("CHAT_PROVIDER=mock is not permitted in production.")

        normalized_secret = self.session_token_hash_secret.get_secret_value().strip().casefold()
        if any(marker in normalized_secret for marker in _PRODUCTION_SECRET_PLACEHOLDER_MARKERS):
            raise ValueError(
                "SESSION_TOKEN_HASH_SECRET must not use a development or example placeholder "
                "in production."
            )
        return self

    @property
    def quotation_trusted_origins(self) -> tuple[str, ...]:
        """Configured browser origins; reverse proxies must configure this explicitly."""
        origins = tuple(
            origin.strip() for origin in self.trusted_origins.split(",") if origin.strip()
        )
        if not origins:
            raise ValueError("TRUSTED_ORIGINS must define at least one origin.")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("TRUSTED_ORIGINS entries must be absolute origins without a path.")
        return origins

    @property
    def guest_session_cookie_name(self) -> str:
        return "__Host-bmh_guest" if self.app_environment == "production" else "bmh_guest"

    @property
    def guest_session_cookie_secure(self) -> bool:
        return self.app_environment == "production"


@lru_cache
def get_settings() -> Settings:
    # Pydantic Settings resolves this required field from the environment or `.env` at runtime.
    return Settings()  # pyright: ignore[reportCallIssue]
