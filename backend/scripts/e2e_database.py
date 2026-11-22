"""Prepare and narrowly clean the isolated database used by browser integration tests."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.dev.seed_catalog import seed_catalog
from app.models.conversation import Conversation, ConversationMessage, GuestSession
from app.models.quotation import (
    IdempotencyOperation,
    OutboxJob,
    ProtectedReview,
    QuoteDraft,
    QuoteDraftLine,
    QuoteSubmission,
    QuoteSubmissionLine,
)
from app.models.support import SupportInquiry, SupportReview


def test_database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    try:
        database_name = make_url(value).database if value else None
    except ArgumentError, TypeError, ValueError:
        database_name = None
    if database_name != "medical_supply_test":
        raise SystemExit("TEST_DATABASE_URL must target the isolated medical_supply_test database.")
    assert value is not None
    return value


async def prepare(database_url: str) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory.begin() as session:
            await seed_catalog(session)
    finally:
        await engine.dispose()


async def cleanup(database_url: str, created_since: datetime) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory.begin() as session:
            await cleanup_sessions(session, created_since)
    finally:
        await engine.dispose()


async def cleanup_sessions(session: AsyncSession, created_since: datetime) -> None:
    """Delete only guest aggregates created during this browser run, in FK-safe order."""
    result = await session.scalars(
        select(GuestSession.id).where(GuestSession.created_at >= created_since)
    )
    session_ids = list(result)
    if not session_ids:
        return

    result = await session.scalars(
        select(Conversation.id).where(Conversation.guest_session_id.in_(session_ids))
    )
    conversation_ids = list(result)
    result = await session.scalars(
        select(QuoteDraft.id).where(QuoteDraft.guest_session_id.in_(session_ids))
    )
    draft_ids = list(result)
    result = await session.scalars(
        select(QuoteSubmission.id).where(QuoteSubmission.guest_session_id.in_(session_ids))
    )
    quote_submission_ids = list(result)
    result = await session.scalars(
        select(SupportInquiry.id).where(SupportInquiry.guest_session_id.in_(session_ids))
    )
    support_inquiry_ids = list(result)

    aggregate_ids = [*quote_submission_ids, *support_inquiry_ids]
    if aggregate_ids:
        await session.execute(delete(OutboxJob).where(OutboxJob.aggregate_id.in_(aggregate_ids)))
    if quote_submission_ids:
        await session.execute(
            delete(QuoteSubmissionLine).where(
                QuoteSubmissionLine.submission_id.in_(quote_submission_ids)
            )
        )
    await session.execute(
        delete(ProtectedReview).where(ProtectedReview.guest_session_id.in_(session_ids))
    )
    await session.execute(
        delete(SupportReview).where(SupportReview.guest_session_id.in_(session_ids))
    )
    await session.execute(
        delete(IdempotencyOperation).where(IdempotencyOperation.guest_session_id.in_(session_ids))
    )
    if conversation_ids:
        await session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.conversation_id.in_(conversation_ids)
            )
        )
    await session.execute(
        delete(SupportInquiry).where(SupportInquiry.guest_session_id.in_(session_ids))
    )
    await session.execute(
        delete(QuoteSubmission).where(QuoteSubmission.guest_session_id.in_(session_ids))
    )
    if draft_ids:
        await session.execute(delete(QuoteDraftLine).where(QuoteDraftLine.draft_id.in_(draft_ids)))
    await session.execute(delete(QuoteDraft).where(QuoteDraft.guest_session_id.in_(session_ids)))
    await session.execute(
        delete(Conversation).where(Conversation.guest_session_id.in_(session_ids))
    )
    await session.execute(delete(GuestSession).where(GuestSession.id.in_(session_ids)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "prepare", "cleanup"))
    parser.add_argument("--created-since")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = test_database_url()
    if args.command == "validate":
        return
    if args.command == "prepare":
        asyncio.run(prepare(database_url))
        return
    if args.created_since is None:
        raise SystemExit("--created-since is required for cleanup.")
    asyncio.run(cleanup(database_url, datetime.fromisoformat(args.created_since)))


if __name__ == "__main__":
    main()
