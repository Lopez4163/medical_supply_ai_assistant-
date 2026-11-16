from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.quotations import get_quotation_service
from app.api.v1.sessions import get_session_service
from app.core.settings import get_settings
from app.db.session import get_database_engine, get_session_factory
from app.dev.seed_catalog import seed_catalog
from app.main import app
from app.models.catalog import (
    InventoryItem,
    ProductCategory,
    ProductListing,
    SkuCompatibility,
    SkuVariant,
)
from app.models.conversation import Conversation, ConversationMessage, GuestSession
from app.models.quotation import (
    IdempotencyOperation,
    IdempotencyOperationStatus,
    QuoteDraft,
    QuoteDraftLine,
)
from app.schemas.quotations import DraftQuotePublic
from app.services.quotations import QuotationService, QuoteSessionInvalid, QuoteVersionConflict
from app.services.sessions import GuestContext, SessionService


@pytest_asyncio.fixture
async def quote_client() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    engine = get_database_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        def session_service() -> SessionService:
            return SessionService(session, get_settings())

        def quotation_service() -> QuotationService:
            return QuotationService(session, get_settings())

        app.dependency_overrides[get_session_service] = session_service
        app.dependency_overrides[get_quotation_service] = quotation_service
        try:
            await seed_catalog(session)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                client.headers["Origin"] = "http://test"
                yield client, session
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def _bootstrap(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/sessions")
    assert response.status_code == 201


def _add_payload(
    *, quantity: int = 2, version: int = 0, operation_id: str | None = None
) -> dict[str, object]:
    return {
        "sku": "PPE-NIT-M",
        "quantity": quantity,
        "expected_version": version,
        "operation_id": operation_id or str(uuid4()),
    }


async def _committed_guest() -> GuestContext:
    factory = get_session_factory()
    async with factory() as session:
        await seed_catalog(session)
        bootstrap = await SessionService(session, get_settings()).bootstrap(raw_token=None)
        return bootstrap.context


async def _remove_committed_guest(guest: GuestContext) -> None:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        draft_ids = list(
            await session.scalars(
                select(QuoteDraft.id).where(QuoteDraft.guest_session_id == guest.guest_session_id)
            )
        )
        if draft_ids:
            await session.execute(
                delete(QuoteDraftLine).where(QuoteDraftLine.draft_id.in_(draft_ids))
            )
            await session.execute(delete(QuoteDraft).where(QuoteDraft.id.in_(draft_ids)))
        await session.execute(
            delete(IdempotencyOperation).where(
                IdempotencyOperation.guest_session_id == guest.guest_session_id
            )
        )
        await session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.conversation_id == guest.conversation_id
            )
        )
        await session.execute(delete(Conversation).where(Conversation.id == guest.conversation_id))
        await session.execute(delete(GuestSession).where(GuestSession.id == guest.guest_session_id))
        # The concurrency fixture commits the deterministic catalog so independent
        # connections can see it; return the otherwise isolated test database to empty.
        await session.execute(delete(SkuCompatibility))
        await session.execute(delete(InventoryItem))
        await session.execute(delete(SkuVariant))
        await session.execute(delete(ProductListing))
        await session.execute(delete(ProductCategory))


async def _concurrently(
    guest: GuestContext,
    *operations: tuple[str, object],
) -> list[object]:
    barrier = asyncio.Barrier(len(operations))
    factory = get_session_factory()

    async def invoke(name: str, payload: object) -> object:
        async with factory() as session:
            service = QuotationService(session, get_settings())
            await barrier.wait()
            values = cast(dict[str, object], payload)
            if name == "add":
                return await service.add_line(
                    guest=guest,
                    sku=cast(str, values["sku"]),
                    quantity=cast(int, values["quantity"]),
                    expected_version=cast(int, values["expected_version"]),
                    operation_id=cast(UUID, values["operation_id"]),
                )
            if name == "update":
                return await service.update_line(
                    guest=guest,
                    line_id=cast(UUID, values["line_id"]),
                    quantity=cast(int, values["quantity"]),
                    mode=cast(Literal["replace", "increment"], values["mode"]),
                    expected_version=cast(int, values["expected_version"]),
                    operation_id=cast(UUID, values["operation_id"]),
                )
            return await service.remove_line(
                guest=guest,
                line_id=cast(UUID, values["line_id"]),
                expected_version=cast(int, values["expected_version"]),
                operation_id=cast(UUID, values["operation_id"]),
            )

    return list(
        await asyncio.gather(
            *(invoke(name, payload) for name, payload in operations), return_exceptions=True
        )
    )


@pytest.mark.asyncio
async def test_draft_lifecycle_merges_updates_removes_and_keeps_inventory_unchanged(
    quote_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = quote_client
    await _bootstrap(client)
    assert (await client.get("/api/v1/quotations/draft")).json() == {"draft": None}
    inventory_before = await session.scalar(
        select(InventoryItem.quantity_on_hand)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == "PPE-NIT-M")
    )

    added = await client.post("/api/v1/quotations/draft/lines", json=_add_payload())
    assert added.status_code == 200
    draft = added.json()
    assert draft["version"] == 1
    assert draft["lines"][0]["requested_quantity"] == 2
    assert Decimal(draft["indicative_total_usd"]) == Decimal("22.00")
    assert draft["lines"][0]["availability"] == "limited_stock"
    line_id = draft["lines"][0]["id"]

    merged = await client.post(
        "/api/v1/quotations/draft/lines", json=_add_payload(quantity=3, version=1)
    )
    assert merged.status_code == 200
    assert merged.json()["lines"][0]["requested_quantity"] == 5
    replaced = await client.patch(
        f"/api/v1/quotations/draft/lines/{line_id}",
        json={
            "quantity": 4,
            "mode": "replace",
            "expected_version": 2,
            "operation_id": str(uuid4()),
        },
    )
    assert replaced.json()["lines"][0]["requested_quantity"] == 4
    incremented = await client.patch(
        f"/api/v1/quotations/draft/lines/{line_id}",
        json={
            "quantity": 2,
            "mode": "increment",
            "expected_version": 3,
            "operation_id": str(uuid4()),
        },
    )
    assert incremented.json()["lines"][0]["requested_quantity"] == 6
    deleted = await client.request(
        "DELETE",
        f"/api/v1/quotations/draft/lines/{line_id}",
        json={"expected_version": 4, "operation_id": str(uuid4())},
    )
    assert deleted.status_code == 200
    assert deleted.json()["version"] == 5
    assert deleted.json()["lines"] == []
    assert (
        await session.scalar(
            select(InventoryItem.quantity_on_hand)
            .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
            .where(SkuVariant.sku == "PPE-NIT-M")
        )
        == inventory_before
    )


@pytest.mark.asyncio
async def test_idempotent_retry_returns_committed_snapshot_without_double_increment(
    quote_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = quote_client
    await _bootstrap(client)
    operation_id = str(uuid4())
    payload = _add_payload(quantity=3, operation_id=operation_id)
    first = await client.post("/api/v1/quotations/draft/lines", json=payload)
    second = await client.post("/api/v1/quotations/draft/lines", json=payload)
    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    line = await session.scalar(select(QuoteDraftLine))
    assert line is not None and line.quantity == 3
    assert await session.scalar(select(IdempotencyOperation)) is not None


@pytest.mark.asyncio
async def test_conflicts_cross_session_access_and_bad_quantities_are_rejected(
    quote_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = quote_client
    await _bootstrap(client)
    created = await client.post("/api/v1/quotations/draft/lines", json=_add_payload())
    assert created.status_code == 200
    stale = await client.post("/api/v1/quotations/draft/lines", json=_add_payload(version=0))
    assert stale.status_code == 409
    mismatch_id = str(uuid4())
    assert (
        await client.post(
            "/api/v1/quotations/draft/lines", json=_add_payload(version=1, operation_id=mismatch_id)
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/quotations/draft/lines",
            json=_add_payload(quantity=3, version=1, operation_id=mismatch_id),
        )
    ).status_code == 409
    for quantity in [0, -1, 1.5, True, "2"]:
        response = await client.post(
            "/api/v1/quotations/draft/lines", json=_add_payload(quantity=quantity)
        )
        assert response.status_code == 422

    unknown_line = await client.patch(
        f"/api/v1/quotations/draft/lines/{uuid4()}",
        json={
            "quantity": 1,
            "mode": "replace",
            "expected_version": 2,
            "operation_id": str(uuid4()),
        },
    )
    assert unknown_line.status_code == 404
    assert await session.scalar(select(QuoteDraft)) is not None


@pytest.mark.asyncio
async def test_out_of_stock_item_remains_a_warning_line(
    quote_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = quote_client
    await _bootstrap(client)
    response = await client.post(
        "/api/v1/quotations/draft/lines",
        json={
            "sku": "CON-UNDER-10",
            "quantity": 1,
            "expected_version": 0,
            "operation_id": str(uuid4()),
        },
    )
    assert response.status_code == 200
    line = response.json()["lines"][0]
    assert line["availability"] == "out_of_stock"
    assert line["quantity_sufficient"] is False
    assert "out of stock" in line["availability_notice"].lower()


@pytest.mark.asyncio
async def test_mutations_require_one_configured_origin_and_return_a_version_code(
    quote_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = quote_client
    await _bootstrap(client)
    payload = _add_payload()
    for headers in (
        {"Origin": "https://attacker.test"},
        {"Origin": "not-an-origin"},
        [("Origin", "http://test"), ("Origin", "https://attacker.test")],
    ):
        response = await client.post(
            "/api/v1/quotations/draft/lines", json=payload, headers=headers
        )
        assert response.status_code == 403
    client.headers.pop("Origin")
    assert (await client.post("/api/v1/quotations/draft/lines", json=payload)).status_code == 403
    client.headers["Origin"] = "http://test"
    assert (await client.post("/api/v1/quotations/draft/lines", json=payload)).status_code == 200
    conflict = await client.post("/api/v1/quotations/draft/lines", json=_add_payload(version=0))
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "QUOTE_VERSION_CONFLICT"


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", [0, -1, True, 1.5, "2", None])
async def test_service_rejects_invalid_runtime_quantities_before_mutation(
    quote_client: tuple[httpx.AsyncClient, AsyncSession], quantity: object
) -> None:
    client, session = quote_client
    await _bootstrap(client)
    assert await session.scalar(select(QuoteDraft)) is None
    session_row = await session.scalar(select(GuestSession))
    conversation_row = await session.scalar(select(Conversation))
    assert session_row is not None and conversation_row is not None
    service = QuotationService(session, get_settings())
    with pytest.raises(ValueError):
        await service.add_line(
            guest=GuestContext(session_row.id, conversation_row.id, session_row.expires_at),
            sku="PPE-NIT-M",
            quantity=cast(int, quantity),
            expected_version=0,
            operation_id=uuid4(),
        )
    assert await session.scalar(select(QuoteDraft)) is None


@pytest.mark.asyncio
async def test_mutation_rechecks_a_revoked_guest_under_its_row_lock(
    quote_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = quote_client
    await _bootstrap(client)
    guest_session = await session.scalar(select(GuestSession))
    conversation = await session.scalar(select(Conversation))
    assert guest_session is not None and conversation is not None
    guest = GuestContext(guest_session.id, conversation.id, guest_session.expires_at)
    guest_session.revoked_at = datetime.now(UTC)
    await session.flush()
    with pytest.raises(QuoteSessionInvalid):
        await QuotationService(session, get_settings()).add_line(
            guest=guest, sku="PPE-NIT-M", quantity=1, expected_version=0, operation_id=uuid4()
        )
    assert await session.scalar(select(QuoteDraft)) is None


@pytest.mark.asyncio
async def test_independent_postgresql_sessions_serialize_mutations() -> None:
    guest = await _committed_guest()
    try:
        first = await _concurrently(
            guest,
            (
                "add",
                {"sku": "PPE-NIT-M", "quantity": 2, "expected_version": 0, "operation_id": uuid4()},
            ),
            (
                "add",
                {"sku": "PPE-NIT-M", "quantity": 3, "expected_version": 0, "operation_id": uuid4()},
            ),
        )
        assert sum(not isinstance(result, Exception) for result in first) == 1
        assert sum(isinstance(result, QuoteVersionConflict) for result in first) == 1

        factory = get_session_factory()
        async with factory() as session:
            draft = await session.scalar(
                select(QuoteDraft).where(QuoteDraft.guest_session_id == guest.guest_session_id)
            )
            line = await session.scalar(select(QuoteDraftLine))
            assert draft is not None and line is not None
            assert draft.version == 1 and line.quantity in {2, 3}
            line_id = line.id

        updates = await _concurrently(
            guest,
            (
                "update",
                {
                    "line_id": line_id,
                    "quantity": 7,
                    "mode": "replace",
                    "expected_version": 1,
                    "operation_id": uuid4(),
                },
            ),
            (
                "update",
                {
                    "line_id": line_id,
                    "quantity": 9,
                    "mode": "replace",
                    "expected_version": 1,
                    "operation_id": uuid4(),
                },
            ),
        )
        assert sum(not isinstance(result, Exception) for result in updates) == 1
        assert sum(isinstance(result, QuoteVersionConflict) for result in updates) == 1

        duplicate_id = uuid4()
        duplicate = await _concurrently(
            guest,
            (
                "add",
                {
                    "sku": "CON-UNDER-10",
                    "quantity": 1,
                    "expected_version": 2,
                    "operation_id": duplicate_id,
                },
            ),
            (
                "add",
                {
                    "sku": "CON-UNDER-10",
                    "quantity": 1,
                    "expected_version": 2,
                    "operation_id": duplicate_id,
                },
            ),
        )
        assert all(not isinstance(result, Exception) for result in duplicate)
        assert duplicate[0] == duplicate[1]
        async with factory() as session:
            assert (
                await session.scalar(
                    select(func.count(QuoteDraft.id)).where(
                        QuoteDraft.guest_session_id == guest.guest_session_id
                    )
                )
                == 1
            )
            lines = list(await session.scalars(select(QuoteDraftLine)))
            assert len(lines) == 2
            assert sum(line.quantity for line in lines if line.sku_variant_id) >= 1
    finally:
        await _remove_committed_guest(guest)


@pytest.mark.asyncio
async def test_independent_postgresql_add_remove_interleaving_is_explicit() -> None:
    guest = await _committed_guest()
    factory = get_session_factory()
    try:
        async with factory() as session:
            created = await QuotationService(session, get_settings()).add_line(
                guest=guest, sku="PPE-NIT-M", quantity=1, expected_version=0, operation_id=uuid4()
            )
            line_id = created.lines[0].id
        outcomes = await _concurrently(
            guest,
            (
                "add",
                {
                    "sku": "CON-UNDER-10",
                    "quantity": 1,
                    "expected_version": 1,
                    "operation_id": uuid4(),
                },
            ),
            ("remove", {"line_id": line_id, "expected_version": 1, "operation_id": uuid4()}),
        )
        assert sum(not isinstance(result, Exception) for result in outcomes) == 1
        assert sum(isinstance(result, QuoteVersionConflict) for result in outcomes) == 1
        async with factory() as session:
            draft = await session.scalar(
                select(QuoteDraft).where(QuoteDraft.guest_session_id == guest.guest_session_id)
            )
            assert draft is not None and draft.version == 2
            remaining_lines = list(
                await session.scalars(
                    select(QuoteDraftLine).where(QuoteDraftLine.draft_id == draft.id)
                )
            )
            assert len(remaining_lines) in {0, 1}
            if remaining_lines:
                variant = await session.scalar(
                    select(SkuVariant).where(SkuVariant.id == remaining_lines[0].sku_variant_id)
                )
                assert variant is not None and variant.sku == "CON-UNDER-10"
    finally:
        await _remove_committed_guest(guest)


@pytest.mark.asyncio
async def test_mutation_rollback_does_not_persist_an_operation_or_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guest = await _committed_guest()
    operation_id = uuid4()
    factory = get_session_factory()

    async def fail_projection(_: QuoteDraft) -> DraftQuotePublic:
        raise RuntimeError("forced projection failure")

    try:
        async with factory() as failed_session:
            failed_service = QuotationService(failed_session, get_settings())
            monkeypatch.setattr(failed_service, "_project_draft", fail_projection)
            with pytest.raises(RuntimeError, match="forced projection failure"):
                await failed_service.add_line(
                    guest=guest,
                    sku="PPE-NIT-M",
                    quantity=2,
                    expected_version=0,
                    operation_id=operation_id,
                )

        async with factory() as verification_session:
            assert (
                await verification_session.scalar(
                    select(QuoteDraft).where(QuoteDraft.guest_session_id == guest.guest_session_id)
                )
                is None
            )
            assert (
                await verification_session.scalar(select(func.count()).select_from(QuoteDraftLine))
                == 0
            )
            assert (
                await verification_session.scalar(
                    select(IdempotencyOperation).where(
                        IdempotencyOperation.guest_session_id == guest.guest_session_id,
                        IdempotencyOperation.operation_id == operation_id,
                    )
                )
                is None
            )

        async with factory() as retry_session:
            committed = await QuotationService(retry_session, get_settings()).add_line(
                guest=guest,
                sku="PPE-NIT-M",
                quantity=2,
                expected_version=0,
                operation_id=operation_id,
            )
            assert committed.version == 1
            assert committed.lines[0].requested_quantity == 2

        async with factory() as replay_session:
            replayed = await QuotationService(replay_session, get_settings()).add_line(
                guest=guest,
                sku="PPE-NIT-M",
                quantity=2,
                expected_version=0,
                operation_id=operation_id,
            )
            assert replayed == committed

        async with factory() as verification_session:
            drafts = list(
                await verification_session.scalars(
                    select(QuoteDraft).where(QuoteDraft.guest_session_id == guest.guest_session_id)
                )
            )
            assert len(drafts) == 1
            lines = list(
                await verification_session.scalars(
                    select(QuoteDraftLine).where(QuoteDraftLine.draft_id == drafts[0].id)
                )
            )
            operations = list(
                await verification_session.scalars(
                    select(IdempotencyOperation).where(
                        IdempotencyOperation.guest_session_id == guest.guest_session_id,
                        IdempotencyOperation.operation_id == operation_id,
                    )
                )
            )
            assert drafts[0].version == 1
            assert len(lines) == 1 and lines[0].quantity == 2
            variant = await verification_session.scalar(
                select(SkuVariant).where(SkuVariant.id == lines[0].sku_variant_id)
            )
            assert variant is not None and variant.sku == "PPE-NIT-M"
            assert len(operations) == 1
            assert operations[0].status == IdempotencyOperationStatus.COMMITTED
    finally:
        await _remove_committed_guest(guest)
