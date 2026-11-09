from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.conversations import get_conversation_service
from app.api.v1.sessions import get_session_service
from app.core.settings import get_settings
from app.db.session import get_database_engine
from app.dev.seed_catalog import seed_catalog
from app.main import app
from app.models.catalog import CatalogLifecycleStatus, InventoryItem, SkuVariant
from app.models.conversation import Conversation, ConversationMessage, GuestSession
from app.schemas.conversations import (
    ConfirmationPromptElement,
    ConfirmationPromptSnapshot,
    InventoryNoticeElement,
    ProductResultsElement,
    QuoteUpdateElement,
    QuoteUpdateSnapshot,
    SourceReferenceElement,
    SourceReferenceSnapshot,
    SupportInquiryFormElement,
    SupportInquiryFormSnapshot,
)
from app.schemas.products import AvailabilityResponse, ProductCardPublic, ProductSearchResponse
from app.services.conversations import ConversationService, DuplicateClientMessage
from app.services.inventory import AvailabilityStatus
from app.services.sessions import GuestContext, SessionService


@pytest_asyncio.fixture
async def client_session_and_service() -> AsyncIterator[
    tuple[httpx.AsyncClient, AsyncSession, ConversationService]
]:
    engine = get_database_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        def get_test_session_service() -> SessionService:
            return SessionService(session, get_settings())

        def get_test_conversation_service() -> ConversationService:
            return ConversationService(session)

        app.dependency_overrides[get_session_service] = get_test_session_service
        app.dependency_overrides[get_conversation_service] = get_test_conversation_service
        try:
            await seed_catalog(session)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client, session, ConversationService(session)
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def _guest_context(session: AsyncSession) -> GuestContext:
    guest_session = await session.scalar(select(GuestSession))
    conversation = await session.scalar(select(Conversation))
    assert guest_session is not None
    assert conversation is not None
    return GuestContext(
        guest_session_id=guest_session.id,
        conversation_id=conversation.id,
        expires_at=guest_session.expires_at,
    )


def _product_card(sku: str = "PPE-NIT-M") -> ProductCardPublic:
    return ProductCardPublic(
        sku=sku,
        product_id="PPE-001",
        name="Nitrile Examination Gloves",
        category_code="PPE",
        category_name="Personal Protective Equipment",
        sales_unit="100/box",
        indicative_price_usd=Decimal("11.00"),
        lifecycle_status=CatalogLifecycleStatus.ACTIVE,
        selector_attributes={"size": "medium", "material": "nitrile"},
        primary_image_reference=None,
        image_fallback_key="PH PPE",
        availability=AvailabilityStatus.LIMITED_STOCK,
    )


@pytest.mark.asyncio
async def test_current_history_restores_one_welcome_without_mutating_it(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, session, _service = client_session_and_service

    created = await client.post("/api/v1/sessions")
    first_history = await client.get("/api/v1/conversations/current")
    second_history = await client.get("/api/v1/conversations/current")

    assert created.status_code == 201
    assert first_history.status_code == second_history.status_code == 200
    assert first_history.json() == second_history.json()
    payload = first_history.json()
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["kind"] == "welcome"
    assert payload["messages"][0]["ordinal"] == 0
    assert payload["messages"][0]["freshness"] == "historical_snapshot"
    assert await session.scalar(select(func.count(ConversationMessage.id))) == 1


@pytest.mark.asyncio
async def test_history_returns_stable_order_and_historical_product_snapshot(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, session, service = client_session_and_service
    assert (await client.post("/api/v1/sessions")).status_code == 201
    guest = await _guest_context(session)
    card = _product_card()
    before_inventory = await session.scalar(
        select(InventoryItem.quantity_on_hand)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == card.sku)
    )

    await service.append_user_message(
        guest=guest,
        text="Please show medium nitrile gloves.",
        client_message_id=uuid4(),
    )
    await service.append_assistant_message(
        guest=guest,
        text="Here is a matching historical result.",
        elements=[
            ProductResultsElement(
                kind="product_results",
                result_set=ProductSearchResponse(products=[card], next_cursor=None),
            )
        ],
    )

    history = await client.get("/api/v1/conversations/current")
    after_inventory = await session.scalar(
        select(InventoryItem.quantity_on_hand)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == card.sku)
    )

    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["ordinal"] for message in messages] == [0, 1, 2]
    assert [message["role"] for message in messages] == ["assistant", "user", "assistant"]
    product_snapshot = messages[-1]["elements"][0]["result_set"]["products"][0]
    assert product_snapshot["sku"] == card.sku
    assert product_snapshot["availability"] == "limited_stock"
    assert messages[-1]["freshness"] == "historical_snapshot"
    assert "quantity_on_hand" not in json.dumps(history.json())
    assert before_inventory == after_inventory


@pytest.mark.asyncio
async def test_history_is_cookie_scoped_and_rejects_missing_expired_and_revoked_sessions(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, session, _service = client_session_and_service
    missing = await client.get("/api/v1/conversations/current")
    first = await client.post("/api/v1/sessions")
    own_history = await client.get(
        "/api/v1/conversations/current",
        params={"conversation_id": str(uuid4())},
    )
    guest_session = await session.scalar(select(GuestSession))
    assert guest_session is not None
    guest_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.flush()
    expired = await client.get("/api/v1/conversations/current")
    guest_session.expires_at = datetime.now(UTC) + timedelta(days=7)
    guest_session.revoked_at = datetime.now(UTC)
    await session.flush()
    revoked = await client.get("/api/v1/conversations/current")

    assert missing.status_code == 401
    assert first.status_code == 201
    assert own_history.status_code == 200
    assert own_history.json()["conversation_id"] == first.json()["conversation_id"]
    assert expired.status_code == revoked.status_code == 401


@pytest.mark.asyncio
async def test_malformed_guest_cookie_cannot_retrieve_history(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, _session, _service = client_session_and_service

    response = await client.get(
        "/api/v1/conversations/current",
        headers={"Cookie": "bmh_guest=not-a-valid-opaque-session-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Guest session is missing or invalid."}
    assert "not-a-valid-opaque-session-token" not in response.text


@pytest.mark.asyncio
async def test_second_guest_cannot_select_the_first_guests_history(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    first_client, _session, _service = client_session_and_service
    first_bootstrap = await first_client.post("/api/v1/sessions")
    assert first_bootstrap.status_code == 201

    second_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    try:
        second_bootstrap = await second_client.post("/api/v1/sessions")
        attempted_access = await second_client.get(
            "/api/v1/conversations/current",
            params={"conversation_id": first_bootstrap.json()["conversation_id"]},
        )
    finally:
        await second_client.aclose()

    assert second_bootstrap.status_code == 201
    assert attempted_access.status_code == 200
    assert attempted_access.json()["conversation_id"] == second_bootstrap.json()["conversation_id"]
    assert attempted_access.json()["conversation_id"] != first_bootstrap.json()["conversation_id"]


@pytest.mark.asyncio
async def test_assistant_elements_validate_and_round_trip_without_private_inventory(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, session, service = client_session_and_service
    assert (await client.post("/api/v1/sessions")).status_code == 201
    guest = await _guest_context(session)
    elements = [
        ProductResultsElement(
            kind="product_results",
            result_set=ProductSearchResponse(products=[_product_card()], next_cursor=None),
        ),
        InventoryNoticeElement(
            kind="inventory_notice",
            notice=AvailabilityResponse(
                sku="PPE-NIT-M",
                availability=AvailabilityStatus.LIMITED_STOCK,
                quantity_sufficient=False,
                message="The requested quantity is not currently available.",
            ),
        ),
        QuoteUpdateElement(
            kind="quote_update",
            quote=QuoteUpdateSnapshot(draft_id=uuid4(), version=1),
        ),
        ConfirmationPromptElement(
            kind="confirmation_prompt",
            prompt=ConfirmationPromptSnapshot(
                title="Review quotation",
                message="Confirm after review.",
                confirm_label="Confirm",
            ),
        ),
        SourceReferenceElement(
            kind="source_reference",
            source=SourceReferenceSnapshot(
                source_id="catalog-policy",
                title="Catalog policy",
                excerpt="Synthetic data only.",
            ),
        ),
        SupportInquiryFormElement(
            kind="support_inquiry_form",
            form=SupportInquiryFormSnapshot(
                title="Contact support",
                description="Opt in to request assistance.",
            ),
        ),
    ]
    await service.append_assistant_message(
        guest=guest,
        text="Saved display elements.",
        elements=elements,
    )

    response = await client.get("/api/v1/conversations/current")

    assert response.status_code == 200
    persisted_elements = response.json()["messages"][-1]["elements"]
    assert [element["kind"] for element in persisted_elements] == [
        "product_results",
        "inventory_notice",
        "quote_update",
        "confirmation_prompt",
        "source_reference",
        "support_inquiry_form",
    ]
    assert "quantity_on_hand" not in json.dumps(persisted_elements)


@pytest.mark.asyncio
async def test_product_results_reject_more_than_five_cards(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    _client, _session, _service = client_session_and_service

    with pytest.raises(ValidationError):
        ProductSearchResponse(
            products=[_product_card(f"PPE-NIT-{index}") for index in range(6)], next_cursor=None
        )

    with pytest.raises(ValidationError):
        ProductResultsElement.model_validate(
            {
                "kind": "product_results",
                "result_set": {
                    "products": [
                        _product_card().model_dump() | {"quantity_on_hand": 42},
                    ],
                    "next_cursor": None,
                },
            }
        )


@pytest.mark.asyncio
async def test_invalid_stored_elements_and_schema_versions_fail_safely(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, session, _service = client_session_and_service
    assert (await client.post("/api/v1/sessions")).status_code == 201
    conversation = await session.scalar(select(Conversation))
    assert conversation is not None
    conversation_id = conversation.id
    invalid_element_transaction = await session.begin_nested()
    session.add(
        ConversationMessage(
            conversation_id=conversation_id,
            server_ordinal=1,
            role="assistant",
            message_kind="turn",
            content_json={"text": "Unsafe persisted payload."},
            elements_json=[{"kind": "unknown_element"}],
            element_schema_version=1,
        )
    )
    await session.flush()

    invalid_element = await client.get("/api/v1/conversations/current")
    await invalid_element_transaction.rollback()
    invalid_version_transaction = await session.begin_nested()
    session.add(
        ConversationMessage(
            conversation_id=conversation_id,
            server_ordinal=1,
            role="assistant",
            message_kind="turn",
            content_json={"text": "Unsupported version."},
            elements_json=[],
            element_schema_version=2,
        )
    )
    await session.flush()
    invalid_version = await client.get("/api/v1/conversations/current")
    await invalid_version_transaction.rollback()

    assert invalid_element.status_code == invalid_version.status_code == 500
    assert invalid_element.json()["detail"] == "Conversation history is unavailable."


@pytest.mark.asyncio
async def test_duplicate_client_message_is_rejected_and_ordinals_remain_stable(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, session, service = client_session_and_service
    assert (await client.post("/api/v1/sessions")).status_code == 201
    guest = await _guest_context(session)
    client_message_id = uuid4()
    first = await service.append_user_message(
        guest=guest,
        text="First message.",
        client_message_id=client_message_id,
    )

    with pytest.raises(DuplicateClientMessage):
        await service.append_user_message(
            guest=guest,
            text="Replay must not append.",
            client_message_id=client_message_id,
        )
    history = await client.get("/api/v1/conversations/current")

    assert first.ordinal == 1
    assert [message["ordinal"] for message in history.json()["messages"]] == [0, 1]


@pytest.mark.asyncio
async def test_append_rollback_does_not_leave_a_partial_message(
    client_session_and_service: tuple[httpx.AsyncClient, AsyncSession, ConversationService],
) -> None:
    client, session, service = client_session_and_service
    assert (await client.post("/api/v1/sessions")).status_code == 201
    guest = await _guest_context(session)
    original_flush = session.flush

    async def fail_flush(*_: object, **__: object) -> None:
        raise RuntimeError("forced append failure")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(session, "flush", fail_flush)
    try:
        with pytest.raises(RuntimeError, match="forced append failure"):
            async with session.begin_nested():
                await service.append_user_message(
                    guest=guest,
                    text="This must not persist.",
                    client_message_id=uuid4(),
                )
    finally:
        monkeypatch.setattr(session, "flush", original_flush)
        monkeypatch.undo()

    history = await client.get("/api/v1/conversations/current")

    assert history.status_code == 200
    assert [message["ordinal"] for message in history.json()["messages"]] == [0]


@pytest.mark.asyncio
async def test_concurrent_appends_lock_the_conversation_and_allocate_unique_ordinals() -> None:
    """Use two independent PostgreSQL transactions to exercise the ordinal row lock."""
    engine = get_database_engine()
    async with AsyncSession(engine, expire_on_commit=False) as setup_session:
        bootstrap = await SessionService(setup_session, get_settings()).bootstrap(raw_token=None)

    first_locked = asyncio.Event()
    second_attempting_append = asyncio.Event()
    second_completed = asyncio.Event()
    first_message_id = uuid4()
    second_message_id = uuid4()

    async def append_first() -> None:
        async with AsyncSession(engine, expire_on_commit=False) as first_session:
            async with first_session.begin():
                await first_session.execute(
                    select(Conversation)
                    .where(Conversation.id == bootstrap.context.conversation_id)
                    .with_for_update()
                )
                first_locked.set()
                await asyncio.wait_for(second_attempting_append.wait(), timeout=1)
                await ConversationService(first_session).append_user_message(
                    guest=bootstrap.context,
                    text="First concurrent message.",
                    client_message_id=first_message_id,
                )
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(second_completed.wait(), timeout=0.2)

    async def append_second() -> None:
        await asyncio.wait_for(first_locked.wait(), timeout=1)
        async with AsyncSession(engine, expire_on_commit=False) as second_session:
            async with second_session.begin():
                second_attempting_append.set()
                await ConversationService(second_session).append_user_message(
                    guest=bootstrap.context,
                    text="Second concurrent message.",
                    client_message_id=second_message_id,
                )
        second_completed.set()

    try:
        await asyncio.gather(append_first(), append_second())
        async with AsyncSession(engine, expire_on_commit=False) as verification_session:
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
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as cleanup_session:
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

    assert [message.server_ordinal for message in messages] == [0, 1, 2]
    assert {message.client_message_id for message in messages[1:]} == {
        first_message_id,
        second_message_id,
    }
