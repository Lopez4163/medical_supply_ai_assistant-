"""Draft quotation persistence owned by the deterministic quotation service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class QuoteDraftStatus(StrEnum):
    ACTIVE = "active"
    SUBMITTED = "submitted"


class IdempotencyOperationStatus(StrEnum):
    COMMITTED = "committed"


class QuoteDraft(Base):
    __tablename__ = "quote_drafts"
    __table_args__ = (
        CheckConstraint("version >= 0", name="ck_quote_drafts_version_nonnegative"),
        Index(
            "uq_quote_drafts_active_guest_session",
            "guest_session_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    guest_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[QuoteDraftStatus] = mapped_column(
        Enum(QuoteDraftStatus, name="quote_draft_status", values_callable=_enum_values),
        nullable=False,
        default=QuoteDraftStatus.ACTIVE,
        server_default=text("'active'"),
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class QuoteDraftLine(Base):
    __tablename__ = "quote_draft_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quote_draft_lines_quantity_positive"),
        CheckConstraint("indicative_unit_price > 0", name="ck_quote_draft_lines_price_positive"),
        UniqueConstraint("draft_id", "sku_variant_id", name="uq_quote_draft_lines_draft_sku"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("quote_drafts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sku_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("sku_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    indicative_unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class IdempotencyOperation(Base):
    __tablename__ = "idempotency_operations"
    __table_args__ = (
        UniqueConstraint(
            "guest_session_id", "operation_id", name="uq_idempotency_operations_session_operation"
        ),
        CheckConstraint(
            "length(btrim(operation_kind)) > 0", name="ck_idempotency_operations_kind_not_blank"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(nullable=False)
    guest_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    operation_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[IdempotencyOperationStatus] = mapped_column(
        Enum(
            IdempotencyOperationStatus,
            name="idempotency_operation_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=IdempotencyOperationStatus.COMMITTED,
        server_default=text("'committed'"),
    )
    result_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class ProtectedReview(Base):
    __tablename__ = "protected_reviews"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    guest_session_id: Mapped[UUID] = mapped_column(ForeignKey("guest_sessions.id"), index=True)
    draft_id: Mapped[UUID] = mapped_column(ForeignKey("quote_drafts.id"), index=True)
    draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuoteSubmission(Base):
    __tablename__ = "quote_submissions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reference: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    guest_session_id: Mapped[UUID] = mapped_column(ForeignKey("guest_sessions.id"), index=True)
    draft_id: Mapped[UUID] = mapped_column(ForeignKey("quote_drafts.id"), unique=True)
    operation_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class QuoteSubmissionLine(Base):
    __tablename__ = "quote_submission_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quote_submission_lines_quantity_positive"),
        CheckConstraint(
            "indicative_unit_price > 0", name="ck_quote_submission_lines_price_positive"
        ),
        UniqueConstraint("submission_id", "sku", name="uq_quote_submission_lines_submission_sku"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(
        ForeignKey("quote_submissions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sku_variant_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sales_unit: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    indicative_unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)


class OutboxJob(Base):
    __tablename__ = "outbox_jobs"
    __table_args__ = (
        UniqueConstraint("job_type", "aggregate_id", name="uq_outbox_jobs_aggregate"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    reference: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
