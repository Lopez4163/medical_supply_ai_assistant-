"""Deterministic protected workflow for synthetic support inquiries."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.models.quotation import IdempotencyOperation, OutboxJob, QuoteSubmission
from app.models.support import SupportInquiry, SupportReview
from app.schemas.support import SupportInquiryPublic, SupportReviewPublic
from app.services.sessions import GuestContext, InvalidGuestSession, SessionService


class SupportReviewInvalid(Exception):
    pass


class SupportSessionInvalid(Exception):
    pass


class SupportIdempotencyPayloadMismatch(Exception):
    pass


class SupportContactUnavailable(Exception):
    pass


class SupportInquiryService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._last_submission_was_replay = False

    @property
    def last_submission_was_replay(self) -> bool:
        return self._last_submission_was_replay

    async def review(
        self,
        *,
        guest: GuestContext,
        opt_in: bool,
        reuse_contact: bool,
        contact: dict[str, object] | None,
        subject: str,
        summary: str,
        conversation_context: str | None,
    ) -> SupportReviewPublic:
        if not opt_in:
            raise ValueError("Explicit support-inquiry opt-in is required.")
        async with self._mutation_transaction():
            await self._renew_and_lock_guest(guest=guest)
            resolved_contact = (
                await self._previous_contact(guest=guest) if reuse_contact else contact
            )
            if resolved_contact is None:
                raise SupportContactUnavailable
            content = {
                "contact": resolved_contact,
                "subject": subject,
                "summary": summary,
                "conversation_context": conversation_context,
            }
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(minutes=15)
            self._session.add(
                SupportReview(
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    guest_session_id=guest.guest_session_id,
                    content_digest=self._fingerprint("support_review", content),
                    content_json=content,
                    expires_at=expires_at,
                )
            )
            return SupportReviewPublic(
                review_token=token,
                expires_at=expires_at,
                subject=subject,
                summary=summary,
                disclosure=(
                    "This synthetic support inquiry does not notify real staff or promise "
                    "a response."
                ),
            )

    async def submit(
        self, *, guest: GuestContext, review_token: str, operation_id: UUID
    ) -> SupportInquiryPublic:
        self._last_submission_was_replay = False
        fingerprint = self._fingerprint("submit_support", {"review_token": review_token})
        async with self._mutation_transaction():
            await self._renew_and_lock_guest(guest=guest)
            operation = await self._session.scalar(
                select(IdempotencyOperation)
                .where(
                    IdempotencyOperation.guest_session_id == guest.guest_session_id,
                    IdempotencyOperation.operation_id == operation_id,
                )
                .with_for_update()
            )
            if operation is not None:
                if (
                    operation.operation_kind != "submit_support"
                    or operation.request_fingerprint != fingerprint
                ):
                    raise SupportIdempotencyPayloadMismatch
                self._last_submission_was_replay = True
                return SupportInquiryPublic.model_validate(operation.result_json)
            review = await self._session.scalar(
                select(SupportReview)
                .where(
                    SupportReview.token_hash == hashlib.sha256(review_token.encode()).hexdigest(),
                    SupportReview.guest_session_id == guest.guest_session_id,
                )
                .with_for_update()
            )
            if (
                review is None
                or review.consumed_at is not None
                or review.invalidated_at is not None
                or review.expires_at <= datetime.now(UTC)
            ):
                raise SupportReviewInvalid
            content = review.content_json
            if self._fingerprint("support_review", content) != review.content_digest:
                review.invalidated_at = datetime.now(UTC)
                raise SupportReviewInvalid
            now = datetime.now(UTC)
            reference = f"S-{uuid4().hex[:12].upper()}"
            inquiry = SupportInquiry(
                reference=reference,
                guest_session_id=guest.guest_session_id,
                operation_id=operation_id,
                contact_json=cast(dict[str, object], content["contact"]),
                subject=cast(str, content["subject"]),
                summary=cast(str, content["summary"]),
                conversation_context=cast(str | None, content["conversation_context"]),
            )
            self._session.add(inquiry)
            await self._session.flush()
            self._session.add(
                OutboxJob(
                    job_type="SUPPORT_SHEETS_SYNC",
                    aggregate_id=inquiry.id,
                    reference=reference,
                    payload_json={"reference": reference, "inquiry": content},
                )
            )
            review.consumed_at = now
            result = SupportInquiryPublic(
                reference=reference,
                submitted_at=now,
                message=(
                    "Your synthetic support inquiry was saved. It does not confirm real staff "
                    "notification."
                ),
            )
            self._store_operation(
                guest=guest,
                operation_id=operation_id,
                fingerprint=fingerprint,
                result=result,
            )
            return result

    async def reconcile(
        self, *, guest: GuestContext, operation_id: UUID
    ) -> SupportInquiryPublic | None:
        operation = await self._session.scalar(
            select(IdempotencyOperation).where(
                IdempotencyOperation.guest_session_id == guest.guest_session_id,
                IdempotencyOperation.operation_id == operation_id,
                IdempotencyOperation.operation_kind == "submit_support",
            )
        )
        return SupportInquiryPublic.model_validate(operation.result_json) if operation else None

    async def _previous_contact(self, *, guest: GuestContext) -> dict[str, object] | None:
        inquiry_contact = await self._session.scalar(
            select(SupportInquiry.contact_json)
            .where(SupportInquiry.guest_session_id == guest.guest_session_id)
            .order_by(SupportInquiry.submitted_at.desc())
        )
        if inquiry_contact is not None:
            return inquiry_contact
        quote_snapshot = await self._session.scalar(
            select(QuoteSubmission.snapshot_json)
            .where(QuoteSubmission.guest_session_id == guest.guest_session_id)
            .order_by(QuoteSubmission.submitted_at.desc())
        )
        if quote_snapshot is None:
            return None
        contact = quote_snapshot.get("contact")
        return contact if isinstance(contact, dict) else None

    def _store_operation(
        self,
        *,
        guest: GuestContext,
        operation_id: UUID,
        fingerprint: str,
        result: SupportInquiryPublic,
    ) -> None:
        self._session.add(
            IdempotencyOperation(
                operation_id=operation_id,
                guest_session_id=guest.guest_session_id,
                operation_kind="submit_support",
                request_fingerprint=fingerprint,
                result_json=result.model_dump(mode="json"),
            )
        )

    async def _renew_and_lock_guest(self, *, guest: GuestContext) -> None:
        try:
            await SessionService(self._session, self._settings).renew_activity(
                guest_session_id=guest.guest_session_id
            )
        except InvalidGuestSession:
            raise SupportSessionInvalid from None

    def _mutation_transaction(self):
        return (
            self._session.begin_nested()
            if self._session.in_transaction()
            else self._session.begin()
        )

    @staticmethod
    def _fingerprint(operation_kind: str, payload: dict[str, object]) -> str:
        canonical = json.dumps(
            {"operation_kind": operation_kind, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()
