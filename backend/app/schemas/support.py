"""Strict public contracts for synthetic support inquiries."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictSupportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupportContact(_StrictSupportModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("first_name", "last_name")
    @classmethod
    def names_are_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name must not be blank.")
        return normalized

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        if normalized and "@" not in normalized:
            raise ValueError("Email must be valid.")
        return normalized

    @field_validator("phone")
    @classmethod
    def phone_is_not_blank(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @model_validator(mode="after")
    def has_contact_method(self) -> SupportContact:
        if not self.email and not self.phone:
            raise ValueError("Provide an email address or phone number.")
        return self


class SupportReviewRequest(_StrictSupportModel):
    opt_in: Literal[True]
    reuse_contact: bool = False
    contact: SupportContact | None = None
    subject: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2_000)
    conversation_context: str | None = Field(default=None, max_length=2_000)

    @field_validator("subject", "summary", "conversation_context")
    @classmethod
    def text_is_not_blank(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        if value is not None and not normalized:
            raise ValueError("Text must not be blank.")
        return normalized

    @model_validator(mode="after")
    def requires_contact_or_explicit_reuse(self) -> SupportReviewRequest:
        if self.reuse_contact == (self.contact is not None):
            raise ValueError("Provide contact details or explicitly reuse prior contact details.")
        return self


class SupportReviewPublic(_StrictSupportModel):
    review_token: str
    expires_at: datetime
    subject: str
    summary: str
    disclosure: str


class SupportSubmitRequest(_StrictSupportModel):
    review_token: str = Field(min_length=20, max_length=200)
    confirmation: Literal[True]
    operation_id: UUID


class SupportInquiryPublic(_StrictSupportModel):
    reference: str
    submitted_at: datetime
    message: str
