"""Persistent, provider-reported AI usage observations."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiUsageRecord(Base):
    """One gateway attempt, with provider usage only when the provider supplied it."""

    __tablename__ = "ai_usage_records"
    __table_args__ = (
        CheckConstraint("latency_ms >= 0", name="ck_ai_usage_records_latency_nonnegative"),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_usage_records_input_tokens_nonnegative",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_usage_records_output_tokens_nonnegative",
        ),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_ai_usage_records_total_tokens_nonnegative",
        ),
        CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
            name="ck_ai_usage_records_cost_nonnegative",
        ),
        Index("ix_ai_usage_records_conversation_id", "conversation_id"),
        Index("ix_ai_usage_records_recorded_at", "recorded_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="RESTRICT"), nullable=True
    )
    correlation_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    selected_model: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_model: Mapped[str | None] = mapped_column(String(200))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 8))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    error_class: Mapped[str | None] = mapped_column(String(64))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
