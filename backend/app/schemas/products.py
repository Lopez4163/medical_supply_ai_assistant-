"""Public-safe catalog and inventory HTTP contracts."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.catalog import CatalogLifecycleStatus
from app.services.inventory import AvailabilityStatus


class _StrictPublicProductModel(BaseModel):
    """Reject fields that are not approved for browser-facing product projections."""

    model_config = ConfigDict(extra="forbid")


class ProductCardPublic(_StrictPublicProductModel):
    """A resolved sellable SKU suitable for a product-results batch."""

    sku: str
    product_id: str
    name: str
    category_code: str
    category_name: str
    sales_unit: str
    indicative_price_usd: Decimal
    lifecycle_status: CatalogLifecycleStatus
    selector_attributes: dict[str, object]
    primary_image_reference: str | None
    image_fallback_key: str
    availability: AvailabilityStatus


class ProductSearchResponse(_StrictPublicProductModel):
    products: list[ProductCardPublic] = Field(max_length=5)
    next_cursor: str | None


class ProductDetailPublic(ProductCardPublic):
    description: str
    searchable_attributes: dict[str, object]


class AvailabilityRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(strict=True, gt=0)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        normalized_sku = value.strip().upper()
        if not normalized_sku:
            raise ValueError("SKU must not be blank.")
        return normalized_sku


class AvailabilityResponse(_StrictPublicProductModel):
    sku: str
    availability: AvailabilityStatus
    quantity_sufficient: bool
    message: str
