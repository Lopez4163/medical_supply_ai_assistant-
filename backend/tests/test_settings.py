from typing import Literal

import pytest
from pydantic import SecretStr, ValidationError

from app.core.settings import Settings


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        # This deliberately exercises Pydantic Settings without its runtime environment source.
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_settings_reject_non_psycopg_postgres_url() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL psycopg"):
        Settings(
            database_url="postgresql://localhost/medical_supply",
            session_token_hash_secret=SecretStr("a" * 32),
        )


def test_settings_require_a_long_session_token_hash_secret() -> None:
    with pytest.raises(ValidationError, match="SESSION_TOKEN_HASH_SECRET"):
        Settings(
            database_url="postgresql+psycopg://localhost/medical_supply",
            session_token_hash_secret=SecretStr("too-short"),
        )


@pytest.mark.parametrize(
    "secret",
    [
        "replace-with-a-local-development-secret-at-least-32-characters",
        "change-me-for-local-development-only-at-least-32-characters",
    ],
)
def test_production_rejects_obvious_session_secret_placeholders(secret: str) -> None:
    with pytest.raises(ValidationError, match="development or example placeholder"):
        Settings(
            database_url="postgresql+psycopg://localhost/medical_supply",
            app_environment="production",
            session_token_hash_secret=SecretStr(secret),
        )


def test_production_uses_a_secure_host_only_cookie_name() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://localhost/medical_supply",
        app_environment="production",
        session_token_hash_secret=SecretStr("ConfigValidationValue7281946350zxyKLMNPQ"),
    )

    assert settings.guest_session_cookie_name == "__Host-bmh_guest"
    assert settings.guest_session_cookie_secure is True


@pytest.mark.parametrize("environment", ["development", "test"])
def test_nonproduction_allows_local_session_secret_placeholders(
    environment: Literal["development", "test"],
) -> None:
    settings = Settings(
        database_url="postgresql+psycopg://localhost/medical_supply",
        app_environment=environment,
        session_token_hash_secret=SecretStr(
            "replace-with-a-local-development-secret-at-least-32-characters"
        ),
    )

    assert settings.guest_session_cookie_name == "bmh_guest"
    assert settings.guest_session_cookie_secure is False
