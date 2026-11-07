import os

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.core.settings import get_settings
from app.db.session import dispose_database_engine


def require_test_database_url() -> str:
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    if not test_database_url:
        pytest.fail("TEST_DATABASE_URL must be set before running backend tests.")

    try:
        database_name = make_url(test_database_url).database
    except ArgumentError:
        pytest.fail("TEST_DATABASE_URL must be a valid SQLAlchemy database URL.")

    if database_name != "medical_supply_test":
        pytest.fail("TEST_DATABASE_URL must target the isolated medical_supply_test database.")

    return test_database_url


@pytest_asyncio.fixture(autouse=True)
async def reset_database_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", require_test_database_url())
    get_settings.cache_clear()
    await dispose_database_engine()
    yield
    await dispose_database_engine()
    get_settings.cache_clear()
