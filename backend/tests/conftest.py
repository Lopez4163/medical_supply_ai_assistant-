import os

import pytest
import pytest_asyncio

from app.core.settings import get_settings
from app.db.session import dispose_database_engine


@pytest_asyncio.fixture(autouse=True)
async def reset_database_configuration(monkeypatch: pytest.MonkeyPatch):
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    if test_database_url is not None:
        monkeypatch.setenv("DATABASE_URL", test_database_url)
    get_settings.cache_clear()
    await dispose_database_engine()
    yield
    await dispose_database_engine()
    get_settings.cache_clear()
