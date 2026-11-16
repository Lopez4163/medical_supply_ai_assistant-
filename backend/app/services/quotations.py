"""Deterministic, session-scoped quotation draft mutations."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.models.catalog import ProductListing, SkuVariant
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
from app.schemas.quotations import (
    DraftQuoteLinePublic,
    DraftQuotePublic,
    QuoteReviewPublic,
    QuoteSubmissionPublic,
)
from app.services.catalog import CatalogService
from app.services.inventory import AvailabilityStatus, InventoryCheck, InventoryService
from app.services.sessions import GuestContext, InvalidGuestSession, SessionService


class QuoteVersionConflict(Exception):
    pass


class QuoteLineNotFound(Exception):
    pass


class QuoteSkuNotFound(Exception):
    pass


class QuoteSkuUnresolved(Exception):
    pass


class IdempotencyPayloadMismatch(Exception):
    pass


class QuoteSessionInvalid(Exception):
    pass


class QuoteReviewInvalid(Exception):
    pass


class QuotationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._last_submission_was_replay = False

    @property
    def last_submission_was_replay(self) -> bool:
        return self._last_submission_was_replay

    async def get_draft(self, *, guest: GuestContext) -> DraftQuotePublic | None:
        draft = await self._session.scalar(
            select(QuoteDraft).where(
                QuoteDraft.guest_session_id == guest.guest_session_id,
                QuoteDraft.status == QuoteDraftStatus.ACTIVE,
            )
        )
        return await self._project_draft(draft) if draft is not None else None

    async def add_line(
        self,
        *,
        guest: GuestContext,
        sku: str,
        quantity: int,
        expected_version: int,
        operation_id: UUID,
    ) -> DraftQuotePublic:
        quantity = InventoryService.validate_requested_quantity(quantity)
        fingerprint = self._fingerprint(
            "add_line", {"sku": sku, "quantity": quantity, "expected_version": expected_version}
        )
        async with self._mutation_transaction():
            await self._renew_and_lock_guest(guest=guest)
            replay = await self._replay_if_committed(
                guest=guest,
                operation_id=operation_id,
                operation_kind="add_line",
                fingerprint=fingerprint,
            )
            if replay is not None:
                return replay
            variant = await CatalogService(self._session).get_sku(sku=sku)
            if variant is None:
                if (
                    await CatalogService(self._session).get_product_family(product_id=sku)
                    is not None
                ):
                    raise QuoteSkuUnresolved
                raise QuoteSkuNotFound
            variant_id = await self._session.scalar(
                select(SkuVariant.id).where(SkuVariant.sku == variant.sku)
            )
            assert variant_id is not None
            draft = await self._locked_draft(guest=guest)
            if draft is None:
                if expected_version != 0:
                    raise QuoteVersionConflict
                draft = QuoteDraft(guest_session_id=guest.guest_session_id)
                self._session.add(draft)
                await self._session.flush()
            elif draft.version != expected_version:
                raise QuoteVersionConflict
            line = await self._session.scalar(
                select(QuoteDraftLine)
                .where(
                    QuoteDraftLine.draft_id == draft.id, QuoteDraftLine.sku_variant_id == variant_id
                )
                .with_for_update()
            )
            if line is None:
                line = QuoteDraftLine(
                    draft_id=draft.id,
                    sku_variant_id=variant_id,
                    quantity=quantity,
                    indicative_unit_price=variant.indicative_price,
                )
                self._session.add(line)
            else:
                line.quantity += quantity
            draft.version += 1
            await self._invalidate_reviews(draft.id)
            await self._session.flush()
            result = await self._project_draft(draft)
            self._store_operation(
                guest=guest,
                operation_id=operation_id,
                operation_kind="add_line",
                fingerprint=fingerprint,
                result=result,
            )
        return result

    async def update_line(
        self,
        *,
        guest: GuestContext,
        line_id: UUID,
        quantity: int,
        mode: Literal["replace", "increment"],
        expected_version: int,
        operation_id: UUID,
    ) -> DraftQuotePublic:
        quantity = InventoryService.validate_requested_quantity(quantity)
        fingerprint = self._fingerprint(
            "update_line",
            {
                "line_id": str(line_id),
                "quantity": quantity,
                "mode": mode,
                "expected_version": expected_version,
            },
        )
        async with self._mutation_transaction():
            await self._renew_and_lock_guest(guest=guest)
            replay = await self._replay_if_committed(
                guest=guest,
                operation_id=operation_id,
                operation_kind="update_line",
                fingerprint=fingerprint,
            )
            if replay is not None:
                return replay
            draft = await self._locked_draft(guest=guest)
            if draft is None:
                raise QuoteLineNotFound
            if draft.version != expected_version:
                raise QuoteVersionConflict
            line = await self._session.scalar(
                select(QuoteDraftLine)
                .where(QuoteDraftLine.id == line_id, QuoteDraftLine.draft_id == draft.id)
                .with_for_update()
            )
            if line is None:
                raise QuoteLineNotFound
            line.quantity = quantity if mode == "replace" else line.quantity + quantity
            draft.version += 1
            await self._invalidate_reviews(draft.id)
            await self._session.flush()
            result = await self._project_draft(draft)
            self._store_operation(
                guest=guest,
                operation_id=operation_id,
                operation_kind="update_line",
                fingerprint=fingerprint,
                result=result,
            )
        return result

    async def remove_line(
        self, *, guest: GuestContext, line_id: UUID, expected_version: int, operation_id: UUID
    ) -> DraftQuotePublic:
        fingerprint = self._fingerprint(
            "remove_line", {"line_id": str(line_id), "expected_version": expected_version}
        )
        async with self._mutation_transaction():
            await self._renew_and_lock_guest(guest=guest)
            replay = await self._replay_if_committed(
                guest=guest,
                operation_id=operation_id,
                operation_kind="remove_line",
                fingerprint=fingerprint,
            )
            if replay is not None:
                return replay
            draft = await self._locked_draft(guest=guest)
            if draft is None:
                raise QuoteLineNotFound
            if draft.version != expected_version:
                raise QuoteVersionConflict
            line = await self._session.scalar(
                select(QuoteDraftLine)
                .where(QuoteDraftLine.id == line_id, QuoteDraftLine.draft_id == draft.id)
                .with_for_update()
            )
            if line is None:
                raise QuoteLineNotFound
            await self._session.delete(line)
            draft.version += 1
            await self._invalidate_reviews(draft.id)
            await self._session.flush()
            result = await self._project_draft(draft)
            self._store_operation(
                guest=guest,
                operation_id=operation_id,
                operation_kind="remove_line",
                fingerprint=fingerprint,
                result=result,
            )
        return result

    async def review_draft(
        self,
        *,
        guest: GuestContext,
        expected_version: int,
        contact: dict[str, object],
        fulfillment: str,
        delivery_city: str | None,
    ) -> QuoteReviewPublic:
        if not contact.get("email") and not contact.get("phone"):
            raise ValueError("Provide an email address or phone number.")
        if fulfillment == "delivery" and not (delivery_city or "").strip():
            raise ValueError("Delivery city is required.")
        if fulfillment == "cali_pickup" and delivery_city is not None:
            raise ValueError("Pickup does not accept a delivery city.")
        async with self._mutation_transaction():
            await self._renew_and_lock_guest(guest=guest)
            draft = await self._locked_draft(guest=guest)
            if draft is None or draft.version != expected_version:
                raise QuoteVersionConflict
            content, projected = await self._current_review_content(
                draft=draft,
                contact=contact,
                fulfillment=fulfillment,
                delivery_city=delivery_city,
            )
            if not projected.lines:
                raise QuoteReviewInvalid
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(minutes=15)
            self._session.add(
                ProtectedReview(
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    guest_session_id=guest.guest_session_id,
                    draft_id=draft.id,
                    draft_version=draft.version,
                    content_digest=self._fingerprint("quote_review", content),
                    content_json=content,
                    expires_at=expires_at,
                )
            )
            return QuoteReviewPublic(
                review_token=token,
                expires_at=expires_at,
                draft=projected,
                disclosure=(
                    "This synthetic quote request is not an order, reservation, or "
                    "fulfillment commitment."
                ),
            )

    async def submit_draft(
        self,
        *,
        guest: GuestContext,
        review_token: str,
        expected_version: int,
        operation_id: UUID,
    ) -> QuoteSubmissionPublic:
        self._last_submission_was_replay = False
        fingerprint = self._fingerprint(
            "submit_quote", {"review_token": review_token, "expected_version": expected_version}
        )
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
                    operation.operation_kind != "submit_quote"
                    or operation.request_fingerprint != fingerprint
                ):
                    raise IdempotencyPayloadMismatch
                self._last_submission_was_replay = True
                return QuoteSubmissionPublic.model_validate(operation.result_json)
            draft = await self._locked_draft(guest=guest)
            if draft is None or draft.version != expected_version:
                raise QuoteVersionConflict
            review = await self._session.scalar(
                select(ProtectedReview)
                .where(
                    ProtectedReview.token_hash == hashlib.sha256(review_token.encode()).hexdigest(),
                    ProtectedReview.guest_session_id == guest.guest_session_id,
                    ProtectedReview.draft_id == draft.id,
                )
                .with_for_update()
            )
            if (
                review is None
                or review.draft_version != draft.version
                or review.consumed_at
                or review.invalidated_at
                or review.expires_at <= datetime.now(UTC)
            ):
                raise QuoteReviewInvalid
            content = review.content_json
            fresh_content, current = await self._current_review_content(
                draft=draft,
                contact=cast(dict[str, object], content["contact"]),
                fulfillment=cast(str, content["fulfillment"]),
                delivery_city=cast(str | None, content["delivery_city"]),
            )
            if self._fingerprint("quote_review", fresh_content) != review.content_digest:
                review.invalidated_at = datetime.now(UTC)
                raise QuoteReviewInvalid
            reference = f"Q-{uuid4().hex[:12].upper()}"
            now = datetime.now(UTC)
            submission = QuoteSubmission(
                reference=reference,
                guest_session_id=guest.guest_session_id,
                draft_id=draft.id,
                operation_id=operation_id,
                snapshot_json=content,
            )
            self._session.add(submission)
            await self._session.flush()
            variant_ids = dict(
                (
                    await self._session.execute(
                        select(QuoteDraftLine.id, QuoteDraftLine.sku_variant_id).where(
                            QuoteDraftLine.draft_id == draft.id
                        )
                    )
                ).all()
            )
            self._session.add_all(
                [
                    QuoteSubmissionLine(
                        submission_id=submission.id,
                        sku_variant_id=variant_ids[line.id],
                        sku=line.sku,
                        product_name=line.product_name,
                        sales_unit=line.sales_unit,
                        quantity=line.requested_quantity,
                        indicative_unit_price=line.indicative_unit_price_usd,
                        availability=line.availability.value,
                    )
                    for line in current.lines
                ]
            )
            self._session.add(
                OutboxJob(
                    job_type="QUOTE_SHEETS_SYNC",
                    aggregate_id=submission.id,
                    reference=reference,
                    payload_json={
                        "reference": reference,
                        "quote": content,
                    },
                )
            )
            draft.status = QuoteDraftStatus.SUBMITTED
            review.consumed_at = now
            result = QuoteSubmissionPublic(
                reference=reference,
                submitted_at=now,
                message=(
                    "Your synthetic quotation request was saved. It is not an order or "
                    "fulfillment confirmation."
                ),
            )
            self._store_operation(
                guest=guest,
                operation_id=operation_id,
                operation_kind="submit_quote",
                fingerprint=fingerprint,
                result=result,
            )
            return result

    async def reconcile_submission(
        self, *, guest: GuestContext, operation_id: UUID
    ) -> QuoteSubmissionPublic | None:
        operation = await self._session.scalar(
            select(IdempotencyOperation).where(
                IdempotencyOperation.guest_session_id == guest.guest_session_id,
                IdempotencyOperation.operation_id == operation_id,
                IdempotencyOperation.operation_kind == "submit_quote",
            )
        )
        return QuoteSubmissionPublic.model_validate(operation.result_json) if operation else None

    async def _invalidate_reviews(self, draft_id: UUID) -> None:
        reviews = await self._session.scalars(
            select(ProtectedReview).where(
                ProtectedReview.draft_id == draft_id,
                ProtectedReview.consumed_at.is_(None),
                ProtectedReview.invalidated_at.is_(None),
            )
        )
        for review in reviews:
            review.invalidated_at = datetime.now(UTC)

    async def _current_review_content(
        self,
        *,
        draft: QuoteDraft,
        contact: dict[str, object],
        fulfillment: str,
        delivery_city: str | None,
    ) -> tuple[dict[str, object], DraftQuotePublic]:
        """Project a review with current catalog price, never overwriting draft snapshots."""
        projected = await self._project_draft(draft)
        prices = dict(
            (
                await self._session.execute(
                    select(QuoteDraftLine.id, SkuVariant.indicative_price)
                    .join(SkuVariant, QuoteDraftLine.sku_variant_id == SkuVariant.id)
                    .where(QuoteDraftLine.draft_id == draft.id)
                )
            ).all()
        )
        lines = [
            line.model_copy(
                update={
                    "indicative_unit_price_usd": prices[line.id],
                    "indicative_line_subtotal_usd": prices[line.id] * line.requested_quantity,
                }
            )
            for line in projected.lines
        ]
        current = projected.model_copy(
            update={
                "lines": lines,
                "indicative_total_usd": sum(
                    (line.indicative_line_subtotal_usd for line in lines), Decimal("0.00")
                ),
            }
        )
        return (
            {
                "draft": current.model_dump(mode="json"),
                "contact": contact,
                "fulfillment": fulfillment,
                "delivery_city": delivery_city,
            },
            current,
        )

    async def _renew_and_lock_guest(self, *, guest: GuestContext) -> None:
        try:
            await SessionService(self._session, self._settings).renew_activity(
                guest_session_id=guest.guest_session_id
            )
        except InvalidGuestSession:
            raise QuoteSessionInvalid from None

    def _mutation_transaction(self):
        """Own an outer transaction, or compose safely under an integration transaction."""
        return (
            self._session.begin_nested()
            if self._session.in_transaction()
            else self._session.begin()
        )

    async def _locked_draft(self, *, guest: GuestContext) -> QuoteDraft | None:
        return await self._session.scalar(
            select(QuoteDraft)
            .where(
                QuoteDraft.guest_session_id == guest.guest_session_id,
                QuoteDraft.status == QuoteDraftStatus.ACTIVE,
            )
            .with_for_update()
        )

    async def _replay_if_committed(
        self, *, guest: GuestContext, operation_id: UUID, operation_kind: str, fingerprint: str
    ) -> DraftQuotePublic | None:
        operation = await self._session.scalar(
            select(IdempotencyOperation)
            .where(
                IdempotencyOperation.guest_session_id == guest.guest_session_id,
                IdempotencyOperation.operation_id == operation_id,
            )
            .with_for_update()
        )
        if operation is None:
            return None
        if (
            operation.operation_kind != operation_kind
            or operation.request_fingerprint != fingerprint
        ):
            raise IdempotencyPayloadMismatch
        return DraftQuotePublic.model_validate(operation.result_json)

    def _store_operation(
        self,
        *,
        guest: GuestContext,
        operation_id: UUID,
        operation_kind: str,
        fingerprint: str,
        result: DraftQuotePublic | QuoteSubmissionPublic,
    ) -> None:
        self._session.add(
            IdempotencyOperation(
                operation_id=operation_id,
                guest_session_id=guest.guest_session_id,
                operation_kind=operation_kind,
                request_fingerprint=fingerprint,
                result_json=result.model_dump(mode="json"),
            )
        )

    async def _project_draft(self, draft: QuoteDraft) -> DraftQuotePublic:
        """Project current catalog details with the original line price snapshot.

        API-04 must revalidate authoritative prices at review and submission.
        """
        rows = (
            await self._session.execute(
                select(QuoteDraftLine, SkuVariant, ProductListing)
                .join(SkuVariant, QuoteDraftLine.sku_variant_id == SkuVariant.id)
                .join(ProductListing, SkuVariant.listing_id == ProductListing.id)
                .where(QuoteDraftLine.draft_id == draft.id)
                .order_by(QuoteDraftLine.created_at, QuoteDraftLine.id)
            )
        ).all()
        inventory = InventoryService(self._session)
        lines: list[DraftQuoteLinePublic] = []
        for line, variant, listing in rows:
            check = await inventory.check_availability(sku=variant.sku, quantity=line.quantity)
            lines.append(
                DraftQuoteLinePublic(
                    id=line.id,
                    sku=variant.sku,
                    product_id=listing.product_id,
                    product_name=listing.name,
                    selector_attributes=variant.selector_attributes,
                    sales_unit=variant.sales_unit,
                    requested_quantity=line.quantity,
                    indicative_unit_price_usd=line.indicative_unit_price,
                    indicative_line_subtotal_usd=line.indicative_unit_price * line.quantity,
                    availability=check.availability,
                    quantity_sufficient=check.is_sufficient,
                    availability_notice=self._availability_notice(check),
                    created_at=line.created_at,
                    updated_at=line.updated_at,
                )
            )
        return DraftQuotePublic(
            id=draft.id,
            status=draft.status,
            version=draft.version,
            lines=lines,
            indicative_total_usd=sum(
                (line.indicative_line_subtotal_usd for line in lines), Decimal("0.00")
            ),
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

    @staticmethod
    def _availability_notice(check: InventoryCheck) -> str:
        if check.availability == AvailabilityStatus.OUT_OF_STOCK:
            return "This item is currently out of stock and remains in your draft as a request."
        if check.availability in {AvailabilityStatus.DISCONTINUED, AvailabilityStatus.UNAVAILABLE}:
            return "Current availability cannot support a fulfillment promise."
        if not check.is_sufficient:
            return (
                "The requested quantity is not currently available; "
                "it remains in your draft as a request."
            )
        if check.availability == AvailabilityStatus.LIMITED_STOCK:
            return "Limited availability for the requested quantity."
        return "Available for the requested quantity."

    @staticmethod
    def _fingerprint(kind: str, payload: dict[str, object]) -> str:
        normalized = json.dumps({"kind": kind, **payload}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode()).hexdigest()
