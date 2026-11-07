"""Private inventory checks and public-safe availability projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import (
    CatalogLifecycleStatus,
    InventoryItem,
    ProductCategory,
    ProductListing,
    SkuVariant,
)


class AvailabilityStatus(StrEnum):
    IN_STOCK = "in_stock"
    LIMITED_STOCK = "limited_stock"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    UNAVAILABLE = "unavailable"


class InvalidRequestedQuantity(ValueError):
    """Raised when a request does not specify a positive whole quantity."""


@dataclass(frozen=True)
class InventoryCheck:
    """Public-safe result that deliberately omits exact stock."""

    sku: str
    availability: AvailabilityStatus
    is_sufficient: bool


@dataclass(frozen=True)
class _InventorySnapshot:
    sku: str
    category_code: str
    lifecycle_status: CatalogLifecycleStatus
    category_is_active: bool
    listing_is_active: bool
    quantity_on_hand: int | None
    selector_attributes: dict[str, object]


class LimitedStockThresholdPolicy:
    """Optional policy for classifying positive stock as limited rather than in stock."""

    def threshold_for(self, snapshot: _InventorySnapshot) -> int | None:
        raise NotImplementedError


class ProposedLimitedStockThresholdPolicy(LimitedStockThresholdPolicy):
    """Document 03's proposed thresholds; inject explicitly until independently approved."""

    def threshold_for(self, snapshot: _InventorySnapshot) -> int | None:
        if snapshot.category_code in {"MOB", "BTH", "DGN"}:
            return 3
        if snapshot.category_code == "DIA":
            if "meter_model" in snapshot.selector_attributes or snapshot.sku.endswith("-LDEV"):
                return 5
            return 20
        if snapshot.category_code in {"PPE", "WND", "CON", "SYR"}:
            return 20
        if snapshot.category_code == "OTC":
            return 15
        return None


class InventoryService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        threshold_policy: LimitedStockThresholdPolicy | None = None,
    ) -> None:
        self._session = session
        self._threshold_policy = threshold_policy

    @staticmethod
    def validate_requested_quantity(quantity: int) -> int:
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise InvalidRequestedQuantity("Requested quantity must be a positive whole number.")
        return quantity

    async def check_availability(self, *, sku: str, quantity: int) -> InventoryCheck:
        requested_quantity = self.validate_requested_quantity(quantity)
        snapshot = await self._load_snapshot(sku=sku)
        if snapshot is None:
            return InventoryCheck(
                sku=sku, availability=AvailabilityStatus.UNAVAILABLE, is_sufficient=False
            )

        availability = self._classify(snapshot)
        return InventoryCheck(
            sku=snapshot.sku,
            availability=availability,
            is_sufficient=(
                availability in {AvailabilityStatus.IN_STOCK, AvailabilityStatus.LIMITED_STOCK}
                and snapshot.quantity_on_hand is not None
                and snapshot.quantity_on_hand >= requested_quantity
            ),
        )

    async def has_sufficient_inventory(self, *, sku: str, quantity: int) -> bool:
        """Internal helper for deterministic services; it never projects a stock count."""
        requested_quantity = self.validate_requested_quantity(quantity)
        snapshot = await self._load_snapshot(sku=sku)
        if snapshot is None:
            return False
        return (
            self._classify(snapshot)
            in {AvailabilityStatus.IN_STOCK, AvailabilityStatus.LIMITED_STOCK}
            and snapshot.quantity_on_hand is not None
            and snapshot.quantity_on_hand >= requested_quantity
        )

    async def _load_snapshot(self, *, sku: str) -> _InventorySnapshot | None:
        result = await self._session.execute(
            select(SkuVariant, ProductListing, ProductCategory, InventoryItem)
            .join(ProductListing, SkuVariant.listing_id == ProductListing.id)
            .join(ProductCategory, ProductListing.category_id == ProductCategory.id)
            .outerjoin(InventoryItem, InventoryItem.sku_variant_id == SkuVariant.id)
            .where(SkuVariant.sku == sku)
        )
        row = result.one_or_none()
        if row is None:
            return None

        variant, listing, category, inventory = row
        return _InventorySnapshot(
            sku=variant.sku,
            category_code=category.code,
            lifecycle_status=variant.lifecycle_status,
            category_is_active=category.is_active,
            listing_is_active=listing.lifecycle_status == CatalogLifecycleStatus.ACTIVE,
            quantity_on_hand=inventory.quantity_on_hand if inventory is not None else None,
            selector_attributes=variant.selector_attributes,
        )

    def _classify(self, snapshot: _InventorySnapshot) -> AvailabilityStatus:
        if snapshot.lifecycle_status == CatalogLifecycleStatus.DISCONTINUED:
            return AvailabilityStatus.DISCONTINUED
        if not snapshot.category_is_active or not snapshot.listing_is_active:
            return AvailabilityStatus.UNAVAILABLE
        if snapshot.quantity_on_hand is None:
            return AvailabilityStatus.UNAVAILABLE
        if snapshot.quantity_on_hand == 0:
            return AvailabilityStatus.OUT_OF_STOCK

        threshold = (
            self._threshold_policy.threshold_for(snapshot) if self._threshold_policy else None
        )
        if threshold is not None and snapshot.quantity_on_hand <= threshold:
            return AvailabilityStatus.LIMITED_STOCK
        return AvailabilityStatus.IN_STOCK
