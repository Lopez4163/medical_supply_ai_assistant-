"""Deterministic, session-scoped quotation draft mutations."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.models.catalog import ProductListing, SkuVariant
from app.models.quotation import IdempotencyOperation, QuoteDraft, QuoteDraftLine, QuoteDraftStatus
from app.schemas.quotations import DraftQuoteLinePublic, DraftQuotePublic
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


class QuotationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

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
        result: DraftQuotePublic,
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
