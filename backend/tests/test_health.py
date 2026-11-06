from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.api.v1.router import get_database_engine
from app.main import app


@pytest.mark.asyncio
async def test_liveness_does_not_require_database() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_reports_ready_for_migrated_test_database() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_hides_database_failure_details() -> None:
    async def get_unavailable_engine() -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(
            "postgresql+psycopg://127.0.0.1:1/unavailable",
            connect_args={"connect_timeout": 1},
        )
        try:
            yield engine
        finally:
            await engine.dispose()

    app.dependency_overrides[get_database_engine] = get_unavailable_engine
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
