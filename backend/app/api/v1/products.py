"""Public-safe, read-only catalog and inventory endpoints."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error_responses
from app.core.settings import get_settings
from app.db.session import get_db_session
from app.schemas.products import (
    AvailabilityRequest,
    AvailabilityResponse,
    ProductCardPublic,
    ProductDetailPublic,
    ProductSearchResponse,
)
from app.services.catalog import CatalogSearchFilters, CatalogService, CatalogVariant
from app.services.inventory import (
    AvailabilityStatus,
    InventoryCheck,
    InventoryService,
    ProposedLimitedStockThresholdPolicy,
)

router = APIRouter(prefix="/products", tags=["products"])

_PAGE_SIZE = 5
_CURSOR_VERSION = 1
_CURSOR_FIELDS = (
    "q",
    "sku",
    "product_id",
    "category",
    "size",
    "material",
    "product_type",
    "model_system",
    "capacity",
    "sales_unit",
    "attribute_key",
    "attribute_value",
)


@dataclass(frozen=True)
class _SearchContext:
    q: str | None
    sku: str | None
    product_id: str | None
    category: str | None
    size: str | None
    material: str | None
    product_type: str | None
    model_system: str | None
    capacity: str | None
    sales_unit: str | None
    attribute_key: str | None
    attribute_value: str | None

    def to_filters(self) -> CatalogSearchFilters:
        attributes: dict[str, str | int | bool] | None = (
            {self.attribute_key: self.attribute_value}
            if self.attribute_key is not None and self.attribute_value is not None
            else None
        )
        return CatalogSearchFilters(
            query=self.q,
            sku=self.sku,
            product_id=self.product_id,
            category=self.category,
            size=self.size,
            material=self.material,
            product_type=self.product_type,
            model_system=self.model_system,
            capacity=self.capacity,
            sales_unit=self.sales_unit,
            attributes=attributes,
        )


def _normalize_optional(value: str | None, *, uppercase: bool = False) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    if not normalized_value:
        return None
    return normalized_value.upper() if uppercase else normalized_value.casefold()


def _search_context(
    *,
    q: str | None,
    sku: str | None,
    product_id: str | None,
    category: str | None,
    size: str | None,
    material: str | None,
    product_type: str | None,
    model_system: str | None,
    capacity: str | None,
    sales_unit: str | None,
    attribute_key: str | None,
    attribute_value: str | None,
) -> _SearchContext:
    normalized_attribute_key = _normalize_optional(attribute_key)
    normalized_attribute_value = _normalize_optional(attribute_value)
    if (normalized_attribute_key is None) != (normalized_attribute_value is None):
        raise HTTPException(
            status_code=422,
            detail="attribute_key and attribute_value must be provided together.",
        )
    return _SearchContext(
        q=_normalize_optional(q),
        sku=_normalize_optional(sku, uppercase=True),
        product_id=_normalize_optional(product_id, uppercase=True),
        category=_normalize_optional(category),
        size=_normalize_optional(size),
        material=_normalize_optional(material),
        product_type=_normalize_optional(product_type),
        model_system=_normalize_optional(model_system),
        capacity=_normalize_optional(capacity),
        sales_unit=_normalize_optional(sales_unit),
        attribute_key=normalized_attribute_key,
        attribute_value=normalized_attribute_value,
    )


def _cursor_signing_key() -> bytes:
    """Derive an internal cursor signing key without placing a secret in source control."""
    return hashlib.sha256(get_settings().database_url.encode()).digest()


def _encode_cursor(*, offset: int, context: _SearchContext) -> str:
    payload = json.dumps(
        {"context": asdict(context), "offset": offset, "version": _CURSOR_VERSION},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    encoded_payload = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(_cursor_signing_key(), encoded_payload, hashlib.sha256).digest()
    return f"{encoded_payload.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _decode_cursor(cursor: str) -> tuple[int, _SearchContext]:
    try:
        encoded_payload, encoded_signature = cursor.split(".")
        expected_signature = hmac.new(
            _cursor_signing_key(), encoded_payload.encode(), hashlib.sha256
        ).digest()
        provided_signature = base64.b64decode(
            f"{encoded_signature}{'=' * (-len(encoded_signature) % 4)}",
            altchars=b"-_",
            validate=True,
        )
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise ValueError
        payload = json.loads(
            base64.b64decode(
                f"{encoded_payload}{'=' * (-len(encoded_payload) % 4)}",
                altchars=b"-_",
                validate=True,
            )
        )
        if (
            not isinstance(payload, dict)
            or payload.get("version") != _CURSOR_VERSION
            or not isinstance(payload.get("offset"), int)
            or payload["offset"] < 1
            or not isinstance(payload.get("context"), dict)
            or set(payload["context"]) != set(_CURSOR_FIELDS)
        ):
            raise ValueError
        context = _SearchContext(**payload["context"])
    except TypeError, ValueError, json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid search cursor.") from None
    return payload["offset"], context


def _merge_cursor_context(
    request_context: _SearchContext, cursor_context: _SearchContext
) -> _SearchContext:
    request_values = asdict(request_context)
    cursor_values = asdict(cursor_context)
    if any(
        request_values[field] is not None and request_values[field] != cursor_values[field]
        for field in _CURSOR_FIELDS
    ):
        raise HTTPException(status_code=422, detail="Search cursor does not match the filters.")
    return cursor_context


def _to_card(variant: CatalogVariant, availability: AvailabilityStatus) -> ProductCardPublic:
    return ProductCardPublic(
        sku=variant.sku,
        product_id=variant.product_id,
        name=variant.name,
        category_code=variant.category_code,
        category_name=variant.category_name,
        sales_unit=variant.sales_unit,
        indicative_price_usd=variant.indicative_price,
        lifecycle_status=variant.lifecycle_status,
        selector_attributes=variant.selector_attributes,
        primary_image_reference=variant.primary_image_reference,
        image_fallback_key=variant.image_fallback_key,
        availability=availability,
    )


def _availability_message(check: InventoryCheck) -> str:
    if check.availability == AvailabilityStatus.DISCONTINUED:
        return "This item is discontinued."
    if check.availability == AvailabilityStatus.OUT_OF_STOCK:
        return "This item is currently out of stock."
    if check.availability == AvailabilityStatus.UNAVAILABLE:
        return "Current availability cannot be verified."
    if check.is_sufficient:
        if check.availability == AvailabilityStatus.LIMITED_STOCK:
            return "Limited availability for the requested quantity."
        return "Available for the requested quantity."
    return "The requested quantity is not currently available."


@router.get("/search", response_model=ProductSearchResponse, responses=api_error_responses(422))
async def search_products(
    q: Annotated[str | None, Query(max_length=200)] = None,
    sku: Annotated[str | None, Query(max_length=64)] = None,
    product_id: Annotated[str | None, Query(max_length=64)] = None,
    category: Annotated[str | None, Query(max_length=128)] = None,
    size: Annotated[str | None, Query(max_length=128)] = None,
    material: Annotated[str | None, Query(max_length=128)] = None,
    product_type: Annotated[str | None, Query(max_length=128)] = None,
    model_system: Annotated[str | None, Query(max_length=128)] = None,
    capacity: Annotated[str | None, Query(max_length=128)] = None,
    sales_unit: Annotated[str | None, Query(max_length=128)] = None,
    attribute_key: Annotated[str | None, Query(max_length=128)] = None,
    attribute_value: Annotated[str | None, Query(max_length=128)] = None,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
    session: AsyncSession = Depends(get_db_session),
) -> ProductSearchResponse:
    """Search public catalog fields in deterministic, five-card batches."""
    request_context = _search_context(
        q=q,
        sku=sku,
        product_id=product_id,
        category=category,
        size=size,
        material=material,
        product_type=product_type,
        model_system=model_system,
        capacity=capacity,
        sales_unit=sales_unit,
        attribute_key=attribute_key,
        attribute_value=attribute_value,
    )
    offset = 0
    context = request_context
    if cursor is not None:
        offset, cursor_context = _decode_cursor(cursor)
        context = _merge_cursor_context(request_context, cursor_context)

    variants = await CatalogService(session).search(filters=context.to_filters())
    page = variants[offset : offset + _PAGE_SIZE]
    inventory_service = InventoryService(
        session, threshold_policy=ProposedLimitedStockThresholdPolicy()
    )
    products = [
        _to_card(
            variant,
            (await inventory_service.check_availability(sku=variant.sku, quantity=1)).availability,
        )
        for variant in page
    ]
    next_offset = offset + len(page)
    return ProductSearchResponse(
        products=products,
        next_cursor=(
            _encode_cursor(offset=next_offset, context=context)
            if next_offset < len(variants)
            else None
        ),
    )


@router.get("/{sku}", response_model=ProductDetailPublic, responses=api_error_responses(404))
async def get_product(
    sku: str,
    session: AsyncSession = Depends(get_db_session),
) -> ProductDetailPublic:
    """Return one resolved SKU without exposing private inventory."""
    variant = await CatalogService(session).get_sku(sku=sku)
    if variant is None:
        raise HTTPException(status_code=404, detail="Product SKU was not found.")
    availability = await InventoryService(
        session, threshold_policy=ProposedLimitedStockThresholdPolicy()
    ).check_availability(sku=variant.sku, quantity=1)
    card = _to_card(variant, availability.availability)
    return ProductDetailPublic(
        **card.model_dump(),
        description=variant.description,
        searchable_attributes=variant.searchable_attributes,
    )


@router.post(
    "/availability", response_model=AvailabilityResponse, responses=api_error_responses(404, 422)
)
async def check_product_availability(
    request: AvailabilityRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AvailabilityResponse:
    """Check one requested quantity against current private PostgreSQL inventory."""
    if await CatalogService(session).get_sku(sku=request.sku) is None:
        raise HTTPException(status_code=404, detail="Product SKU was not found.")
    check = await InventoryService(
        session, threshold_policy=ProposedLimitedStockThresholdPolicy()
    ).check_availability(sku=request.sku, quantity=request.quantity)
    return AvailabilityResponse(
        sku=check.sku,
        availability=check.availability,
        quantity_sufficient=check.is_sufficient,
        message=_availability_message(check),
    )
