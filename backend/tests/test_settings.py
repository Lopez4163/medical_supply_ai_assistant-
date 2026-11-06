import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        # This deliberately exercises Pydantic Settings without its runtime environment source.
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_settings_reject_non_psycopg_postgres_url() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL psycopg"):
        Settings(database_url="postgresql://localhost/medical_supply")
