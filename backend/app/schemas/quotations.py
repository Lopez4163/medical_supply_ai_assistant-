"""Public contracts for direct draft quotation controls."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.quotation import QuoteDraftStatus
from app.services.inventory import AvailabilityStatus


class _StrictQuotationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddQuoteLineRequest(_StrictQuotationModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(strict=True, gt=0)
    expected_version: int = Field(strict=True, ge=0)
    operation_id: UUID

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("SKU must not be blank.")
        return normalized


class UpdateQuoteLineRequest(_StrictQuotationModel):
    quantity: int = Field(strict=True, gt=0)
    mode: Literal["replace", "increment"]
    expected_version: int = Field(strict=True, ge=0)
    operation_id: UUID


class DeleteQuoteLineRequest(_StrictQuotationModel):
    expected_version: int = Field(strict=True, ge=0)
    operation_id: UUID


class DraftQuoteLinePublic(_StrictQuotationModel):
    """Current catalog display details with an indicative price captured at first add."""

    id: UUID
    sku: str
    product_id: str
    product_name: str
    selector_attributes: dict[str, object]
    sales_unit: str
    requested_quantity: int
    indicative_unit_price_usd: Decimal  # Ordinary edits do not replace this line snapshot.
    indicative_line_subtotal_usd: Decimal
    availability: AvailabilityStatus
    quantity_sufficient: bool
    availability_notice: str
    created_at: datetime
    updated_at: datetime


class DraftQuotePublic(_StrictQuotationModel):
    id: UUID
    status: QuoteDraftStatus
    version: int = Field(ge=0)
    lines: list[DraftQuoteLinePublic]
    indicative_total_usd: Decimal
    created_at: datetime
    updated_at: datetime


class DraftQuoteResponse(_StrictQuotationModel):
    draft: DraftQuotePublic | None
