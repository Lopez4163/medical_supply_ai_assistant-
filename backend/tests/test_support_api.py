from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sessions import get_session_service
from app.api.v1.support import get_support_inquiry_service
from app.core.settings import get_settings
from app.db.session import get_database_engine, get_session_factory
from app.main import app
from app.models.conversation import Conversation, ConversationMessage, GuestSession
from app.models.quotation import (
    IdempotencyOperation,
    OutboxJob,
    ProtectedReview,
    QuoteDraft,
    QuoteDraftLine,
    QuoteDraftStatus,
    QuoteSubmission,
    QuoteSubmissionLine,
)
from app.models.support import SupportInquiry, SupportReview
from app.schemas.support import SupportInquiryPublic
from app.services.sessions import SessionService
from app.services.support import SupportInquiryService, SupportReviewInvalid


@pytest_asyncio.fixture
async def support_client() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    engine = get_database_engine()
    async with AsyncSession(engine, expire_on_commit=False) as snapshot_session:
        existing_guest_ids = set(await snapshot_session.scalars(select(GuestSession.id)))
    session = AsyncSession(engine, expire_on_commit=False)
    app.dependency_overrides[get_session_service] = lambda: SessionService(session, get_settings())
    app.dependency_overrides[get_support_inquiry_service] = lambda: SupportInquiryService(
        session, get_settings()
    )
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["Origin"] = "http://test"
            yield client, session
    finally:
        app.dependency_overrides.clear()
        await session.close()
        async with AsyncSession(engine, expire_on_commit=False) as cleanup_session:
            created_guest_ids = set(await cleanup_session.scalars(select(GuestSession.id)))
        for guest_session_id in created_guest_ids - existing_guest_ids:
            await _remove_committed_guest(guest_session_id)


async def _bootstrap(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/v1/sessions")).status_code == 201


def _review_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "opt_in": True,
        "reuse_contact": False,
        "contact": {"first_name": "Demo", "last_name": "Guest", "email": "demo@test"},
        "subject": "Need help with a quote",
        "summary": "Please clarify the synthetic quotation process.",
        "conversation_context": "Guest asked about a submitted quotation.",
    }
    payload.update(overrides)
    return payload


async def _review(client: httpx.AsyncClient) -> dict[str, object]:
    response = await client.post("/api/v1/support/review", json=_review_payload())
    assert response.status_code == 200
    return cast(dict[str, object], response.json())


async def _review_guest_id(session: AsyncSession, token: object) -> UUID:
    guest_session_id = await session.scalar(
        select(SupportReview.guest_session_id).where(
            SupportReview.token_hash == hashlib.sha256(str(token).encode()).hexdigest()
        )
    )
    assert guest_session_id is not None
    return guest_session_id


async def _remove_committed_guest(guest_session_id: UUID) -> None:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        draft_ids = list(
            await session.scalars(
                select(QuoteDraft.id).where(QuoteDraft.guest_session_id == guest_session_id)
            )
        )
        if draft_ids:
            submission_ids = list(
                await session.scalars(
                    select(QuoteSubmission.id).where(QuoteSubmission.draft_id.in_(draft_ids))
                )
            )
            if submission_ids:
                await session.execute(
                    delete(OutboxJob).where(OutboxJob.aggregate_id.in_(submission_ids))
                )
                await session.execute(
                    delete(QuoteSubmissionLine).where(
                        QuoteSubmissionLine.submission_id.in_(submission_ids)
                    )
                )
            await session.execute(
                delete(ProtectedReview).where(ProtectedReview.draft_id.in_(draft_ids))
            )
            await session.execute(
                delete(QuoteSubmission).where(QuoteSubmission.draft_id.in_(draft_ids))
            )
            await session.execute(
                delete(QuoteDraftLine).where(QuoteDraftLine.draft_id.in_(draft_ids))
            )
            await session.execute(delete(QuoteDraft).where(QuoteDraft.id.in_(draft_ids)))
        inquiry_ids = list(
            await session.scalars(
                select(SupportInquiry.id).where(SupportInquiry.guest_session_id == guest_session_id)
            )
        )
        if inquiry_ids:
            await session.execute(delete(OutboxJob).where(OutboxJob.aggregate_id.in_(inquiry_ids)))
        await session.execute(
            delete(SupportReview).where(SupportReview.guest_session_id == guest_session_id)
        )
        await session.execute(
            delete(SupportInquiry).where(SupportInquiry.guest_session_id == guest_session_id)
        )
        await session.execute(
            delete(IdempotencyOperation).where(
                IdempotencyOperation.guest_session_id == guest_session_id
            )
        )
        conversation_ids = list(
            await session.scalars(
                select(Conversation.id).where(Conversation.guest_session_id == guest_session_id)
            )
        )
        if conversation_ids:
            await session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.conversation_id.in_(conversation_ids)
                )
            )
        await session.execute(
            delete(Conversation).where(Conversation.guest_session_id == guest_session_id)
        )
        await session.execute(delete(GuestSession).where(GuestSession.id == guest_session_id))


@pytest.mark.asyncio
async def test_review_and_confirmed_submission_persist_immutable_inquiry_and_outbox(
    support_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = support_client
    await _bootstrap(client)
    review = await _review(client)
    operation_id = str(uuid4())
    response = await client.post(
        "/api/v1/support/inquiries",
        json={
            "review_token": review["review_token"],
            "confirmation": True,
            "operation_id": operation_id,
        },
    )
    assert response.status_code == 201
    inquiry = await session.scalar(
        select(SupportInquiry).where(SupportInquiry.reference == response.json()["reference"])
    )
    assert inquiry is not None
    assert inquiry.subject == "Need help with a quote"
    assert inquiry.contact_json["email"] == "demo@test"
    outbox = await session.scalar(select(OutboxJob).where(OutboxJob.aggregate_id == inquiry.id))
    assert outbox is not None and outbox.job_type == "SUPPORT_SHEETS_SYNC"
    assert outbox.aggregate_id == inquiry.id
    assert outbox.payload_json == {
        "reference": inquiry.reference,
        "inquiry": {
            "contact": inquiry.contact_json,
            "subject": inquiry.subject,
            "summary": inquiry.summary,
            "conversation_context": "Guest asked about a submitted quotation.",
        },
    }
    assert "review_token" not in json.dumps(outbox.payload_json)
    assert (
        await client.get(f"/api/v1/support/inquiries/reconcile/{operation_id}")
    ).json() == response.json()


@pytest.mark.asyncio
async def test_invalid_expired_reused_and_cross_session_tokens_cannot_submit(
    support_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = support_client
    await _bootstrap(client)
    invalid = await client.post(
        "/api/v1/support/inquiries",
        json={"review_token": "x" * 32, "confirmation": True, "operation_id": str(uuid4())},
    )
    assert invalid.status_code == 409
    factory = get_session_factory()
    async with factory() as expiry_session:
        bootstrap = await SessionService(expiry_session, get_settings()).bootstrap(raw_token=None)
        expired_guest = bootstrap.context
        review = await SupportInquiryService(expiry_session, get_settings()).review(
            guest=expired_guest,
            opt_in=True,
            reuse_contact=False,
            contact={"first_name": "Demo", "last_name": "Guest", "email": "demo@test"},
            subject="Need help with a quote",
            summary="Please clarify the synthetic quotation process.",
            conversation_context=None,
        )
    try:
        token_hash = hashlib.sha256(review.review_token.encode()).hexdigest()
        async with factory() as expiry_session, expiry_session.begin():
            await expiry_session.execute(
                update(SupportReview)
                .where(SupportReview.token_hash == token_hash)
                .values(expires_at=datetime(2000, 1, 1, tzinfo=UTC))
            )
        async with factory() as expiry_session:
            with pytest.raises(SupportReviewInvalid):
                await SupportInquiryService(expiry_session, get_settings()).submit(
                    guest=expired_guest, review_token=review.review_token, operation_id=uuid4()
                )
    finally:
        await _remove_committed_guest(expired_guest.guest_session_id)


@pytest.mark.asyncio
async def test_reused_token_and_cross_session_token_are_rejected_without_side_effects(
    support_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = support_client
    await _bootstrap(client)
    review = await _review(client)
    factory = get_session_factory()
    async with factory() as second_session:
        second = await SessionService(second_session, get_settings()).bootstrap(raw_token=None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as second_client:
        second_client.headers["Origin"] = "http://test"
        second_client.cookies.set(get_settings().guest_session_cookie_name, second.raw_token)
        cross_session = await second_client.post(
            "/api/v1/support/inquiries",
            json={
                "review_token": review["review_token"],
                "confirmation": True,
                "operation_id": str(uuid4()),
            },
        )
    assert cross_session.status_code == 409
    first = await client.post(
        "/api/v1/support/inquiries",
        json={
            "review_token": review["review_token"],
            "confirmation": True,
            "operation_id": str(uuid4()),
        },
    )
    assert first.status_code == 201
    reused = await client.post(
        "/api/v1/support/inquiries",
        json={
            "review_token": review["review_token"],
            "confirmation": True,
            "operation_id": str(uuid4()),
        },
    )
    assert reused.status_code == 409
    assert (
        await session.scalar(
            select(func.count())
            .select_from(SupportInquiry)
            .where(SupportInquiry.reference == first.json()["reference"])
        )
        == 1
    )


@pytest.mark.asyncio
async def test_contact_reuse_requires_explicit_consent_and_missing_contact_is_rejected(
    support_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = support_client
    await _bootstrap(client)
    guest_session = await session.scalar(
        select(GuestSession).order_by(GuestSession.created_at.desc())
    )
    assert guest_session is not None
    draft = QuoteDraft(
        guest_session_id=guest_session.id,
        status=QuoteDraftStatus.SUBMITTED,
        version=1,
    )
    session.add(draft)
    await session.flush()
    session.add(
        QuoteSubmission(
            reference=f"Q-{uuid4().hex[:12].upper()}",
            guest_session_id=guest_session.id,
            draft_id=draft.id,
            operation_id=uuid4(),
            snapshot_json={
                "contact": {
                    "first_name": "Quote",
                    "last_name": "Contact",
                    "email": "quote-contact@test",
                    "phone": None,
                }
            },
        )
    )
    await session.commit()
    no_contact = await client.post(
        "/api/v1/support/review",
        json=_review_payload(contact=None),
    )
    assert no_contact.status_code == 422
    unavailable_reuse = await client.post(
        "/api/v1/support/review",
        json=_review_payload(reuse_contact=True, contact=None),
    )
    assert unavailable_reuse.status_code == 200
    reused_review = await session.scalar(
        select(SupportReview).where(
            SupportReview.token_hash
            == hashlib.sha256(str(unavailable_reuse.json()["review_token"]).encode()).hexdigest()
        )
    )
    assert reused_review is not None
    reused_contact = cast(dict[str, object], reused_review.content_json["contact"])
    assert reused_contact["email"] == "quote-contact@test"
    factory = get_session_factory()
    async with factory() as second_session:
        second = await SessionService(second_session, get_settings()).bootstrap(raw_token=None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as second_client:
        second_client.headers["Origin"] = "http://test"
        second_client.cookies.set(get_settings().guest_session_cookie_name, second.raw_token)
        cross_session_reuse = await second_client.post(
            "/api/v1/support/review",
            json=_review_payload(reuse_contact=True, contact=None),
        )
    assert cross_session_reuse.status_code == 422
    reused = await client.post(
        "/api/v1/support/review",
        json=_review_payload(reuse_contact=True, contact=None),
    )
    assert reused.status_code == 200
    assert (
        await session.scalar(
            select(func.count())
            .select_from(SupportInquiry)
            .where(SupportInquiry.guest_session_id == guest_session.id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_declined_confirmation_and_cross_origin_leave_inquiry_and_draft_unchanged(
    support_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = support_client
    await _bootstrap(client)
    guest_session = await session.scalar(
        select(GuestSession).order_by(GuestSession.created_at.desc())
    )
    assert guest_session is not None
    draft = QuoteDraft(guest_session_id=guest_session.id)
    session.add(draft)
    await session.commit()
    conversation = await session.scalar(
        select(Conversation).where(Conversation.guest_session_id == guest_session.id)
    )
    assert conversation is not None
    before_messages = await session.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
    )
    review = await _review(client)
    before_inquiries = await session.scalar(
        select(func.count())
        .select_from(SupportInquiry)
        .where(SupportInquiry.guest_session_id == guest_session.id)
    )
    before_outbox = await session.scalar(
        select(func.count())
        .select_from(OutboxJob)
        .where(OutboxJob.job_type == "SUPPORT_SHEETS_SYNC")
    )
    declined = await client.post(
        "/api/v1/support/inquiries",
        json={
            "review_token": review["review_token"],
            "confirmation": False,
            "operation_id": str(uuid4()),
        },
    )
    assert declined.status_code == 422
    cross_origin = await client.post(
        "/api/v1/support/review",
        json=_review_payload(),
        headers={"Origin": "https://bad.test"},
    )
    assert cross_origin.status_code == 403
    assert (
        await session.scalar(
            select(func.count())
            .select_from(SupportInquiry)
            .where(SupportInquiry.guest_session_id == guest_session.id)
        )
        == before_inquiries
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(OutboxJob)
            .where(OutboxJob.job_type == "SUPPORT_SHEETS_SYNC")
        )
        == before_outbox
    )
    unchanged_draft = await session.get(QuoteDraft, draft.id)
    assert unchanged_draft is not None and unchanged_draft.status == QuoteDraftStatus.ACTIVE
    assert (
        await session.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
        )
        == before_messages
    )


@pytest.mark.asyncio
async def test_identical_replay_conflict_and_reconciliation_are_safe(
    support_client: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = support_client
    await _bootstrap(client)
    review = await _review(client)
    operation_id = str(uuid4())
    payload = {
        "review_token": review["review_token"],
        "confirmation": True,
        "operation_id": operation_id,
    }
    first = await client.post("/api/v1/support/inquiries", json=payload)
    replay = await client.post("/api/v1/support/inquiries", json=payload)
    conflict = await client.post(
        "/api/v1/support/inquiries", json={**payload, "review_token": "y" * 32}
    )
    assert first.status_code == 201
    assert replay.status_code == 200 and replay.json() == first.json()
    assert conflict.status_code == 409
    assert (
        await client.get(f"/api/v1/support/inquiries/reconcile/{operation_id}")
    ).json() == first.json()
    assert (
        await session.scalar(
            select(func.count())
            .select_from(SupportInquiry)
            .where(SupportInquiry.reference == first.json()["reference"])
        )
        == 1
    )


@pytest.mark.asyncio
async def test_independent_transactions_create_one_inquiry_and_outbox() -> None:
    factory = get_session_factory()
    async with factory() as session:
        bootstrap = await SessionService(session, get_settings()).bootstrap(raw_token=None)
        guest = bootstrap.context
        review = await SupportInquiryService(session, get_settings()).review(
            guest=guest,
            opt_in=True,
            reuse_contact=False,
            contact={"first_name": "Demo", "last_name": "Guest", "email": "demo@test"},
            subject="Need help with a quote",
            summary="Please clarify the synthetic quotation process.",
            conversation_context="Guest asked about a submitted quotation.",
        )
    barrier = asyncio.Barrier(2)
    operation_id = uuid4()

    async def submit() -> object:
        async with factory() as session:
            await barrier.wait()
            return await SupportInquiryService(session, get_settings()).submit(
                guest=guest, review_token=review.review_token, operation_id=operation_id
            )

    try:
        results = await asyncio.gather(submit(), submit(), return_exceptions=True)
        assert all(not isinstance(result, Exception) for result in results)
        assert results[0] == results[1]
        async with factory() as session:
            inquiry_ids = list(
                await session.scalars(
                    select(SupportInquiry.id).where(
                        SupportInquiry.guest_session_id == guest.guest_session_id
                    )
                )
            )
            assert len(inquiry_ids) == 1
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(OutboxJob)
                    .where(OutboxJob.aggregate_id.in_(inquiry_ids))
                )
                == 1
            )
    finally:
        await _remove_committed_guest(guest.guest_session_id)


@pytest.mark.asyncio
async def test_post_outbox_failure_rolls_back_inquiry_and_outbox_then_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = get_session_factory()
    async with factory() as session:
        bootstrap = await SessionService(session, get_settings()).bootstrap(raw_token=None)
        guest = bootstrap.context
        review = await SupportInquiryService(session, get_settings()).review(
            guest=guest,
            opt_in=True,
            reuse_contact=False,
            contact={"first_name": "Demo", "last_name": "Guest", "email": "demo@test"},
            subject="Need help with a quote",
            summary="Please clarify the synthetic quotation process.",
            conversation_context="Guest asked about a submitted quotation.",
        )
    operation_id = uuid4()
    failed_reference: str | None = None
    async with factory() as session:
        service = SupportInquiryService(session, get_settings())

        def fail_after_outbox(**values: object) -> None:
            nonlocal failed_reference
            result = values["result"]
            assert isinstance(result, SupportInquiryPublic)
            failed_reference = result.reference
            raise RuntimeError("forced failure")

        monkeypatch.setattr(
            service,
            "_store_operation",
            fail_after_outbox,
        )
        with pytest.raises(RuntimeError, match="forced failure"):
            await service.submit(
                guest=guest, review_token=review.review_token, operation_id=operation_id
            )
    try:
        async with factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(SupportInquiry)
                    .where(SupportInquiry.guest_session_id == guest.guest_session_id)
                )
                == 0
            )
            assert failed_reference is not None
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(OutboxJob)
                    .where(
                        OutboxJob.job_type == "SUPPORT_SHEETS_SYNC",
                        OutboxJob.reference == failed_reference,
                    )
                )
                == 0
            )
            result = await SupportInquiryService(session, get_settings()).submit(
                guest=guest, review_token=review.review_token, operation_id=operation_id
            )
            assert result.reference.startswith("S-")
            inquiry_ids = list(
                await session.scalars(
                    select(SupportInquiry.id).where(
                        SupportInquiry.guest_session_id == guest.guest_session_id
                    )
                )
            )
            assert len(inquiry_ids) == 1
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(OutboxJob)
                    .where(
                        OutboxJob.job_type == "SUPPORT_SHEETS_SYNC",
                        OutboxJob.aggregate_id == inquiry_ids[0],
                    )
                )
                == 1
            )
    finally:
        await _remove_committed_guest(guest.guest_session_id)
