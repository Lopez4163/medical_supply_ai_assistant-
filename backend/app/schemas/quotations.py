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


class QuoteContact(_StrictQuotationModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("first_name", "last_name")
    @classmethod
    def names_are_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank.")
        return value

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        if value and "@" not in value:
            raise ValueError("Email must be valid.")
        return value

    @field_validator("phone")
    @classmethod
    def phone_is_not_blank(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class QuoteReviewRequest(_StrictQuotationModel):
    expected_version: int = Field(strict=True, ge=0)
    contact: QuoteContact
    fulfillment: Literal["delivery", "cali_pickup"]
    delivery_city: str | None = Field(default=None, max_length=100)


class QuoteReviewPublic(_StrictQuotationModel):
    review_token: str
    expires_at: datetime
    draft: DraftQuotePublic
    disclosure: str


class QuoteSubmitRequest(_StrictQuotationModel):
    review_token: str = Field(min_length=20, max_length=200)
    expected_version: int = Field(strict=True, ge=0)
    confirmation: Literal[True]
    operation_id: UUID


class QuoteSubmissionPublic(_StrictQuotationModel):
    reference: str
    submitted_at: datetime
    message: str
