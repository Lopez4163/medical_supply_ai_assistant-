"""Validated public projections for persisted conversation history."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.products import AvailabilityResponse, ProductSearchResponse


class _StrictPublicModel(BaseModel):
    """Forbid unapproved fields in persisted customer-visible snapshots."""

    model_config = ConfigDict(extra="forbid")


class QuoteUpdateSnapshot(_StrictPublicModel):
    """Minimal quote display reference; authoritative quote data remains separate."""

    draft_id: UUID
    version: int = Field(ge=0)


class ConfirmationPromptSnapshot(_StrictPublicModel):
    """A display-only confirmation prompt without a protected action token."""

    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2_000)
    confirm_label: str = Field(min_length=1, max_length=100)


class SourceReferenceSnapshot(_StrictPublicModel):
    """Approved evidence metadata persisted with an assistant response."""

    source_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    excerpt: str = Field(min_length=1, max_length=2_000)


class SupportInquiryFormSnapshot(_StrictPublicModel):
    """Display metadata for the later opt-in support workflow."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)


class ProductResultsElement(_StrictPublicModel):
    kind: Literal["product_results"]
    result_set: ProductSearchResponse


class InventoryNoticeElement(_StrictPublicModel):
    kind: Literal["inventory_notice"]
    notice: AvailabilityResponse


class QuoteUpdateElement(_StrictPublicModel):
    kind: Literal["quote_update"]
    quote: QuoteUpdateSnapshot


class ConfirmationPromptElement(_StrictPublicModel):
    kind: Literal["confirmation_prompt"]
    prompt: ConfirmationPromptSnapshot


class SourceReferenceElement(_StrictPublicModel):
    kind: Literal["source_reference"]
    source: SourceReferenceSnapshot


class SupportInquiryFormElement(_StrictPublicModel):
    kind: Literal["support_inquiry_form"]
    form: SupportInquiryFormSnapshot


AssistantElement = Annotated[
    ProductResultsElement
    | InventoryNoticeElement
    | QuoteUpdateElement
    | ConfirmationPromptElement
    | SourceReferenceElement
    | SupportInquiryFormElement,
    Field(discriminator="kind"),
]


class ConversationMessageContent(_StrictPublicModel):
    text: str = Field(min_length=1, max_length=8_000)


class ConversationMessagePublic(_StrictPublicModel):
    id: UUID
    role: Literal["user", "assistant"]
    kind: Literal["welcome", "turn"]
    ordinal: int = Field(ge=0)
    text: str
    elements: list[AssistantElement]
    created_at: datetime
    freshness: Literal["historical_snapshot"] = "historical_snapshot"


class ConversationHistoryResponse(_StrictPublicModel):
    conversation_id: UUID
    messages: list[ConversationMessagePublic]
