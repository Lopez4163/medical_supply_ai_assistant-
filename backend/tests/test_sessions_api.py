from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sessions import get_session_service
from app.core.settings import get_settings
from app.db.session import get_database_engine
from app.main import app
from app.models.conversation import Conversation, ConversationMessage, GuestSession
from app.services.sessions import InvalidGuestSession, SessionService


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = get_database_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def client_and_session(
    db_session: AsyncSession,
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    def get_test_session_service() -> SessionService:
        return SessionService(db_session, get_settings())

    app.dependency_overrides[get_session_service] = get_test_session_service
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Origin": "http://test"},
        ) as client:
            yield client, db_session
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bootstrap_creates_hashed_session_conversation_and_welcome_once(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = client_and_session

    created = await client.post("/api/v1/sessions")
    restored = await client.post("/api/v1/sessions")

    assert created.status_code == 201
    assert restored.status_code == 200
    assert created.json()["restored"] is False
    assert restored.json()["restored"] is True
    assert created.json()["conversation_id"] == restored.json()["conversation_id"]
    assert "synthetic-data demo" in created.json()["welcome_message"]

    cookie = client.cookies.get("bmh_guest")
    assert cookie is not None
    stored_session = await session.scalar(select(GuestSession))
    assert stored_session is not None
    assert stored_session.token_hash != cookie
    assert len(stored_session.token_hash) == 64
    assert await session.scalar(select(func.count(Conversation.id))) == 1
    assert await session.scalar(select(func.count(ConversationMessage.id))) == 1
    welcome = await session.scalar(select(ConversationMessage))
    assert welcome is not None
    assert welcome.role == "assistant"
    assert welcome.message_kind == "welcome"
    assert welcome.content_json == {"text": created.json()["welcome_message"]}

    cookie_header = created.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/" in cookie_header
    assert "domain=" not in cookie_header


@pytest.mark.asyncio
async def test_current_requires_the_cookie_and_never_uses_client_conversation_identifiers(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    missing = await client.get("/api/v1/sessions/current")
    created = await client.post("/api/v1/sessions")
    current = await client.get("/api/v1/sessions/current")

    other_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    try:
        attempted_cross_access = await other_client.get(
            "/api/v1/sessions/current",
            params={"conversation_id": created.json()["conversation_id"]},
        )
    finally:
        await other_client.aclose()

    assert missing.status_code == 401
    assert current.status_code == 200
    assert current.json()["conversation_id"] == created.json()["conversation_id"]
    assert attempted_cross_access.status_code == 401


@pytest.mark.asyncio
async def test_bootstrap_rejects_cross_origin_requests(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    response = await client.post("/api/v1/sessions", headers={"Origin": "https://attacker.test"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_bootstrap_uses_configured_frontend_origins_not_the_backend_host(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _session = client_and_session
    monkeypatch.setenv("TRUSTED_ORIGINS", "https://frontend.example")
    get_settings.cache_clear()

    approved = await client.post("/api/v1/sessions", headers={"Origin": "https://frontend.example"})
    missing = await client.post("/api/v1/sessions", headers={"Origin": ""})
    malformed = await client.post("/api/v1/sessions", headers={"Origin": "not-an-origin"})
    cross_origin = await client.post(
        "/api/v1/sessions", headers={"Origin": "https://attacker.example"}
    )

    assert approved.status_code == 201
    assert missing.status_code == malformed.status_code == cross_origin.status_code == 403


@pytest.mark.asyncio
async def test_current_rejects_expired_and_revoked_cookie_sessions(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = client_and_session

    created = await client.post("/api/v1/sessions")
    assert created.status_code == 201
    expired_session = await session.scalar(select(GuestSession))
    assert expired_session is not None
    expired_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    expired = await client.get("/api/v1/sessions/current")
    await session.rollback()
    replacement = await client.post("/api/v1/sessions")
    active_session = await session.scalar(
        select(GuestSession).where(GuestSession.expires_at > datetime.now(UTC))
    )
    assert active_session is not None
    active_session.revoked_at = datetime.now(UTC)
    await session.flush()
    revoked = await client.get("/api/v1/sessions/current")

    assert expired.status_code == 401
    assert replacement.status_code == 201
    assert revoked.status_code == 401


@pytest.mark.asyncio
async def test_expiration_renewal_and_revocation_enforce_protected_session_boundaries(
    db_session: AsyncSession,
) -> None:
    clock = MutableClock(datetime(2026, 11, 9, tzinfo=UTC))
    service = SessionService(db_session, get_settings(), now=clock.now)

    created = await service.bootstrap(raw_token=None)
    clock.value += timedelta(days=1)
    read_only_context = await service.require_context(raw_token=created.raw_token)

    assert read_only_context.expires_at == created.expires_at
    await db_session.rollback()

    clock.value += timedelta(days=5, hours=23)
    renewed = await service.bootstrap(raw_token=created.raw_token)

    assert renewed.created is False
    assert renewed.context.conversation_id == created.context.conversation_id
    assert renewed.expires_at == clock.value + timedelta(days=7)

    clock.value += timedelta(days=7, seconds=1)
    with pytest.raises(InvalidGuestSession):
        await service.require_context(raw_token=created.raw_token)
    await db_session.rollback()

    replacement = await service.bootstrap(raw_token=created.raw_token)
    assert replacement.created is True
    assert replacement.context.conversation_id != created.context.conversation_id

    guest_session = await db_session.get(GuestSession, replacement.context.guest_session_id)
    assert guest_session is not None
    guest_session.revoked_at = clock.value
    await db_session.flush()
    with pytest.raises(InvalidGuestSession):
        await service.require_context(raw_token=replacement.raw_token)


@pytest.mark.asyncio
async def test_conversation_uniqueness_and_initialization_rollback_are_enforced(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SessionService(db_session, get_settings())
    created = await service.bootstrap(raw_token=None)

    async with db_session.begin_nested():
        db_session.add(
            Conversation(
                guest_session_id=created.context.guest_session_id,
                langgraph_thread_id="duplicate-thread",
                welcome_persisted_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()
    await db_session.rollback()

    original_flush = db_session.flush

    async def fail_flush(*_: object, **__: object) -> None:
        raise RuntimeError("forced initialization failure")

    monkeypatch.setattr(db_session, "flush", fail_flush)
    with pytest.raises(RuntimeError, match="forced initialization failure"):
        await service.bootstrap(raw_token=None)
    monkeypatch.setattr(db_session, "flush", original_flush)

    assert await db_session.scalar(select(func.count(GuestSession.id))) == 1
