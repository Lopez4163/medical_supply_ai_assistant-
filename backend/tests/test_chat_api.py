"""HTTPX/PostgreSQL coverage for the deterministic API-08 chat provider."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.chat import get_chat_service
from app.api.v1.conversations import get_conversation_service
from app.api.v1.sessions import get_session_service
from app.core.settings import Settings, get_settings
from app.db.session import get_database_engine, get_session_factory
from app.dev.seed_catalog import seed_catalog
from app.main import app
from app.models.conversation import Conversation, ConversationMessage, GuestSession
from app.models.quotation import OutboxJob, QuoteDraft, QuoteDraftLine, QuoteSubmission
from app.schemas.chat import ChatTurnRequest
from app.services.chat import ChatService
from app.services.conversations import ConversationService
from app.services.sessions import SessionService


@pytest_asyncio.fixture
async def chat_client() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    engine = get_database_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        def session_service() -> SessionService:
            return SessionService(session, get_settings())

        def chat_service() -> ChatService:
            return ChatService(session, get_settings())

        def conversation_service() -> ConversationService:
            return ConversationService(session)

        app.dependency_overrides[get_session_service] = session_service
        app.dependency_overrides[get_chat_service] = chat_service
        app.dependency_overrides[get_conversation_service] = conversation_service
        try:
            await seed_catalog(session)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Origin": "http://test"},
            ) as client:
                yield client, session
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_chat_persists_search_turn_replays_client_id_and_keeps_inventory_private(
    chat_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = chat_client
    assert (await client.post("/api/v1/sessions")).status_code == 201
    operation = str(uuid4())
    payload = {"client_message_id": operation, "text": "Search nitrile gloves"}

    first = await client.post("/api/v1/chat/messages", json=payload)
    replay = await client.post("/api/v1/chat/messages", json=payload)
    history = await client.get("/api/v1/conversations/current")

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert first.json()["elements"][0]["kind"] == "product_results"
    assert first.json()["elements"][0]["result_context"] == "search"
    assert len(first.json()["elements"][0]["result_set"]["products"]) <= 5
    assert "quantity_on_hand" not in first.text
    assert [message["ordinal"] for message in history.json()["messages"]] == [0, 1, 2]
    assert await session.scalar(select(func.count()).select_from(ConversationMessage)) == 3


@pytest.mark.asyncio
async def test_chat_mutates_only_explicit_add_and_never_submits(
    chat_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = chat_client
    assert (await client.post("/api/v1/sessions")).status_code == 201
    implicit = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "I need PPE-NIT-M"},
    )
    added = await client.post(
        "/api/v1/chat/messages", json={"client_message_id": str(uuid4()), "text": "Add 2 PPE-NIT-M"}
    )

    assert implicit.status_code == added.status_code == 200
    assert implicit.json()["draft_changed"] is False
    assert added.json()["draft_changed"] is True
    assert await session.scalar(select(func.count()).select_from(QuoteSubmission)) == 0
    assert await session.scalar(select(func.count()).select_from(OutboxJob)) == 0


@pytest.mark.asyncio
async def test_chat_accepts_only_strict_positive_quote_commands_and_supports_review(
    chat_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = chat_client
    assert (await client.post("/api/v1/sessions")).status_code == 201

    for text in (
        "do not add 2 PPE-NIT-M",
        '"add 2 PPE-NIT-M"',
        "if available, add 2 PPE-NIT-M",
        "add PPE-NIT-M",
    ):
        response = await client.post(
            "/api/v1/chat/messages", json={"client_message_id": str(uuid4()), "text": text}
        )
        assert response.status_code == 200
        assert response.json()["draft_changed"] is False

    added = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Add 2 PPE-NIT-M"},
    )
    updated = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Update PPE-NIT-M to 3"},
    )
    removed = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Remove PPE-NIT-M"},
    )
    readded = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Add 1 PPE-NIT-M"},
    )
    review = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Review my draft quote"},
    )

    assert all(response.json()["draft_changed"] for response in (added, updated, removed, readded))
    assert review.json()["draft_changed"] is False
    assert [element["kind"] for element in review.json()["elements"]] == [
        "quote_update",
        "confirmation_prompt",
    ]
    line = await session.scalar(select(QuoteDraftLine))
    assert line is not None and line.quantity == 1
    assert await session.scalar(select(func.count()).select_from(QuoteSubmission)) == 0


@pytest.mark.asyncio
async def test_chat_paginates_results_with_a_session_scoped_signed_cursor(
    chat_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _ = chat_client
    assert (await client.post("/api/v1/sessions")).status_code == 201
    first = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Search products"},
    )
    cursor = first.json()["elements"][0]["result_set"]["next_cursor"]
    assert first.status_code == 200
    assert cursor is not None
    assert len(first.json()["elements"][0]["result_set"]["products"]) == 5

    second = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "show more", "cursor": cursor},
    )
    invalid = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "show more", "cursor": f"{cursor}x"},
    )

    first_skus = {
        product["sku"] for product in first.json()["elements"][0]["result_set"]["products"]
    }
    second_skus = {
        product["sku"] for product in second.json()["elements"][0]["result_set"]["products"]
    }
    assert second.status_code == 200
    assert len(second_skus) <= 5 and first_skus.isdisjoint(second_skus)
    assert invalid.status_code == 200 and invalid.json()["elements"] == []


@pytest.mark.asyncio
async def test_chat_returns_inventory_alternatives_and_safe_guidance(
    chat_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = chat_client
    assert (await client.post("/api/v1/sessions")).status_code == 201

    inventory = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Is PPE-NIT-M available?"},
    )
    alternatives = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Alternatives for CON-UNDER-10"},
    )
    support = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "I need support"},
    )
    company = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "What are your company hours?"},
    )
    fallback = await client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid4()), "text": "Should I change my medication?"},
    )

    assert inventory.json()["elements"][0]["kind"] == "inventory_notice"
    assert "quantity_on_hand" not in inventory.text
    assert (
        alternatives.status_code
        == support.status_code
        == company.status_code
        == fallback.status_code
        == 200
    )
    alternative_results = alternatives.json()["elements"][0]
    assert alternative_results["kind"] == "product_results"
    assert alternative_results["result_context"] == "alternatives"
    assert len(alternative_results["result_set"]["products"]) <= 3
    assert support.json()["elements"][0]["kind"] == "support_inquiry_form"
    assert company.json()["elements"] == [] and fallback.json()["elements"] == []
    assert await session.scalar(select(func.count()).select_from(QuoteSubmission)) == 0
    assert await session.scalar(select(func.count()).select_from(OutboxJob)) == 0


@pytest.mark.asyncio
async def test_chat_requires_guest_and_trusted_origin(
    chat_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = chat_client
    payload = {"client_message_id": str(uuid4()), "text": "Search nitrile gloves"}

    missing_guest = await client.post("/api/v1/chat/messages", json=payload)
    assert missing_guest.status_code == 401

    assert (await client.post("/api/v1/sessions")).status_code == 201
    missing_origin = await client.post(
        "/api/v1/chat/messages", json=payload, headers={"Origin": ""}
    )
    assert missing_origin.status_code == 403
    cross_origin = await client.post(
        "/api/v1/chat/messages", json=payload, headers={"Origin": "https://untrusted.example"}
    )
    assert cross_origin.status_code == 403
    first_turn = await client.post("/api/v1/chat/messages", json=payload)
    assert first_turn.status_code == 200

    assert await session.scalar(select(func.count()).select_from(ConversationMessage)) == 3


def test_unimplemented_langgraph_provider_fails_safely() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://localhost/medical_supply_test",
        app_environment="test",
        chat_provider="langgraph",
        session_token_hash_secret=SecretStr("test-session-hash-secret-with-at-least-32-characters"),
    )
    with pytest.raises(HTTPException) as raised:
        get_chat_service(AsyncSession(), settings)
    assert raised.value.status_code == 503
    assert raised.value.detail == {
        "code": "AI_UNAVAILABLE",
        "message": "The configured chat provider is not available.",
    }


@pytest.mark.asyncio
async def test_client_message_replay_is_scoped_to_its_guest_conversation() -> None:
    factory = get_session_factory()
    async with factory() as setup_session:
        first = await SessionService(setup_session, get_settings()).bootstrap(raw_token=None)
    async with factory() as setup_session:
        second = await SessionService(setup_session, get_settings()).bootstrap(raw_token=None)
    request = ChatTurnRequest(client_message_id=uuid4(), text="Tell me about the company")
    try:
        async with factory() as first_session:
            first_response = await ChatService(first_session, get_settings()).respond(
                guest=first.context, request=request
            )
        async with factory() as second_session:
            second_response = await ChatService(second_session, get_settings()).respond(
                guest=second.context, request=request
            )

        assert first_response.conversation_id != second_response.conversation_id
        assert first_response.user_message.id != second_response.user_message.id
        async with factory() as verification_session:
            for conversation_id in (first.context.conversation_id, second.context.conversation_id):
                assert (
                    await verification_session.scalar(
                        select(func.count())
                        .select_from(ConversationMessage)
                        .where(ConversationMessage.conversation_id == conversation_id)
                    )
                    == 3
                )
    finally:
        async with factory() as cleanup_session:
            async with cleanup_session.begin():
                for bootstrap in (first, second):
                    await cleanup_session.execute(
                        delete(ConversationMessage).where(
                            ConversationMessage.conversation_id == bootstrap.context.conversation_id
                        )
                    )
                    await cleanup_session.execute(
                        delete(Conversation).where(
                            Conversation.id == bootstrap.context.conversation_id
                        )
                    )
                    await cleanup_session.execute(
                        delete(GuestSession).where(
                            GuestSession.id == bootstrap.context.guest_session_id
                        )
                    )


@pytest.mark.asyncio
async def test_concurrent_duplicate_client_message_reuses_one_persisted_turn() -> None:
    factory = get_session_factory()
    async with factory() as setup_session:
        bootstrap = await SessionService(setup_session, get_settings()).bootstrap(raw_token=None)
    request_id = uuid4()

    async def send() -> object:
        async with factory() as transaction_session:
            return await ChatService(transaction_session, get_settings()).respond(
                guest=bootstrap.context,
                request=ChatTurnRequest(
                    client_message_id=request_id, text="Tell me about the company"
                ),
            )

    try:
        results = await asyncio.gather(send(), send())
        assert results[0] == results[1]
        async with factory() as verification_session:
            messages = list(
                (
                    await verification_session.scalars(
                        select(ConversationMessage)
                        .where(
                            ConversationMessage.conversation_id == bootstrap.context.conversation_id
                        )
                        .order_by(ConversationMessage.server_ordinal)
                    )
                ).all()
            )
        assert [message.server_ordinal for message in messages] == [0, 1, 2]
        assert sum(message.client_message_id == request_id for message in messages) == 1
    finally:
        async with factory() as cleanup_session:
            async with cleanup_session.begin():
                await cleanup_session.execute(
                    delete(ConversationMessage).where(
                        ConversationMessage.conversation_id == bootstrap.context.conversation_id
                    )
                )
                await cleanup_session.execute(
                    delete(Conversation).where(Conversation.id == bootstrap.context.conversation_id)
                )
                await cleanup_session.execute(
                    delete(GuestSession).where(
                        GuestSession.id == bootstrap.context.guest_session_id
                    )
                )


@pytest.mark.asyncio
async def test_chat_turn_rolls_back_both_messages_with_caller_transaction() -> None:
    factory = get_session_factory()
    async with factory() as setup_session:
        bootstrap = await SessionService(setup_session, get_settings()).bootstrap(raw_token=None)
    try:
        async with get_database_engine().connect() as connection:
            outer_transaction = await connection.begin()
            transaction_session = AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                response = await ChatService(transaction_session, get_settings()).respond(
                    guest=bootstrap.context,
                    request=ChatTurnRequest(client_message_id=uuid4(), text="Add 2 PPE-NIT-M"),
                )
                assert response.assistant_message.ordinal == 2
            finally:
                await transaction_session.close()
                await outer_transaction.rollback()

        async with factory() as verification_session:
            message_count = await verification_session.scalar(
                select(func.count())
                .select_from(ConversationMessage)
                .where(ConversationMessage.conversation_id == bootstrap.context.conversation_id)
            )
        assert message_count == 1
        async with factory() as verification_session:
            assert (
                await verification_session.scalar(
                    select(func.count())
                    .select_from(QuoteDraft)
                    .where(QuoteDraft.guest_session_id == bootstrap.context.guest_session_id)
                )
                == 0
            )
            assert (
                await verification_session.scalar(select(func.count()).select_from(QuoteDraftLine))
                == 0
            )
    finally:
        async with factory() as cleanup_session:
            async with cleanup_session.begin():
                await cleanup_session.execute(
                    delete(ConversationMessage).where(
                        ConversationMessage.conversation_id == bootstrap.context.conversation_id
                    )
                )
                await cleanup_session.execute(
                    delete(Conversation).where(Conversation.id == bootstrap.context.conversation_id)
                )
                await cleanup_session.execute(
                    delete(GuestSession).where(
                        GuestSession.id == bootstrap.context.guest_session_id
                    )
                )
