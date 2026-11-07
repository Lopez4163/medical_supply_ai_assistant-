"""Deterministic catalog lookup, filtering, compatibility, and alternatives services."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import (
    CatalogLifecycleStatus,
    CompatibilityState,
    InventoryItem,
    ProductCategory,
    ProductListing,
    SkuCompatibility,
    SkuVariant,
)
from app.services.inventory import InventoryService, LimitedStockThresholdPolicy


@dataclass(frozen=True)
class CatalogVariant:
    sku: str
    product_id: str
    category_code: str
    name: str
    description: str
    sales_unit: str
    indicative_price: Decimal
    lifecycle_status: CatalogLifecycleStatus
    selector_attributes: dict[str, object]
    searchable_attributes: dict[str, object]
    primary_image_reference: str | None
    image_fallback_key: str


@dataclass(frozen=True)
class ProductFamily:
    product_id: str
    category_code: str
    name: str
    description: str
    lifecycle_status: CatalogLifecycleStatus
    primary_image_reference: str | None
    image_fallback_key: str
    variants: tuple[CatalogVariant, ...]


@dataclass(frozen=True)
class CatalogSearchFilters:
    query: str | None = None
    sku: str | None = None
    product_id: str | None = None
    category: str | None = None
    size: str | None = None
    material: str | None = None
    product_type: str | None = None
    model_system: str | None = None
    capacity: str | int | None = None
    sales_unit: str | None = None
    attributes: dict[str, str | int | bool] | None = None


@dataclass(frozen=True)
class CompatibilityResult:
    first_sku: str
    second_sku: str
    state: CompatibilityState


@dataclass(frozen=True)
class CatalogAlternative:
    variant: CatalogVariant
    difference: str


@dataclass(frozen=True)
class _CatalogRow:
    variant: SkuVariant
    listing: ProductListing
    category: ProductCategory
    inventory: InventoryItem | None


_ESSENTIAL_ALTERNATIVE_ATTRIBUTES = {
    "size",
    "material",
    "meter_model",
    "strip_system",
    "lancet_system",
    "gauge",
    "capacity_ml",
    "tip_type",
    "use_route",
    "cuff_size",
    "dimensions",
    "absorbency",
    "form",
}


class CatalogService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        threshold_policy: LimitedStockThresholdPolicy | None = None,
    ) -> None:
        self._session = session
        self._inventory_service = InventoryService(session, threshold_policy=threshold_policy)

    async def get_sku(self, *, sku: str) -> CatalogVariant | None:
        row = await self._load_row_by_sku(sku=sku)
        return self._to_variant(row) if row is not None else None

    async def get_product_family(self, *, product_id: str) -> ProductFamily | None:
        rows = await self._load_rows(product_id=product_id)
        if not rows:
            return None

        first = rows[0]
        return ProductFamily(
            product_id=first.listing.product_id,
            category_code=first.category.code,
            name=first.listing.name,
            description=first.listing.description,
            lifecycle_status=first.listing.lifecycle_status,
            primary_image_reference=first.listing.primary_image_reference,
            image_fallback_key=first.listing.image_fallback_key,
            variants=tuple(self._to_variant(row) for row in rows),
        )

    async def search(self, *, filters: CatalogSearchFilters) -> tuple[CatalogVariant, ...]:
        rows = await self._load_rows()
        matching_rows = [row for row in rows if self._matches_filters(row, filters)]
        matching_rows.sort(key=lambda row: self._rank(row, filters))
        return tuple(self._to_variant(row) for row in matching_rows)

    async def check_compatibility(self, *, first_sku: str, second_sku: str) -> CompatibilityResult:
        first = await self._load_row_by_sku(sku=first_sku)
        second = await self._load_row_by_sku(sku=second_sku)
        if first is None or second is None:
            return CompatibilityResult(
                first_sku=first_sku,
                second_sku=second_sku,
                state=CompatibilityState.UNKNOWN,
            )

        return CompatibilityResult(
            first_sku=first.variant.sku,
            second_sku=second.variant.sku,
            state=await self._compatibility_state(first.variant.id, second.variant.id),
        )

    async def find_alternatives(
        self,
        *,
        sku: str,
        quantity: int,
        required_attributes: dict[str, str | int | bool] | None = None,
        compatible_with_sku: str | None = None,
    ) -> tuple[CatalogAlternative, ...]:
        self._inventory_service.validate_requested_quantity(quantity)
        original = await self._load_row_by_sku(sku=sku)
        if original is None:
            return ()

        alternatives: list[CatalogAlternative] = []
        for candidate in await self._load_rows():
            if len(alternatives) == 3:
                break
            if not self._is_eligible_alternative(original, candidate, required_attributes):
                continue
            if not await self._inventory_service.has_sufficient_inventory(
                sku=candidate.variant.sku, quantity=quantity
            ):
                continue
            if compatible_with_sku is not None:
                state = await self.check_compatibility(
                    first_sku=candidate.variant.sku,
                    second_sku=compatible_with_sku,
                )
                if state.state != CompatibilityState.COMPATIBLE:
                    continue
            alternatives.append(
                CatalogAlternative(
                    variant=self._to_variant(candidate),
                    difference=self._difference(original, candidate),
                )
            )
        return tuple(alternatives)

    async def _load_row_by_sku(self, *, sku: str) -> _CatalogRow | None:
        rows = await self._load_rows(sku=sku)
        return rows[0] if rows else None

    async def _load_rows(
        self,
        *,
        sku: str | None = None,
        product_id: str | None = None,
    ) -> list[_CatalogRow]:
        statement = (
            select(SkuVariant, ProductListing, ProductCategory, InventoryItem)
            .join(ProductListing, SkuVariant.listing_id == ProductListing.id)
            .join(ProductCategory, ProductListing.category_id == ProductCategory.id)
            .outerjoin(InventoryItem, InventoryItem.sku_variant_id == SkuVariant.id)
            .order_by(ProductCategory.code, ProductListing.product_id, SkuVariant.sku)
        )
        if sku is not None:
            statement = statement.where(SkuVariant.sku == sku.strip().upper())
        if product_id is not None:
            statement = statement.where(ProductListing.product_id == product_id.strip().upper())

        return [_CatalogRow(*row) for row in (await self._session.execute(statement)).all()]

    @staticmethod
    def _to_variant(row: _CatalogRow) -> CatalogVariant:
        return CatalogVariant(
            sku=row.variant.sku,
            product_id=row.listing.product_id,
            category_code=row.category.code,
            name=row.listing.name,
            description=row.listing.description,
            sales_unit=row.variant.sales_unit,
            indicative_price=row.variant.indicative_price,
            lifecycle_status=row.variant.lifecycle_status,
            selector_attributes=row.variant.selector_attributes,
            searchable_attributes={
                **row.listing.searchable_attributes,
                **row.variant.searchable_attributes,
            },
            primary_image_reference=row.listing.primary_image_reference,
            image_fallback_key=row.listing.image_fallback_key,
        )

    def _matches_filters(self, row: _CatalogRow, filters: CatalogSearchFilters) -> bool:
        if filters.sku is not None and row.variant.sku != filters.sku.strip().upper():
            return False
        if (
            filters.product_id is not None
            and row.listing.product_id != filters.product_id.strip().upper()
        ):
            return False
        if filters.category is not None and not self._category_matches(
            row.category, filters.category
        ):
            return False

        attributes = {**row.listing.searchable_attributes, **row.variant.searchable_attributes}
        if filters.size is not None and not self._value_matches(
            attributes.get("size"), filters.size
        ):
            return False
        if filters.material is not None and not self._value_matches(
            attributes.get("material"), filters.material
        ):
            return False
        if filters.product_type is not None and not self._value_matches(
            attributes.get("product_type"), filters.product_type
        ):
            return False
        if filters.model_system is not None and not any(
            self._value_matches(attributes.get(key), filters.model_system)
            for key in ("meter_model", "strip_system", "lancet_system")
        ):
            return False
        if filters.capacity is not None and not any(
            self._value_matches(attributes.get(key), filters.capacity)
            for key in ("capacity", "capacity_ml")
        ):
            return False
        if filters.sales_unit is not None and not self._text_contains(
            row.variant.sales_unit, filters.sales_unit
        ):
            return False
        if filters.attributes is not None and any(
            not self._value_matches(attributes.get(key), value)
            for key, value in filters.attributes.items()
        ):
            return False
        return filters.query is None or self._keyword_matches(row, filters.query)

    def _rank(self, row: _CatalogRow, filters: CatalogSearchFilters) -> tuple[int, int, int, str]:
        exact_match = int(
            (filters.sku is not None and row.variant.sku == filters.sku.strip().upper())
            or (
                filters.product_id is not None
                and row.listing.product_id == filters.product_id.strip().upper()
            )
            or self._query_has_exact_identifier(row, filters.query)
        )
        attribute_matches = sum(
            value is not None
            for value in (
                filters.size,
                filters.material,
                filters.product_type,
                filters.model_system,
                filters.capacity,
                filters.sales_unit,
            )
        ) + (len(filters.attributes) if filters.attributes is not None else 0)
        return (
            -exact_match,
            -attribute_matches,
            -self._keyword_score(row, filters.query),
            row.variant.sku,
        )

    @staticmethod
    def _query_has_exact_identifier(row: _CatalogRow, query: str | None) -> bool:
        if query is None:
            return False
        query_tokens = {token.upper() for token in query.split()}
        return row.variant.sku in query_tokens or row.listing.product_id in query_tokens

    @staticmethod
    def _category_matches(category: ProductCategory, requested: str) -> bool:
        normalized_requested = requested.strip().casefold()
        return normalized_requested in {category.code.casefold(), category.name.casefold()}

    @staticmethod
    def _value_matches(value: object | None, requested: str | int | bool) -> bool:
        return (
            value is not None and str(value).strip().casefold() == str(requested).strip().casefold()
        )

    @staticmethod
    def _text_contains(value: str, requested: str) -> bool:
        return requested.strip().casefold() in value.casefold()

    def _keyword_matches(self, row: _CatalogRow, query: str) -> bool:
        return self._keyword_score(row, query) > 0

    def _keyword_score(self, row: _CatalogRow, query: str | None) -> int:
        if query is None or not query.strip():
            return 0
        attributes = {**row.listing.searchable_attributes, **row.variant.searchable_attributes}
        searchable_text = " ".join(
            (
                row.variant.sku,
                row.listing.product_id,
                row.listing.name,
                row.listing.description,
                row.variant.sales_unit,
                " ".join(map(str, attributes.values())),
            )
        ).casefold()
        return sum(token in searchable_text for token in query.casefold().split())

    async def _compatibility_state(
        self, first_variant_id: UUID, second_variant_id: UUID
    ) -> CompatibilityState:
        state = await self._session.scalar(
            select(SkuCompatibility.state).where(
                or_(
                    and_(
                        SkuCompatibility.source_variant_id == first_variant_id,
                        SkuCompatibility.target_variant_id == second_variant_id,
                    ),
                    and_(
                        SkuCompatibility.source_variant_id == second_variant_id,
                        SkuCompatibility.target_variant_id == first_variant_id,
                    ),
                )
            )
        )
        return state if state is not None else CompatibilityState.UNKNOWN

    def _is_eligible_alternative(
        self,
        original: _CatalogRow,
        candidate: _CatalogRow,
        required_attributes: dict[str, str | int | bool] | None,
    ) -> bool:
        if candidate.variant.sku == original.variant.sku:
            return False
        if (
            not candidate.category.is_active
            or candidate.listing.lifecycle_status != CatalogLifecycleStatus.ACTIVE
            or candidate.variant.lifecycle_status != CatalogLifecycleStatus.ACTIVE
            or candidate.category.id != original.category.id
            or candidate.listing.id != original.listing.id
        ):
            return False

        original_attributes = {
            **original.listing.searchable_attributes,
            **original.variant.searchable_attributes,
        }
        candidate_attributes = {
            **candidate.listing.searchable_attributes,
            **candidate.variant.searchable_attributes,
        }
        for key in _ESSENTIAL_ALTERNATIVE_ATTRIBUTES:
            if (
                key in original_attributes
                and candidate_attributes.get(key) != original_attributes[key]
            ):
                return False
        if required_attributes is not None and any(
            candidate_attributes.get(key) != value for key, value in required_attributes.items()
        ):
            return False
        return True

    @staticmethod
    def _difference(original: _CatalogRow, candidate: _CatalogRow) -> str:
        for key in ("package_count", "capacity", "color", "seat_width_in"):
            original_value = original.variant.selector_attributes.get(key)
            candidate_value = candidate.variant.selector_attributes.get(key)
            if original_value != candidate_value and candidate_value is not None:
                return (
                    f"{key.replace('_', ' ').capitalize()}: {candidate_value} "
                    f"instead of {original_value}."
                )
        if candidate.variant.sales_unit != original.variant.sales_unit:
            return (
                f"Sales unit: {candidate.variant.sales_unit} "
                f"instead of {original.variant.sales_unit}."
            )
        if candidate.variant.indicative_price != original.variant.indicative_price:
            return "Indicative price differs."
        return "Different catalog SKU."
